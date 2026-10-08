"""`GET /v1/threads/{id}/messages` responde conforme contracts/openapi.yaml (FR-016)."""

from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.graph.builder import build_graph
from financial_agent.graph.state import CalculationSource
from tests.contract.test_openapi_contract import assert_matches, spec  # noqa: F401
from tests.fakes import fake_llm


@tool(response_format="content_and_artifact")
def fake_calc(expression: str) -> tuple[str, CalculationSource]:
    """Calculadora falsa para os testes."""
    return f"{expression} = 4.00", CalculationSource(expression=expression, result=Decimal("4"))


CALL = {"name": "fake_calc", "args": {"expression": "2 + 2"}, "id": "c1"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    llm = fake_llm(
        AIMessage("", tool_calls=[CALL]),
        AIMessage("2 + 2 = 4.00"),
        AIMessage("De nada!"),
    )
    graph = build_graph(InMemorySaver(), llm, tools=[fake_calc])
    with TestClient(create_app(graph=graph)) as test_client:
        yield test_client


def test_history_matches_contract(client: TestClient, spec: dict[str, Any]) -> None:  # noqa: F811
    first = client.post("/v1/chat", json={"message": "Quanto é 2+2?"}).json()
    thread_id = first["thread_id"]
    client.post("/v1/chat", json={"message": "Obrigado", "thread_id": thread_id})

    response = client.get(f"/v1/threads/{thread_id}/messages")

    assert response.status_code == 200
    body = response.json()
    assert_matches(spec, "ThreadHistory", body)
    assert body["thread_id"] == thread_id
    messages = body["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "Quanto é 2+2?"),
        ("assistant", "2 + 2 = 4.00"),
        ("user", "Obrigado"),
        ("assistant", "De nada!"),
    ]
    assert messages[1]["sources"] == [{"type": "calculation", "expression": "2 + 2", "result": "4"}]
    assert messages[3]["sources"] == []
    assert "sources" not in messages[0]
    timestamps = [m["created_at"] for m in messages]
    assert timestamps == sorted(timestamps)


def test_unknown_thread_returns_404(client: TestClient, spec: dict[str, Any]) -> None:  # noqa: F811
    response = client.get(f"/v1/threads/{uuid4()}/messages")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert_matches(spec, "Error", response.json())


def test_invalid_thread_id_returns_422(client: TestClient, spec: dict[str, Any]) -> None:  # noqa: F811
    response = client.get("/v1/threads/abc/messages")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert_matches(spec, "Error", response.json())
