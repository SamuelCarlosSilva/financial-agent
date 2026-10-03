"""Checkpoint da Fase 2: o estado do chat fica salvo no Postgres por `thread_id`."""

from langchain_core.messages import AIMessage, HumanMessage

from financial_agent.api import db
from financial_agent.graph.builder import RECURSION_LIMIT, build_graph
from tests.fakes import fake_llm


async def test_state_survives_new_pool_and_graph(postgres_url: str) -> None:
    config = {"configurable": {"thread_id": "thread-persist"}, "recursion_limit": RECURSION_LIMIT}

    pool = await db.open_pool(postgres_url, max_size=2)
    try:
        assert await db.ping(pool)
        checkpointer = await db.setup_checkpointer(pool)
        graph = build_graph(checkpointer, fake_llm(AIMessage("primeira")), tools=[])
        await graph.ainvoke({"messages": [HumanMessage("oi")], "turn_sources": []}, config)
    finally:
        await pool.close()

    # Simula um reinício: pool, checkpointer e grafo novos.
    pool = await db.open_pool(postgres_url, max_size=2)
    try:
        llm = fake_llm(AIMessage("segunda"))
        graph = build_graph(await db.setup_checkpointer(pool), llm, tools=[])
        state = await graph.ainvoke(
            {"messages": [HumanMessage("e agora?")], "turn_sources": []}, config
        )
    finally:
        await pool.close()

    assert [m.content for m in state["messages"]] == ["oi", "primeira", "e agora?", "segunda"]
    assert [m.content for m in llm.calls[0][1:]] == ["oi", "primeira", "e agora?"]
