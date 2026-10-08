"""Memória por thread no Postgres real: continuidade, isolamento e reinício (US5)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx
from langchain_core.messages import AIMessage

from financial_agent.api import db
from financial_agent.api.app import create_app
from financial_agent.api.threads import PostgresThreadStore
from financial_agent.graph.builder import build_graph
from tests.fakes import FakeToolChatModel, fake_llm


@asynccontextmanager
async def running_app(
    postgres_url: str, llm: FakeToolChatModel
) -> AsyncIterator[httpx.AsyncClient]:
    """Sobe a API com pool, checkpointer e grafo novos, como em um reinício do serviço."""
    pool = await db.open_pool(postgres_url, max_size=2)
    try:
        checkpointer = await db.setup_checkpointer(pool)
        await db.setup_thread_metadata(pool)
        graph = build_graph(checkpointer, llm, tools=[])
        app = create_app(graph=graph, threads=PostgresThreadStore(pool))
        transport = httpx.ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            yield client
    finally:
        await pool.close()


def llm_input(llm: FakeToolChatModel, call: int) -> list[str]:
    """Conteúdo enviado ao LLM, sem o system prompt."""
    return [str(m.content) for m in llm.calls[call][1:]]


async def test_same_thread_keeps_context_and_other_thread_is_isolated(postgres_url: str) -> None:
    llm = fake_llm(AIMessage("r1"), AIMessage("r2"), AIMessage("r3"))
    async with running_app(postgres_url, llm) as client:
        first = (await client.post("/v1/chat", json={"message": "Quanto está o dólar?"})).json()
        thread_id = first["thread_id"]
        await client.post("/v1/chat", json={"message": "E o euro?", "thread_id": thread_id})
        await client.post("/v1/chat", json={"message": "E o euro?", "thread_id": str(uuid4())})

    assert llm_input(llm, 1) == ["Quanto está o dólar?", "r1", "E o euro?"]
    assert llm_input(llm, 2) == ["E o euro?"]


async def test_history_survives_restart(postgres_url: str) -> None:
    async with running_app(postgres_url, fake_llm(AIMessage("primeira"))) as client:
        thread_id = (await client.post("/v1/chat", json={"message": "oi"})).json()["thread_id"]

    llm = fake_llm(AIMessage("segunda"))
    async with running_app(postgres_url, llm) as client:
        await client.post("/v1/chat", json={"message": "e agora?", "thread_id": thread_id})
        history = (await client.get(f"/v1/threads/{thread_id}/messages")).json()

    assert llm_input(llm, 0) == ["oi", "primeira", "e agora?"]
    assert [m["content"] for m in history["messages"]] == ["oi", "primeira", "e agora?", "segunda"]


async def test_request_without_thread_id_gets_new_uuid(postgres_url: str) -> None:
    async with running_app(postgres_url, fake_llm(AIMessage("a"), AIMessage("b"))) as client:
        first = (await client.post("/v1/chat", json={"message": "oi"})).json()
        second = (await client.post("/v1/chat", json={"message": "oi"})).json()

    assert UUID(first["thread_id"]) != UUID(second["thread_id"])


async def test_unknown_uuid_creates_thread_with_that_id(postgres_url: str) -> None:
    thread_id = str(uuid4())
    async with running_app(postgres_url, fake_llm(AIMessage("criada"))) as client:
        before = await client.get(f"/v1/threads/{thread_id}/messages")
        response = await client.post("/v1/chat", json={"message": "oi", "thread_id": thread_id})
        after = await client.get(f"/v1/threads/{thread_id}/messages")

    assert before.status_code == 404
    assert response.json()["thread_id"] == thread_id
    assert after.status_code == 200
    assert [(m["role"], m["content"]) for m in after.json()["messages"]] == [
        ("user", "oi"),
        ("assistant", "criada"),
    ]
