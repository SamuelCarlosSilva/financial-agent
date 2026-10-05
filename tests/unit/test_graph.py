"""Grafo base: laço agent ⇄ tools, coleta de fontes do turno e memória por thread."""

from decimal import Decimal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.graph.builder import RECURSION_LIMIT, build_graph
from financial_agent.graph.nodes.agent import collect_sources
from financial_agent.graph.prompts import AGENT_SYSTEM_PROMPT
from financial_agent.graph.state import CalculationSource
from tests.fakes import fake_llm


@tool(response_format="content_and_artifact")
def fake_calc(expression: str) -> tuple[str, CalculationSource]:
    """Calculadora falsa para os testes."""
    return f"{expression} = 4.00", CalculationSource(expression=expression, result=Decimal("4"))


def config(thread_id: str) -> dict[str, object]:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}


async def test_agent_receives_system_prompt_and_answers() -> None:
    llm = fake_llm(AIMessage("Olá!"))
    graph = build_graph(InMemorySaver(), llm, tools=[])

    state = await graph.ainvoke(
        {"messages": [HumanMessage("Oi")], "turn_sources": []}, config=config("t1")
    )

    assert state["messages"][-1].content == "Olá!"
    assert state["turn_sources"] == []
    first_input = llm.calls[0]
    assert isinstance(first_input[0], SystemMessage)
    assert first_input[0].content == AGENT_SYSTEM_PROMPT


async def test_tool_loop_collects_sources_of_current_turn() -> None:
    tool_call = {"name": "fake_calc", "args": {"expression": "2 + 2"}, "id": "c1"}
    llm = fake_llm(
        AIMessage("", tool_calls=[tool_call]),
        AIMessage("2 + 2 = 4.00"),
        AIMessage("Sem cálculo agora."),
    )
    graph = build_graph(InMemorySaver(), llm, tools=[fake_calc])

    first = await graph.ainvoke(
        {"messages": [HumanMessage("Quanto é 2+2?")], "turn_sources": []}, config=config("t1")
    )
    second = await graph.ainvoke(
        {"messages": [HumanMessage("Obrigado")], "turn_sources": []}, config=config("t1")
    )

    assert [s.model_dump() for s in first["turn_sources"]] == [
        {"type": "calculation", "expression": "2 + 2", "result": Decimal("4")}
    ]
    # O turno seguinte não herda as fontes do anterior.
    assert second["turn_sources"] == []


async def test_threads_are_isolated() -> None:
    llm = fake_llm(AIMessage("r1"), AIMessage("r2"), AIMessage("r3"))
    graph = build_graph(InMemorySaver(), llm, tools=[])

    await graph.ainvoke({"messages": [HumanMessage("A")], "turn_sources": []}, config("t1"))
    await graph.ainvoke({"messages": [HumanMessage("B")], "turn_sources": []}, config("t1"))
    await graph.ainvoke({"messages": [HumanMessage("C")], "turn_sources": []}, config("t2"))

    second_turn_input = [m.content for m in llm.calls[1][1:]]
    other_thread_input = [m.content for m in llm.calls[2][1:]]
    assert second_turn_input == ["A", "r1", "B"]
    assert other_thread_input == ["C"]


def test_collect_sources_accepts_list_artifacts_and_ignores_previous_turns() -> None:
    old = ToolMessage(
        "x", tool_call_id="old", artifact=CalculationSource(expression="1", result=Decimal(1))
    )
    current = ToolMessage(
        "y",
        tool_call_id="new",
        artifact=[{"type": "calculation", "expression": "2", "result": "2"}],
    )
    no_artifact = ToolMessage("erro", tool_call_id="err", artifact=None)
    state = {
        "messages": [HumanMessage("1"), old, HumanMessage("2"), current, no_artifact],
        "scope": None,
        "turn_sources": [],
    }

    result = collect_sources(state)  # type: ignore[arg-type]

    assert [s.expression for s in result["turn_sources"]] == ["2"]
