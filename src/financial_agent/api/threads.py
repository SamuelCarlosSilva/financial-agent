"""Registro das threads (`thread_metadata`): existência e última atividade, para a retenção."""

from typing import Protocol

from financial_agent.api.db import Pool


async def touch_thread(pool: Pool, thread_id: str) -> None:
    """Cria a thread se não existir e atualiza `last_activity_at`."""
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO thread_metadata (thread_id) VALUES (%s) "
            "ON CONFLICT (thread_id) DO UPDATE SET last_activity_at = now()",
            (thread_id,),
        )


async def thread_exists(pool: Pool, thread_id: str) -> bool:
    async with pool.connection() as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM thread_metadata WHERE thread_id = %s", (thread_id,)
        )
        return await cursor.fetchone() is not None


class ThreadStore(Protocol):
    async def touch(self, thread_id: str) -> None: ...

    async def exists(self, thread_id: str) -> bool: ...


class PostgresThreadStore:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def touch(self, thread_id: str) -> None:
        await touch_thread(self._pool, thread_id)

    async def exists(self, thread_id: str) -> bool:
        return await thread_exists(self._pool, thread_id)


class InMemoryThreadStore:
    """Registro do modo de teste (`create_app(graph=...)`), sem banco."""

    def __init__(self) -> None:
        self._threads: set[str] = set()

    async def touch(self, thread_id: str) -> None:
        self._threads.add(thread_id)

    async def exists(self, thread_id: str) -> bool:
        return thread_id in self._threads
