"""Montagem do grafo.

START → guardrail ─┬─ in_scope     → agent ⇄ tools → collect_sources → enforce_grounding
                   │                 → verify_grounding → add_advice_disclaimer → END
                   ├─ out_of_scope → refuse → END
                   └─ ambiguous    → clarify → END

Entre o agent e as tools, `quote_guard` devolve ao agent, sem executar, a rodada que calcula
com a cotação de um turno anterior.
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
from financial_agent.graph.nodes.disclaimer import add_advice_disclaimer
from financial_agent.graph.nodes.grounding import enforce_grounding
from financial_agent.graph.nodes.guardrail import GuardrailNode, route_after_guardrail
from financial_agent.graph.nodes.quote_guard import guard_stale_quotes, route_after_quote_guard
from financial_agent.graph.nodes.refuse import refuse
from financial_agent.graph.nodes.verify import VerifierNode
from financial_agent.graph.state import GraphState

# Usado no config de cada invocação. Cada nó executado gasta um passo: guardrail, resposta final
# do agent, collect_sources, enforce_grounding, verify_grounding e add_advice_disclaimer (6), mais
# 3 por rodada agent → quote_guard → tools. O laço já é limitado por MAX_TOOL_ROUNDS; a folga de
# 4 passos é só uma rede de segurança.
RECURSION_LIMIT = 6 + 3 * MAX_TOOL_ROUNDS + 4


def _skip(state: GraphState) -> dict[str, Any]:
    return {}


def build_graph(
    checkpointer: BaseCheckpointSaver[Any],
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    guardrail: GuardrailNode | None = None,
    verifier: VerifierNode | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compila o grafo do agente.

    Com `guardrail`, toda mensagem é classificada antes de chegar ao agente. Sem ele (testes do
    laço do agente), o grafo começa direto no `agent`. Com `verifier`, as respostas que citam
    documentos passam por `verify_grounding`; sem ele, o nó deixa tudo passar.
    """
    builder = StateGraph(GraphState)
    builder.add_node("agent", make_agent_node(llm, tools))
    builder.add_node("quote_guard", guard_stale_quotes)
    builder.add_node("tools", ToolNode(list(tools)))
    builder.add_node("collect_sources", collect_sources)
    builder.add_node("enforce_grounding", enforce_grounding)
    builder.add_node("verify_grounding", verifier or _skip)
    builder.add_node("add_advice_disclaimer", add_advice_disclaimer)

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
        "agent", tools_condition, {"tools": "quote_guard", END: "collect_sources"}
    )
    builder.add_conditional_edges(
        "quote_guard", route_after_quote_guard, {"tools": "tools", "agent": "agent"}
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("collect_sources", "enforce_grounding")
    builder.add_edge("enforce_grounding", "verify_grounding")
    builder.add_edge("verify_grounding", "add_advice_disclaimer")
    builder.add_edge("add_advice_disclaimer", END)

    return builder.compile(checkpointer=checkpointer)
