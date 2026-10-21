"""Grafo base: laço agent ⇄ tools, coleta de fontes do turno e memória por thread."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from financial_agent.api.app import create_app
from financial_agent.graph.builder import RECURSION_LIMIT, build_graph
from financial_agent.graph.nodes.agent import MAX_TOOL_ROUNDS, collect_sources
from financial_agent.graph.nodes.quote_guard import STALE_QUOTE
from financial_agent.graph.prompts import AGENT_SYSTEM_PROMPT
from financial_agent.graph.state import CalculationSource, DocumentSource, FxQuoteSource
from financial_agent.tools.calculator import make_calculator_tool
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


def _document(document_id: str) -> DocumentSource:
    return DocumentSource(
        document_id=document_id, title=document_id, source="doc.pdf", snippet="...", score=0.8
    )


def test_collect_sources_sets_marker_on_cited_documents() -> None:
    search = ToolMessage(
        "[3] Doc A (doc.pdf)\n...\n\n[4] Doc B (doc.pdf)\n...\n\n[5] Doc C (doc.pdf)\n...",
        tool_call_id="s1",
        artifact=[_document("a"), _document("b"), _document("c")],
    )
    quote = FxQuoteSource(
        pair="USD-BRL",
        bid=Decimal("5.1"),
        ask=Decimal("5.2"),
        quoted_at=datetime(2026, 10, 20, tzinfo=UTC),
        provider="awesomeapi",
    )
    fx = ToolMessage("USD-BRL", tool_call_id="q1", artifact=quote)
    calc = ToolMessage(
        "1 + 1 = 2", tool_call_id="c1", artifact=CalculationSource(expression="1 + 1", result=2)
    )
    state = {
        "messages": [HumanMessage("pergunta"), search, fx, calc, AIMessage("A [3] e C [5].")],
        "scope": None,
        "turn_sources": [],
    }

    sources = collect_sources(state)["turn_sources"]  # type: ignore[arg-type]

    documents = [s for s in sources if isinstance(s, DocumentSource)]
    assert [(d.document_id, d.marker) for d in documents] == [("a", 3), ("c", 5)]
    assert [s.type for s in sources if not isinstance(s, DocumentSource)] == [
        "fx_quote",
        "calculation",
    ]
    assert all("marker" not in type(s).model_fields for s in sources if s.type != "document")


def test_document_source_without_marker_still_validates() -> None:
    # Fontes salvas no histórico antes do campo `marker` existir.
    stored = {
        "type": "document",
        "document_id": "a",
        "title": "A",
        "source": "doc.pdf",
        "snippet": "...",
        "score": 0.8,
    }

    assert DocumentSource.model_validate(stored).marker is None


async def test_tool_rounds_are_capped_and_last_call_has_tools_disabled() -> None:
    def call(n: int) -> AIMessage:
        tool_call = {"name": "fake_calc", "args": {"expression": f"{n} + {n}"}, "id": f"c{n}"}
        return AIMessage("", tool_calls=[tool_call])

    # O LLM continuaria pedindo ferramenta; a resposta final só vem por causa do limite.
    llm = fake_llm(*(call(n) for n in range(MAX_TOOL_ROUNDS)), AIMessage("Resposta final."))
    graph = build_graph(InMemorySaver(), llm, tools=[fake_calc])

    state = await graph.ainvoke(
        {"messages": [HumanMessage("Calcule")], "turn_sources": []}, config=config("t1")
    )

    assert state["messages"][-1].content == "Resposta final."
    assert llm.tool_choices == [None] * MAX_TOOL_ROUNDS + ["none"]


async def test_tool_rounds_reset_on_each_turn() -> None:
    tool_call = {"name": "fake_calc", "args": {"expression": "2 + 2"}, "id": "c1"}
    llm = fake_llm(
        AIMessage("", tool_calls=[tool_call]),
        AIMessage("4.00"),
        AIMessage("", tool_calls=[{**tool_call, "id": "c2"}]),
        AIMessage("4.00 de novo"),
    )
    graph = build_graph(InMemorySaver(), llm, tools=[fake_calc])

    for message in ("Quanto é 2+2?", "E de novo?"):
        await graph.ainvoke(
            {"messages": [HumanMessage(message)], "turn_sources": []}, config=config("t1")
        )

    assert llm.tool_choices == [None, None, None, None]


class RecursingGraph:
    async def ainvoke(self, *args: object, **kwargs: object) -> None:
        raise GraphRecursionError("Recursion limit reached")


def test_recursion_error_returns_503() -> None:
    with TestClient(create_app(graph=RecursingGraph())) as client:  # type: ignore[arg-type]
        response = client.post("/v1/chat", json={"message": "Oi"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"


async def test_agent_does_not_see_tool_messages_from_earlier_turns() -> None:
    tool_call = {"name": "fake_calc", "args": {"expression": "2 + 2"}, "id": "c1"}
    llm = fake_llm(
        AIMessage("", tool_calls=[tool_call]),
        AIMessage("2 + 2 = 4.00"),
        AIMessage("De nada!"),
    )
    graph = build_graph(InMemorySaver(), llm, tools=[fake_calc])

    for message in ("Quanto é 2+2?", "Obrigado"):
        await graph.ainvoke(
            {"messages": [HumanMessage(message)], "turn_sources": []}, config=config("t1")
        )

    second_turn_input = llm.calls[-1]
    assert [type(m).__name__ for m in second_turn_input] == [
        "SystemMessage",
        "HumanMessage",
        "AIMessage",
        "HumanMessage",
    ]
    assert second_turn_input[2].content == "2 + 2 = 4.00"
    # O turno atual continua vendo as próprias chamadas de ferramenta.
    assert any(isinstance(m, ToolMessage) for m in llm.calls[1])


def fake_quote_tool(*bids: str) -> BaseTool:
    """`get_currency_quote` falso que devolve um bid diferente a cada chamada."""
    remaining = list(bids)

    @tool("get_currency_quote", response_format="content_and_artifact")
    def get_currency_quote(base: str, quote: str = "BRL") -> tuple[str, FxQuoteSource]:
        """Cotação falsa para os testes."""
        bid = Decimal(remaining.pop(0))
        source = FxQuoteSource(
            pair=f"{base}-{quote}",
            bid=bid,
            ask=bid + Decimal("0.001"),
            quoted_at=datetime(2026, 10, 9, 19, 30, tzinfo=UTC),
            provider="fake",
        )
        return f"Par: {source.pair}\nCompra (bid): {bid}", source

    return get_currency_quote


def quote(call_id: str) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": "get_currency_quote", "args": {"base": "EUR"}, "id": call_id}]
    )


def calc(call_id: str, expression: str) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": "calculate", "args": {"expression": expression}, "id": call_id}]
    )


async def test_calculation_with_quote_from_earlier_turn_is_sent_back_to_the_agent() -> None:
    llm = fake_llm(
        quote("q1"),
        AIMessage("O euro está R$ 5.5831 (compra)."),
        # Acompanhamento: o agente reaproveita o bid do turno anterior.
        calc("c1", "500 * 5.5831"),
        quote("q2"),
        calc("c2", "500 * 5.6"),
        AIMessage("500 euros são R$ 2800.00 (500 * 5.6)."),
    )
    graph = build_graph(
        InMemorySaver(), llm, tools=[fake_quote_tool("5.5831", "5.6"), make_calculator_tool()]
    )

    for message in ("Qual a cotação do euro?", "Quanto são 500 disso em reais?"):
        state = await graph.ainvoke(
            {"messages": [HumanMessage(message)], "turn_sources": []}, config=config("t1")
        )

    blocked = next(
        m for m in state["messages"] if isinstance(m, ToolMessage) and m.tool_call_id == "c1"
    )
    assert blocked.text.startswith(STALE_QUOTE)
    assert "5.5831" in blocked.text
    assert [s.type for s in state["turn_sources"]] == ["fx_quote", "calculation"]
    assert state["turn_sources"][1].expression == "500 * 5.6"


async def test_rate_written_by_the_user_is_not_blocked() -> None:
    llm = fake_llm(
        quote("q1"),
        AIMessage("O euro está R$ 5.5831 (compra)."),
        calc("c1", "500 * 5.5831"),
        AIMessage("500 euros a 5,5831 são R$ 2791.55."),
    )
    graph = build_graph(
        InMemorySaver(), llm, tools=[fake_quote_tool("5.5831"), make_calculator_tool()]
    )

    for message in ("Qual a cotação do euro?", "Quanto são 500 euros a 5,5831 em reais?"):
        state = await graph.ainvoke(
            {"messages": [HumanMessage(message)], "turn_sources": []}, config=config("t1")
        )

    assert [s.type for s in state["turn_sources"]] == ["calculation"]
    assert not any(
        isinstance(m, ToolMessage) and m.text.startswith(STALE_QUOTE) for m in state["messages"]
    )


async def test_quote_fetched_in_the_same_turn_is_not_blocked() -> None:
    # Mesmo bid nos dois turnos: o valor também veio da consulta deste turno.
    llm = fake_llm(
        quote("q1"),
        AIMessage("O euro está R$ 5.5831 (compra)."),
        quote("q2"),
        calc("c1", "500 * 5.5831"),
        AIMessage("500 euros são R$ 2791.55."),
    )
    graph = build_graph(
        InMemorySaver(), llm, tools=[fake_quote_tool("5.5831", "5.5831"), make_calculator_tool()]
    )

    for message in ("Qual a cotação do euro?", "Quanto são 500 disso em reais?"):
        state = await graph.ainvoke(
            {"messages": [HumanMessage(message)], "turn_sources": []}, config=config("t1")
        )

    assert [s.type for s in state["turn_sources"]] == ["fx_quote", "calculation"]
