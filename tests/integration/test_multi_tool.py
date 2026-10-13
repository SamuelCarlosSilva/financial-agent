"""Encadeamento de ferramentas no mesmo turno: cotação → cálculo (US3 cenário 2, FR-007)."""

from decimal import Decimal

import httpx
import respx
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.config import Settings
from financial_agent.graph.builder import build_graph
from financial_agent.tools import get_tools
from tests.fakes import fake_llm

BASE_URL = "https://fx.test"
USD_BRL = {"USDBRL": {"bid": "5.4321", "ask": "5.4351", "create_date": "2026-10-07 14:30:05"}}
QUOTE_CALL = {"name": "get_currency_quote", "args": {"base": "USD"}, "id": "c1"}
CALC_CALL = {"name": "calculate", "args": {"expression": "500 * 5.4321"}, "id": "c2"}


def test_quote_then_calculation_cites_both_sources() -> None:
    llm = fake_llm(
        AIMessage("", tool_calls=[QUOTE_CALL]),
        AIMessage("", tool_calls=[CALC_CALL]),
        AIMessage(
            "US$ 500 equivalem a R$ 2716.05 (500 * 5.4321), usando o valor de compra (bid) "
            "da cotação USD-BRL de 07/10/2026 14:30."
        ),
    )
    tools = get_tools(Settings(FX_API_BASE_URL=BASE_URL))
    graph = build_graph(InMemorySaver(), llm, tools)

    with respx.mock(base_url=BASE_URL) as provider:
        provider.get("/json/last/USD-BRL").mock(return_value=httpx.Response(200, json=USD_BRL))
        with TestClient(create_app(graph=graph)) as client:
            response = client.post(
                "/v1/chat", json={"message": "Quanto são 500 dólares em reais hoje?"}
            )

    assert response.status_code == 200, response.text
    sources = response.json()["sources"]
    assert [s["type"] for s in sources] == ["fx_quote", "calculation"]
    assert sources[0]["pair"] == "USD-BRL"
    assert sources[0]["bid"] == "5.4321"
    assert sources[1]["expression"] == "500 * 5.4321"
    assert Decimal(sources[1]["result"]) == Decimal("2716.05")

    # O resultado veio da calculadora real, executada no laço agent ⇄ tools.
    calc_result = llm.calls[2][-1]
    assert isinstance(calc_result, ToolMessage)
    assert "2716.05" in str(calc_result.content)
