"""Rotas HTTP. A camada só traduz HTTP ↔ invocação do grafo por `thread_id` (Princípio IV)."""

import time
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from financial_agent.api.schemas import ChatRequest, ChatResponse, Health, ScopeLabel
from financial_agent.api.security import require_api_key
from financial_agent.graph.builder import RECURSION_LIMIT
from financial_agent.graph.state import SourceCitation
from financial_agent.logging import get_logger, request_id_var

log = get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=Health, responses={503: {"model": Health}})
async def health(request: Request) -> JSONResponse:
    database_ok = await request.app.state.ping()
    if database_ok:
        body = Health(status="ok", database="ok")
        return JSONResponse(status_code=200, content=body.model_dump())
    body = Health(status="degraded", database="unavailable")
    return JSONResponse(status_code=503, content=body.model_dump())


def _current_turn(messages: Sequence[BaseMessage]) -> Sequence[BaseMessage]:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index + 1 :]
    return messages


def _source_ref(source: SourceCitation) -> dict[str, str]:
    if source.type == "document":
        return {"type": source.type, "id": source.document_id}
    if source.type == "fx_quote":
        return {"type": source.type, "id": source.pair}
    return {"type": source.type, "id": source.expression}


@router.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    graph = request.app.state.graph
    thread_id = body.thread_id or uuid4()
    started = time.perf_counter()

    state: dict[str, Any] = await graph.ainvoke(
        {"messages": [HumanMessage(body.message)], "turn_sources": []},
        config={"configurable": {"thread_id": str(thread_id)}, "recursion_limit": RECURSION_LIMIT},
    )

    turn = _current_turn(state["messages"])
    final = next((m for m in reversed(turn) if isinstance(m, AIMessage)), None)
    answer = final.text if final is not None else ""
    scope_decision = state.get("scope")
    # Grafos sem guardrail (testes do laço do agente) tratam todo turno como em escopo.
    scope: ScopeLabel = scope_decision.label if scope_decision is not None else "in_scope"
    sources: list[SourceCitation] = state.get("turn_sources") or []

    tools_called = [call["name"] for m in turn if isinstance(m, AIMessage) for call in m.tool_calls]
    log.info(
        "chat_turn",
        thread_id=str(thread_id),
        request_id=request_id_var.get(),
        scope_label=scope,
        scope_reason=scope_decision.reason if scope_decision is not None else None,
        tools_called=tools_called,
        sources=[_source_ref(source) for source in sources],
        latency_ms=round((time.perf_counter() - started) * 1000),
    )

    return ChatResponse(thread_id=thread_id, answer=answer, scope=scope, sources=sources)
