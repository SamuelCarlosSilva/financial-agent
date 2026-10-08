"""Pedido de esclarecimento para mensagens ambíguas, sem LLM nem ferramentas."""

from typing import Any

from langchain_core.messages import AIMessage

from financial_agent.graph.prompts import CLARIFY_MESSAGE
from financial_agent.graph.state import GraphState, history_metadata


def clarify(state: GraphState) -> dict[str, Any]:
    return {"messages": [AIMessage(CLARIFY_MESSAGE, additional_kwargs=history_metadata())]}
