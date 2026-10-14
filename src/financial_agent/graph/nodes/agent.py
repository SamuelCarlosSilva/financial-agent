"""Nó do agente (LLM com ferramentas) e coleta das fontes do turno."""

import re
from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, TypeAdapter

from financial_agent.graph.prompts import AGENT_SYSTEM_PROMPT
from financial_agent.graph.state import GraphState, SourceCitation, history_metadata

_source_adapter: TypeAdapter[SourceCitation] = TypeAdapter(SourceCitation)

# Trechos de documento chegam como "[n] título (origem)" (tools/document_search.py) e o agente
# os cita como [n], [n, m] ou [n; m] na resposta.
_FIRST_MARKER = re.compile(r"^\[(\d+)\] ")
_CITATION = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")

# Rodadas agent → tools por turno. Na última chamada as ferramentas ficam desligadas
# (`tool_choice="none"`) e o agente responde com o que já coletou, então o laço sempre termina.
MAX_TOOL_ROUNDS = 4


class AgentNode(Protocol):
    async def __call__(self, state: GraphState) -> dict[str, Any]: ...


def make_agent_node(llm: BaseChatModel, tools: Sequence[BaseTool]) -> AgentNode:
    model = llm.bind_tools(list(tools)) if tools else llm
    final_model = llm.bind_tools(list(tools), tool_choice="none") if tools else llm

    async def agent(state: GraphState) -> dict[str, Any]:
        messages = [SystemMessage(AGENT_SYSTEM_PROMPT), *agent_view(state["messages"])]
        rounds = sum(
            1 for m in current_turn(state["messages"]) if isinstance(m, AIMessage) and m.tool_calls
        )
        chosen = final_model if rounds >= MAX_TOOL_ROUNDS else model
        response = await chosen.ainvoke(messages)
        return {"messages": [response]}

    return agent


def agent_view(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    """O que o agente vê: a conversa visível dos turnos anteriores e o turno atual inteiro.

    Chamadas e resultados de ferramentas de turnos anteriores ficam de fora. Assim cada
    resposta se apoia em ferramentas chamadas no próprio turno e sai com as fontes dele
    (Princípio I), em vez de reaproveitar uma cotação ou um trecho antigo sem citá-lo.
    """
    turn = current_turn(messages)
    earlier = messages[: len(messages) - len(turn)]
    visible = [
        m
        for m in earlier
        if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and not m.tool_calls)
    ]
    return [*visible, *turn]


def current_turn(messages: Sequence[BaseMessage]) -> Sequence[BaseMessage]:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index + 1 :]
    return messages


def to_sources(artifact: Any) -> list[SourceCitation]:
    if artifact is None:
        return []
    items = artifact if isinstance(artifact, list) else [artifact]
    sources: list[SourceCitation] = []
    for item in items:
        if isinstance(item, BaseModel):
            item = item.model_dump()
        sources.append(_source_adapter.validate_python(item))
    return sources


def cited_markers(text: str) -> set[int]:
    return {int(n) for group in _CITATION.findall(text) for n in re.split(r"\s*[,;]\s*", group)}


def collect_sources(state: GraphState) -> dict[str, Any]:
    """Junta em `turn_sources` os artefatos dos `ToolMessage`s do turno atual.

    Trechos de documento só entram se a resposta final citar o número deles: a busca pode
    trazer trechos parecidos que não respondem à pergunta, e esses não são fontes. As fontes e o
    horário também vão para a resposta final, que é o que o histórico da thread expõe.
    """
    turn = current_turn(state["messages"])
    final = next((m for m in reversed(turn) if isinstance(m, AIMessage)), None)
    cited = cited_markers(final.text) if final is not None else set()

    sources: list[SourceCitation] = []
    for message in turn:
        if not isinstance(message, ToolMessage):
            continue
        match = _FIRST_MARKER.match(message.text)
        first = int(match.group(1)) if match else None
        for offset, source in enumerate(to_sources(message.artifact)):
            if source.type == "document" and (first is None or first + offset not in cited):
                continue
            sources.append(source)

    update: dict[str, Any] = {"turn_sources": sources}
    if final is not None:
        # Mesmo id: o reducer `add_messages` substitui a resposta em vez de acrescentar outra.
        kwargs = {**final.additional_kwargs, **history_metadata(sources)}
        update["messages"] = [final.model_copy(update={"additional_kwargs": kwargs})]
    return update
