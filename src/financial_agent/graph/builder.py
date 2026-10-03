"""Montagem do grafo: START → agent ⇄ tools → collect_sources → END."""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from financial_agent.graph.nodes.agent import collect_sources, make_agent_node
from financial_agent.graph.state import GraphState

# Usado no config de cada invocação (agent ⇄ tools não pode girar indefinidamente).
RECURSION_LIMIT = 12


def build_graph(
    checkpointer: BaseCheckpointSaver[Any],
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    guardrail: Any | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compila o grafo do agente.

    `guardrail` é o gancho que a US2 conecta como primeiro nó; até lá, é ignorado.
    """
    builder = StateGraph(GraphState)
    builder.add_node("agent", make_agent_node(llm, tools))
    builder.add_node("tools", ToolNode(list(tools)))
    builder.add_node("collect_sources", collect_sources)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent", tools_condition, {"tools": "tools", END: "collect_sources"}
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("collect_sources", END)

    return builder.compile(checkpointer=checkpointer)
