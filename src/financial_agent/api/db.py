"""Bootstrap do Postgres: pool de conexões, checkpointer do LangGraph, metadata e ping."""

from importlib.resources import files
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

Pool = AsyncConnectionPool[AsyncConnection[DictRow]]


async def open_pool(database_url: str, max_size: int = 20) -> Pool:
    # autocommit/prepare_threshold/dict_row são exigidos pelo AsyncPostgresSaver.
    kwargs: dict[str, Any] = {"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}
    pool: Pool = AsyncConnectionPool(
        database_url,
        connection_class=AsyncConnection[DictRow],
        kwargs=kwargs,
        min_size=1,
        max_size=max_size,
        open=False,
    )
    await pool.open(wait=True)
    return pool


async def setup_checkpointer(pool: Pool) -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    return checkpointer


async def setup_thread_metadata(pool: Pool) -> None:
    sql = files("financial_agent.api").joinpath("sql/thread_metadata.sql").read_text("utf-8")
    async with pool.connection() as conn:
        # Vários comandos no mesmo script: não pode virar prepared statement.
        await conn.execute(sql, prepare=False)


async def ping(pool: Pool) -> bool:
    try:
        async with pool.connection(timeout=5) as conn:
            await conn.execute("SELECT 1")
    except Exception:
        return False
    return True
