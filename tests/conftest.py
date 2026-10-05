from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.config import get_settings
from financial_agent.graph.builder import build_graph
from tests.fakes import FakeToolChatModel
from tests.fakes import fake_llm as make_fake_llm

DEFAULT_ANSWER = "Resposta de teste do assistente financeiro."


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isola os testes do `.env` local: sem chave real e sem autenticação."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("API_KEYS", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_llm() -> FakeToolChatModel:
    return make_fake_llm(AIMessage(DEFAULT_ANSWER))


@pytest.fixture
def checkpointer() -> InMemorySaver:
    return InMemorySaver()


@pytest.fixture
def app_client(fake_llm: FakeToolChatModel, checkpointer: InMemorySaver) -> Iterator[TestClient]:
    graph = build_graph(checkpointer, fake_llm, tools=[])
    with TestClient(create_app(graph=graph)) as client:
        yield client
