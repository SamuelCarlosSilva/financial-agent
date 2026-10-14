"""Bootstrap do Postgres: pool de conexões, checkpointer do LangGraph, metadata e ping."""

from importlib.resources import files
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from financial_agent.graph.state import (
    CalculationSource,
    DocumentSource,
    FxQuoteSource,
    ScopeDecision,
)

Pool = AsyncConnectionPool[AsyncConnection[DictRow]]

# Tipos do projeto gravados no estado do grafo. Mensagens, `Decimal` e `datetime` já estão na
# lista segura do LangGraph; qualquer outro tipo é bloqueado na leitura do checkpoint.
CHECKPOINT_TYPES = (ScopeDecision, DocumentSource, FxQuoteSource, CalculationSource)


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


def checkpoint_serializer() -> JsonPlusSerializer:
    """Serializador com allowlist explícita: sem ela, o LangGraph aceita qualquer tipo com aviso."""
    return JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)


async def setup_checkpointer(pool: Pool) -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver(pool, serde=checkpoint_serializer())
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
