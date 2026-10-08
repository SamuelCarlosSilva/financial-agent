"""Expurgo das threads inativas: `python -m financial_agent.maintenance.purge_threads`.

Remove checkpoints e `thread_metadata` das threads sem atividade há mais de
`THREAD_RETENTION_DAYS` dias. Agendar diariamente, por exemplo com cron:

    0 3 * * * docker compose --profile maintenance run --rm purge
"""

import asyncio
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from financial_agent.api import db
from financial_agent.config import get_settings
from financial_agent.logging import configure_logging, get_logger

log = get_logger(__name__)


async def purge_threads(
    pool: db.Pool, checkpointer: BaseCheckpointSaver[Any], retention_days: int
) -> int:
    """Remove as threads inativas e devolve quantas foram removidas.

    Os checkpoints saem antes da metadata: se a execução falhar no meio, as threads continuam
    selecionáveis e a próxima execução termina o trabalho.
    """
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT thread_id FROM thread_metadata "
            "WHERE last_activity_at < now() - make_interval(days => %s)",
            (retention_days,),
        )
        thread_ids = [row["thread_id"] for row in await cursor.fetchall()]

    for thread_id in thread_ids:
        await checkpointer.adelete_thread(thread_id)

    if thread_ids:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM thread_metadata WHERE thread_id = ANY(%s)", (thread_ids,)
            )
    return len(thread_ids)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    pool = await db.open_pool(settings.DATABASE_URL, max_size=2)
    try:
        checkpointer = await db.setup_checkpointer(pool)
        await db.setup_thread_metadata(pool)
        purged = await purge_threads(pool, checkpointer, settings.THREAD_RETENTION_DAYS)
        log.info("threads_purged", count=purged, retention_days=settings.THREAD_RETENTION_DAYS)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
