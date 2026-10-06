"""Guardrail de escopo: roteamento, recusa e esclarecimento antes de qualquer ferramenta."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.graph.builder import RECURSION_LIMIT, build_graph
from financial_agent.graph.nodes.guardrail import make_guardrail_node, route_after_guardrail
from financial_agent.graph.prompts import CLARIFY_MESSAGE, OUT_OF_SCOPE_MESSAGE
from financial_agent.graph.state import CalculationSource, ScopeDecision
from tests.fakes import FakeToolChatModel, fake_guardrail, fake_llm


@tool(response_format="content_and_artifact")
def fake_calc(expression: str) -> tuple[str, CalculationSource]:
    """Calculadora falsa para os testes."""
    return f"{expression} = 4.00", CalculationSource(expression=expression, result=Decimal("4"))


CALL = {"name": "fake_calc", "args": {"expression": "2 + 2"}, "id": "c1"}


def decision(label: str) -> ScopeDecision:
    return ScopeDecision(label=label, reason="teste")  # type: ignore[arg-type]


def agent_llm() -> FakeToolChatModel:
    return fake_llm(AIMessage("", tool_calls=[CALL]), AIMessage("2 + 2 = 4.00"))


async def run(guardrail_decision: ScopeDecision | Exception, llm: FakeToolChatModel) -> Any:
    guardrail = make_guardrail_node(fake_guardrail(guardrail_decision))
    graph = build_graph(InMemorySaver(), llm, tools=[fake_calc], guardrail=guardrail)
    return await graph.ainvoke(
        {"messages": [HumanMessage("Pergunta")], "turn_sources": []},
        config={"configurable": {"thread_id": "t1"}, "recursion_limit": RECURSION_LIMIT},
    )


async def test_in_scope_goes_to_agent() -> None:
    llm = agent_llm()

    state = await run(decision("in_scope"), llm)

    assert state["scope"].label == "in_scope"
    assert state["messages"][-1].content == "2 + 2 = 4.00"
    assert len(llm.calls) == 2
    assert [s.type for s in state["turn_sources"]] == ["calculation"]


async def test_out_of_scope_is_refused_without_tools() -> None:
    llm = agent_llm()

    state = await run(decision("out_of_scope"), llm)

    assert state["scope"].label == "out_of_scope"
    assert state["messages"][-1].content == OUT_OF_SCOPE_MESSAGE
    assert not any(isinstance(m, ToolMessage) for m in state["messages"])
    assert llm.calls == []
    assert state["turn_sources"] == []


async def test_ambiguous_asks_for_clarification() -> None:
    llm = agent_llm()

    state = await run(decision("ambiguous"), llm)

    assert state["scope"].label == "ambiguous"
    assert state["messages"][-1].content == CLARIFY_MESSAGE
    assert llm.calls == []


async def test_classifier_failure_falls_back_to_out_of_scope() -> None:
    llm = agent_llm()

    state = await run(TimeoutError("openai"), llm)

    assert state["scope"] == ScopeDecision(label="out_of_scope", reason="guardrail_error")
    assert state["messages"][-1].content == OUT_OF_SCOPE_MESSAGE
    assert llm.calls == []


@pytest.mark.parametrize(
    ("label", "route"),
    [("in_scope", "agent"), ("out_of_scope", "refuse"), ("ambiguous", "clarify")],
)
def test_route_after_guardrail(label: str, route: str) -> None:
    state = {"messages": [], "scope": decision(label), "turn_sources": []}

    assert route_after_guardrail(state) == route  # type: ignore[arg-type]


def test_route_without_decision_refuses() -> None:
    state = {"messages": [], "scope": None, "turn_sources": []}

    assert route_after_guardrail(state) == "refuse"  # type: ignore[arg-type]


def test_chat_endpoint_reports_refusal() -> None:
    guardrail = make_guardrail_node(fake_guardrail(decision("out_of_scope")))
    graph = build_graph(InMemorySaver(), agent_llm(), tools=[fake_calc], guardrail=guardrail)

    with TestClient(create_app(graph=graph)) as client:
        response = client.post("/v1/chat", json={"message": "Me dá uma receita de bolo"})

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "out_of_scope"
    assert body["answer"] == OUT_OF_SCOPE_MESSAGE
    assert body["sources"] == []
