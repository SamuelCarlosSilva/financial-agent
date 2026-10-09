"""Aplicação FastAPI: lifespan (pool, checkpointer, grafo compilado) e middlewares."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request, Response
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph

from financial_agent.api import db
from financial_agent.api.errors import register_error_handlers
from financial_agent.api.routes import router
from financial_agent.api.threads import InMemoryThreadStore, PostgresThreadStore, ThreadStore
from financial_agent.config import get_settings
from financial_agent.graph.builder import build_graph
from financial_agent.graph.nodes.guardrail import make_guardrail_node
from financial_agent.logging import configure_logging, request_id_var
from financial_agent.rag.vectorstore import close_vectorstore, get_embeddings, get_vectorstore
from financial_agent.tools import get_tools

PingFn = Callable[[], Awaitable[bool]]


async def _always_ok() -> bool:
    return True


@asynccontextmanager
async def _production_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    pool = await db.open_pool(settings.DATABASE_URL)
    vectorstore = get_vectorstore(settings, get_embeddings(settings))
    # Cliente HTTP compartilhado pelas ferramentas (cotação de moedas).
    http_client = httpx.AsyncClient(timeout=settings.FX_TIMEOUT_SECONDS)
    try:
        checkpointer = await db.setup_checkpointer(pool)
        await db.setup_thread_metadata(pool)
        app.state.threads = PostgresThreadStore(pool)
        llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=0,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            api_key=settings.OPENAI_API_KEY,
        )
        guardrail_llm = ChatOpenAI(
            model=settings.GUARDRAIL_MODEL,
            temperature=0,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            api_key=settings.OPENAI_API_KEY,
        )
        tools = get_tools(settings, vectorstore, http_client)
        # Compilado uma única vez; o estado da conversa vive só no checkpointer.
        app.state.graph = build_graph(
            checkpointer, llm, tools, guardrail=make_guardrail_node(guardrail_llm)
        )

        async def ping() -> bool:
            return await db.ping(pool)

        app.state.ping = ping
        yield
    finally:
        await http_client.aclose()
        await close_vectorstore(vectorstore)
        await pool.close()


def create_app(
    graph: CompiledStateGraph[Any, Any, Any, Any] | None = None,
    ping: PingFn | None = None,
    threads: ThreadStore | None = None,
) -> FastAPI:
    """Cria a aplicação.

    Com `graph` (modo de teste), o lifespan não abre pool nem checkpointer, o `/health` usa
    o `ping` injetado (por padrão, sempre "ok") e as threads ficam no registro injetado (por
    padrão, em memória).
    """
    if graph is None:
        lifespan = _production_lifespan
    else:

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            app.state.graph = graph
            app.state.ping = ping or _always_ok
            app.state.threads = threads or InMemoryThreadStore()
            yield

    app = FastAPI(title="Financial Agent API", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    register_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
