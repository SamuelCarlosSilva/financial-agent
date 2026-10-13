"""Log `chat_turn` (FR-013): campos de auditoria, consumo de tokens e nada de conteúdo sensível."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from structlog.testing import capture_logs

from financial_agent.api.app import create_app
from financial_agent.graph.builder import build_graph
from financial_agent.graph.state import CalculationSource
from tests.fakes import fake_llm

SECRET_MESSAGE = "Meu CPF é 123.456.789-00, quanto é 2 + 2?"
API_KEY = "chave-super-secreta"


@tool(response_format="content_and_artifact")
def calculate(expression: str) -> tuple[str, CalculationSource]:
    """Calculadora falsa para os testes."""
    return f"{expression} = 4.00", CalculationSource(expression=expression, result=Decimal("4"))


def usage(input_tokens: int, output_tokens: int) -> UsageMetadata:
    return UsageMetadata(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def test_chat_turn_log_has_audit_fields_and_token_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEYS", API_KEY)
    call = {"name": "calculate", "args": {"expression": "2 + 2"}, "id": "c1"}
    llm = fake_llm(
        AIMessage("", tool_calls=[call], usage_metadata=usage(100, 10)),
        AIMessage("2 + 2 = 4.00", usage_metadata=usage(150, 20)),
    )
    graph = build_graph(InMemorySaver(), llm, tools=[calculate])

    with capture_logs() as logs, TestClient(create_app(graph=graph)) as client:
        response = client.post(
            "/v1/chat", json={"message": SECRET_MESSAGE}, headers={"X-API-Key": API_KEY}
        )

    assert response.status_code == 200
    [event] = [e for e in logs if e["event"] == "chat_turn"]
    assert event["scope_label"] == "in_scope"
    assert event["tools_called"] == ["calculate"]
    assert event["sources"] == [{"type": "calculation", "id": "2 + 2"}]
    assert isinstance(event["latency_ms"], int)
    assert event["tokens"] == usage(250, 30)
    assert event["thread_id"] == response.json()["thread_id"]

    logged = repr(logs)
    assert API_KEY not in logged
    assert SECRET_MESSAGE not in logged
    assert "123.456.789-00" not in logged


def test_chat_turn_log_without_usage_metadata_reports_zero() -> None:
    graph = build_graph(InMemorySaver(), fake_llm(AIMessage("Olá!")), tools=[])

    with capture_logs() as logs, TestClient(create_app(graph=graph)) as client:
        client.post("/v1/chat", json={"message": "Oi"})

    [event] = [e for e in logs if e["event"] == "chat_turn"]
    assert event["tokens"] == usage(0, 0)
