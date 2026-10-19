"""A API responde conforme contracts/openapi.yaml (FR-011)."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from financial_agent.api.app import create_app
from financial_agent.graph.builder import build_graph
from tests.conftest import DEFAULT_ANSWER
from tests.fakes import FakeToolChatModel

CONTRACT = Path(__file__).parents[2] / "specs/001-financial-assistant-api/contracts/openapi.yaml"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    with CONTRACT.open(encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)
    return loaded


def assert_matches(spec: dict[str, Any], schema_name: str, payload: Any) -> None:
    schema = {"$ref": f"#/components/schemas/{schema_name}", "components": spec["components"]}
    Draft202012Validator(schema).validate(payload)


def test_health_matches_contract(app_client: TestClient, spec: dict[str, Any]) -> None:
    response = app_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert_matches(spec, "Health", response.json())


def test_health_degraded_when_database_down(
    fake_llm: FakeToolChatModel, checkpointer: Any, spec: dict[str, Any]
) -> None:
    async def db_down() -> bool:
        return False

    app = create_app(graph=build_graph(checkpointer, fake_llm, tools=[]), ping=db_down)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
    assert_matches(spec, "Health", response.json())


def test_chat_new_thread_matches_contract(app_client: TestClient, spec: dict[str, Any]) -> None:
    response = app_client.post("/v1/chat", json={"message": "Quanto está o dólar?"})

    assert response.status_code == 200
    body = response.json()
    assert_matches(spec, "ChatResponse", body)
    assert body["answer"] == DEFAULT_ANSWER
    assert body["scope"] == "in_scope"
    assert body["sources"] == []
    assert response.headers["X-Request-ID"]


def test_chat_request_example_starts_a_new_thread(app_client: TestClient) -> None:
    # Sem isso, o Swagger manda o mesmo UUID de exemplo em todo teste feito pelo /docs.
    schema = app_client.get("/openapi.json").json()["components"]["schemas"]["ChatRequest"]

    assert schema["examples"] == [{"message": "O que é come-cotas?"}]
    assert schema["properties"]["thread_id"]["examples"] == [None]


def test_chat_keeps_given_thread_id(app_client: TestClient, spec: dict[str, Any]) -> None:
    thread_id = "3f6c2a3e-8a1b-4a53-9d7a-2f1d0c1b9e10"

    response = app_client.post("/v1/chat", json={"message": "E o euro?", "thread_id": thread_id})

    assert response.status_code == 200
    assert response.json()["thread_id"] == thread_id
    assert_matches(spec, "ChatResponse", response.json())


@pytest.mark.parametrize(
    "payload",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "a" * 4001},
        {"message": "oi", "thread_id": "abc"},
        {"message": "oi", "extra": 1},
        {},
    ],
    ids=["empty", "blank", "too-long", "bad-thread-id", "extra-field", "missing-message"],
)
def test_chat_rejects_invalid_input(
    app_client: TestClient, spec: dict[str, Any], payload: dict[str, Any]
) -> None:
    response = app_client.post("/v1/chat", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert_matches(spec, "Error", body)
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_chat_requires_api_key_when_configured(
    app_client: TestClient, spec: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from financial_agent.config import get_settings

    monkeypatch.setenv("API_KEYS", "chave-a, chave-b")
    get_settings.cache_clear()

    missing = app_client.post("/v1/chat", json={"message": "oi"})
    wrong = app_client.post("/v1/chat", json={"message": "oi"}, headers={"X-API-Key": "x"})
    ok = app_client.post("/v1/chat", json={"message": "oi"}, headers={"X-API-Key": "chave-b"})
    health = app_client.get("/health")

    assert missing.status_code == wrong.status_code == 401
    assert_matches(spec, "Error", missing.json())
    assert missing.json()["error"]["code"] == "unauthorized"
    assert ok.status_code == 200
    assert health.status_code == 200
