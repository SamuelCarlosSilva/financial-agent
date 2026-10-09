"""Fluxo de cotação pela API: fonte `fx_quote` citada e nenhum valor sem provedor (FR-012)."""

import re
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.config import Settings
from financial_agent.graph.builder import build_graph
from financial_agent.tools import get_tools
from financial_agent.tools.currency_quote import PROVIDER_UNAVAILABLE
from tests.fakes import FakeToolChatModel, fake_llm

BASE_URL = "https://fx.test"
QUOTE_CALL = {"name": "get_currency_quote", "args": {"base": "USD"}, "id": "c1"}
USD_BRL = {"USDBRL": {"bid": "5.4321", "ask": "5.4351", "create_date": "2026-10-07 14:30:05"}}


@pytest.fixture
def provider() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


def chat(llm: FakeToolChatModel, message: str) -> dict[str, object]:
    tools = get_tools(Settings(FX_API_BASE_URL=BASE_URL))
    graph = build_graph(InMemorySaver(), llm, tools)
    with TestClient(create_app(graph=graph)) as client:
        response = client.post("/v1/chat", json={"message": message})
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def test_quote_is_returned_as_fx_source(provider: respx.MockRouter) -> None:
    provider.get("/json/last/USD-BRL").mock(return_value=httpx.Response(200, json=USD_BRL))
    llm = fake_llm(
        AIMessage("", tool_calls=[QUOTE_CALL]),
        AIMessage("O dólar está em R$ 5.4321 para compra (bid), cotação de 07/10/2026 14:30."),
    )

    body = chat(llm, "Quanto está o dólar?")

    sources = body["sources"]
    assert isinstance(sources, list)
    assert sources == [
        {
            "type": "fx_quote",
            "pair": "USD-BRL",
            "bid": "5.4321",
            "ask": "5.4351",
            "quoted_at": "2026-10-07T14:30:05-03:00",
            "provider": "awesomeapi",
        }
    ]


def test_provider_down_gives_no_value(provider: respx.MockRouter) -> None:
    route = provider.get("/json/last/USD-BRL").mock(return_value=httpx.Response(503))
    llm = fake_llm(
        AIMessage("", tool_calls=[QUOTE_CALL]),
        AIMessage("A cotação do dólar está indisponível no momento. Tente novamente mais tarde."),
    )

    body = chat(llm, "Quanto está o dólar?")

    assert route.call_count == 2
    assert body["sources"] == []
    assert not re.search(r"\d", str(body["answer"]))
    # O agente não recebeu nenhum número da ferramenta que pudesse repassar ao usuário.
    tool_result = llm.calls[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert str(tool_result.content).startswith(PROVIDER_UNAVAILABLE)
    assert not re.search(r"\d", str(tool_result.content))
