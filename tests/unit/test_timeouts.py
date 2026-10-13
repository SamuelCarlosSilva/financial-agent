"""Timeouts e quedas de dependências viram 503 no formato do contrato (FR-012)."""

from typing import Any

import httpx
import openai
import psycopg
from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.graph.builder import build_graph
from tests.fakes import FakeToolChatModel


class TimingOutChatModel(FakeToolChatModel):
    """LLM que estoura o `LLM_TIMEOUT_SECONDS`, como o `ChatOpenAI` faz ao exceder o `timeout`."""

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise openai.APITimeoutError(request=request)


class BrokenThreadStore:
    async def touch(self, thread_id: str) -> None:
        raise psycopg.OperationalError("connection refused")


def assert_upstream_unavailable(response: httpx.Response) -> None:
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "upstream_unavailable"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_llm_timeout_returns_503() -> None:
    llm = TimingOutChatModel(responses=[], calls=[], tool_choices=[])
    graph = build_graph(InMemorySaver(), llm, tools=[])

    with TestClient(create_app(graph=graph)) as client:
        response = client.post("/v1/chat", json={"message": "O que é CDB?"})

    assert_upstream_unavailable(response)


def test_database_failure_on_chat_returns_503() -> None:
    llm = TimingOutChatModel(responses=[], calls=[], tool_choices=[])
    graph = build_graph(InMemorySaver(), llm, tools=[])

    with TestClient(create_app(graph=graph, threads=BrokenThreadStore())) as client:  # type: ignore[arg-type]
        response = client.post("/v1/chat", json={"message": "O que é CDB?"})

    assert_upstream_unavailable(response)
    assert llm.calls == []


def test_database_down_makes_health_return_503() -> None:
    async def database_down() -> bool:
        return False

    graph = build_graph(InMemorySaver(), TimingOutChatModel(responses=[]), tools=[])

    with TestClient(create_app(graph=graph, ping=database_down)) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
