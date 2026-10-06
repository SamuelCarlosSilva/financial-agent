"""Recusa de escopo: mensagem padrão, sem LLM nem ferramentas."""

from typing import Any

from langchain_core.messages import AIMessage

from financial_agent.graph.prompts import OUT_OF_SCOPE_MESSAGE
from financial_agent.graph.state import GraphState


def refuse(state: GraphState) -> dict[str, Any]:
    return {"messages": [AIMessage(OUT_OF_SCOPE_MESSAGE)]}
