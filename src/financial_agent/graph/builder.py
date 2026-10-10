"""Montagem do grafo.

START → guardrail ─┬─ in_scope     → agent ⇄ tools → collect_sources → enforce_grounding → END
                   ├─ out_of_scope → refuse → END
                   └─ ambiguous    → clarify → END
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from financial_agent.graph.nodes.agent import MAX_TOOL_ROUNDS, collect_sources, make_agent_node
from financial_agent.graph.nodes.clarify import clarify
from financial_agent.graph.nodes.grounding import enforce_grounding
from financial_agent.graph.nodes.guardrail import GuardrailNode, route_after_guardrail
from financial_agent.graph.nodes.refuse import refuse
from financial_agent.graph.state import GraphState

# Usado no config de cada invocação. Cada nó executado gasta um passo: guardrail, resposta final
# do agent, collect_sources e enforce_grounding (4), mais 2 por rodada agent → tools. O laço já é
# limitado por MAX_TOOL_ROUNDS; a folga de 4 passos é só uma rede de segurança.
RECURSION_LIMIT = 4 + 2 * MAX_TOOL_ROUNDS + 4


def build_graph(
    checkpointer: BaseCheckpointSaver[Any],
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    guardrail: GuardrailNode | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compila o grafo do agente.

    Com `guardrail`, toda mensagem é classificada antes de chegar ao agente. Sem ele (testes do
    laço do agente), o grafo começa direto no `agent`.
    """
    builder = StateGraph(GraphState)
    builder.add_node("agent", make_agent_node(llm, tools))
    builder.add_node("tools", ToolNode(list(tools)))
    builder.add_node("collect_sources", collect_sources)
    builder.add_node("enforce_grounding", enforce_grounding)

    if guardrail is None:
        builder.add_edge(START, "agent")
    else:
        builder.add_node("guardrail", guardrail)
        builder.add_node("refuse", refuse)
        builder.add_node("clarify", clarify)
        builder.add_edge(START, "guardrail")
        builder.add_conditional_edges(
            "guardrail",
            route_after_guardrail,
            {"agent": "agent", "refuse": "refuse", "clarify": "clarify"},
        )
        builder.add_edge("refuse", END)
        builder.add_edge("clarify", END)

    builder.add_conditional_edges(
        "agent", tools_condition, {"tools": "tools", END: "collect_sources"}
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("collect_sources", "enforce_grounding")
    builder.add_edge("enforce_grounding", END)

    return builder.compile(checkpointer=checkpointer)
