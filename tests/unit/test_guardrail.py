"""Guardrail de escopo: roteamento, recusa e esclarecimento antes de qualquer ferramenta."""

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.api.app import create_app
from financial_agent.errors import UpstreamUnavailableError
from financial_agent.graph.builder import RECURSION_LIMIT, build_graph
from financial_agent.graph.nodes.guardrail import make_guardrail_node, route_after_guardrail
from financial_agent.graph.prompts import (
    ADVICE_DISCLAIMER,
    CLARIFY_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
)
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


async def run(
    guardrail_decision: ScopeDecision | Exception, llm: FakeToolChatModel, advice: bool = False
) -> Any:
    guardrail = make_guardrail_node(fake_guardrail(guardrail_decision, advice=[advice]))
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


async def test_classifier_failure_is_reported_as_unavailable() -> None:
    llm = agent_llm()

    with pytest.raises(UpstreamUnavailableError):
        await run(TimeoutError("openai"), llm)

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


def test_chat_endpoint_reports_classifier_failure_as_unavailable() -> None:
    guardrail = make_guardrail_node(fake_guardrail(TimeoutError("openai")))
    graph = build_graph(InMemorySaver(), agent_llm(), tools=[fake_calc], guardrail=guardrail)

    with TestClient(create_app(graph=graph), raise_server_exceptions=False) as client:
        response = client.post("/v1/chat", json={"message": "Quanto está o dólar?"})

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "upstream_unavailable"
    assert error["message"] == "Serviço temporariamente indisponível."


async def test_advice_request_gets_disclaimer_when_agent_omits_it() -> None:
    state = await run(
        decision("in_scope"), fake_llm(AIMessage("Depende do seu perfil de risco.")), advice=True
    )

    assert state["advice_request"] is True

    answer = state["messages"][-1]
    assert answer.content == f"Depende do seu perfil de risco.\n\n{ADVICE_DISCLAIMER}"
    # A resposta é substituída, não duplicada, e mantém as fontes do histórico.
    assert sum(isinstance(m, AIMessage) for m in state["messages"]) == 1
    assert "sources" in answer.additional_kwargs


async def test_disclaimer_is_not_repeated() -> None:
    text = (
        "Depende do seu perfil. Esta resposta é informativa e NÃO constitui recomendação de "
        "investimento."
    )

    state = await run(decision("in_scope"), fake_llm(AIMessage(text)), advice=True)

    assert state["messages"][-1].content == text


async def test_other_questions_get_no_disclaimer() -> None:
    state = await run(decision("in_scope"), agent_llm(), advice=False)

    assert state["messages"][-1].content == "2 + 2 = 4.00"


async def test_advice_check_failure_does_not_block_the_answer() -> None:
    model = fake_guardrail(decision("in_scope"))
    # Um valor inválido faz o `AdviceCheck` falhar na validação, como uma resposta quebrada.
    model.advice = ["quebrado"]  # type: ignore[list-item]
    guardrail = make_guardrail_node(model)

    update = await guardrail({"messages": [HumanMessage("Pergunta")]})  # type: ignore[typeddict-item]

    assert update["scope"].label == "in_scope"
    assert update["advice_request"] is False
