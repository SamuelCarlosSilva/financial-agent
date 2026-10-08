"""Expurgo de threads inativas: remove checkpoints e metadata só das antigas (retenção)."""

from langchain_core.messages import AIMessage, HumanMessage

from financial_agent.api import db
from financial_agent.api.threads import thread_exists, touch_thread
from financial_agent.graph.builder import RECURSION_LIMIT, build_graph
from financial_agent.maintenance.purge_threads import purge_threads
from tests.fakes import fake_llm


def config(thread_id: str) -> dict[str, object]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


async def test_purge_removes_only_inactive_threads(postgres_url: str) -> None:
    old, recent = "purge-old", "purge-recent"
    pool = await db.open_pool(postgres_url, max_size=2)
    try:
        checkpointer = await db.setup_checkpointer(pool)
        await db.setup_thread_metadata(pool)
        graph = build_graph(checkpointer, fake_llm(AIMessage("a"), AIMessage("b")), tools=[])
        for thread_id in (old, recent):
            await touch_thread(pool, thread_id)
            await graph.ainvoke(
                {"messages": [HumanMessage("oi")], "turn_sources": []}, config(thread_id)
            )
        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE thread_metadata SET last_activity_at = now() - interval '31 days' "
                "WHERE thread_id = %s",
                (old,),
            )

        purged = await purge_threads(pool, checkpointer, retention_days=30)

        assert purged == 1
        assert await checkpointer.aget_tuple(config(old)) is None
        assert not await thread_exists(pool, old)
        assert await checkpointer.aget_tuple(config(recent)) is not None
        assert await thread_exists(pool, recent)
    finally:
        await pool.close()
