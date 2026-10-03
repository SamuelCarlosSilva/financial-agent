"""Nó do agente (LLM com ferramentas) e coleta das fontes do turno."""

from collections.abc import Sequence
from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, TypeAdapter

from financial_agent.graph.prompts import AGENT_SYSTEM_PROMPT
from financial_agent.graph.state import GraphState, SourceCitation

_source_adapter: TypeAdapter[SourceCitation] = TypeAdapter(SourceCitation)


class AgentNode(Protocol):
    async def __call__(self, state: GraphState) -> dict[str, Any]: ...


def make_agent_node(llm: BaseChatModel, tools: Sequence[BaseTool]) -> AgentNode:
    model = llm.bind_tools(list(tools)) if tools else llm

    async def agent(state: GraphState) -> dict[str, Any]:
        messages = [SystemMessage(AGENT_SYSTEM_PROMPT), *state["messages"]]
        response = await model.ainvoke(messages)
        return {"messages": [response]}

    return agent


def _current_turn(messages: Sequence[BaseMessage]) -> Sequence[BaseMessage]:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index + 1 :]
    return messages


def _to_sources(artifact: Any) -> list[SourceCitation]:
    if artifact is None:
        return []
    items = artifact if isinstance(artifact, list) else [artifact]
    sources: list[SourceCitation] = []
    for item in items:
        if isinstance(item, BaseModel):
            item = item.model_dump()
        sources.append(_source_adapter.validate_python(item))
    return sources


def collect_sources(state: GraphState) -> dict[str, Any]:
    """Junta em `turn_sources` os artefatos dos `ToolMessage`s do turno atual."""
    sources: list[SourceCitation] = []
    for message in _current_turn(state["messages"]):
        if isinstance(message, ToolMessage):
            sources.extend(_to_sources(message.artifact))
    return {"turn_sources": sources}
