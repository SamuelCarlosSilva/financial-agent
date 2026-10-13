"""Ferramenta `search_financial_documents`: limiar, formatação, artefato e validação."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from financial_agent.api.app import create_app
from financial_agent.config import Settings
from financial_agent.graph.builder import build_graph
from financial_agent.graph.prompts import NOT_FOUND_MESSAGE
from financial_agent.graph.state import DocumentSource
from financial_agent.tools import get_tools
from financial_agent.tools.document_search import NO_RESULTS, make_search_tool
from tests.fakes import fake_llm


class FakeVectorStore:
    """Devolve `(Document, score)` fixos e registra as buscas recebidas."""

    def __init__(self, results: list[tuple[Document, float]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    async def asimilarity_search_with_relevance_scores(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        self.calls.append({"query": query, "k": k})
        return self.results[:k]


def doc(text: str, source: str, title: str, page: int | None = None) -> Document:
    metadata: dict[str, Any] = {"source": source, "title": title, "document_id": f"id-{source}"}
    if page is not None:
        metadata["page"] = page
    return Document(page_content=text, metadata=metadata)


def settings(**overrides: Any) -> Settings:
    return Settings(RAG_MIN_SCORE=0.5, RAG_TOP_K=3, **overrides)


async def run(tool: Any, query: str) -> ToolMessage:
    call = {"type": "tool_call", "name": tool.name, "args": {"query": query}, "id": "c1"}
    message = await tool.ainvoke(call)
    assert isinstance(message, ToolMessage)
    return message


async def test_returns_numbered_chunks_above_threshold() -> None:
    long_text = "Come-cotas é a antecipação semestral do imposto de renda. " * 20
    store = FakeVectorStore(
        [
            (doc(long_text, "come-cotas.md", "Come-cotas"), 0.82),
            (doc("Tabela regressiva do IR.", "tributacao.pdf", "Tributação", page=3), 0.61),
            (doc("Trecho pouco relevante.", "outro.md", "Outro"), 0.49),
        ]
    )
    tool = make_search_tool(store, settings())  # type: ignore[arg-type]

    message = await run(tool, "O que é come-cotas?")

    assert store.calls == [{"query": "O que é come-cotas?", "k": 3}]
    content = str(message.content)
    assert content.startswith("[1] Come-cotas (come-cotas.md)\nCome-cotas é a antecipação")
    assert "\n\n[2] Tributação (tributacao.pdf, p.3)\nTabela regressiva do IR." in content
    assert "[3]" not in content and "pouco relevante" not in content

    sources = message.artifact
    assert [type(s) for s in sources] == [DocumentSource, DocumentSource]
    first, second = sources
    assert (first.document_id, first.title, first.source, first.page) == (
        "id-come-cotas.md",
        "Come-cotas",
        "come-cotas.md",
        None,
    )
    assert first.score == pytest.approx(0.82)
    assert len(first.snippet) <= 300
    assert first.snippet.startswith("Come-cotas é a antecipação")
    assert second.page == 3


async def test_score_equal_to_threshold_is_kept() -> None:
    store = FakeVectorStore([(doc("No limite.", "a.md", "A"), 0.5)])
    tool = make_search_tool(store, settings())  # type: ignore[arg-type]

    message = await run(tool, "limite")

    assert len(message.artifact) == 1


async def test_everything_below_threshold_returns_no_results() -> None:
    store = FakeVectorStore([(doc("Irrelevante.", "a.md", "A"), 0.2)])
    tool = make_search_tool(store, settings())  # type: ignore[arg-type]

    message = await run(tool, "Qual a capital da Mongólia?")

    assert message.content == NO_RESULTS == "NENHUM_RESULTADO_RELEVANTE"
    assert message.artifact == []


async def test_empty_store_returns_no_results() -> None:
    tool = make_search_tool(FakeVectorStore([]), settings())  # type: ignore[arg-type]

    message = await run(tool, "qualquer coisa")

    assert message.content == NO_RESULTS
    assert message.artifact == []


@pytest.mark.parametrize("query", ["", "   ", "x" * 501])
async def test_invalid_query_is_rejected(query: str) -> None:
    store = FakeVectorStore([])
    tool = make_search_tool(store, settings())  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await tool.ainvoke({"query": query})
    assert store.calls == []


async def test_query_with_500_characters_is_accepted() -> None:
    tool = make_search_tool(FakeVectorStore([]), settings())  # type: ignore[arg-type]

    message = await run(tool, "x" * 500)

    assert message.content == NO_RESULTS


def test_docstring_follows_the_contract() -> None:
    tool = make_search_tool(FakeVectorStore([]), settings())  # type: ignore[arg-type]

    assert tool.name == "search_financial_documents"
    assert "NÃO use para cotações de moedas nem para cálculos." in tool.description
    assert '"NENHUM_RESULTADO_RELEVANTE"' in tool.description


def test_registry_adds_search_tool_only_with_vectorstore() -> None:
    assert [t.name for t in get_tools(settings())] == ["get_currency_quote", "calculate"]

    tools = get_tools(settings(), vectorstore=FakeVectorStore([]))  # type: ignore[arg-type]

    assert [t.name for t in tools] == [
        "search_financial_documents",
        "get_currency_quote",
        "calculate",
    ]


def test_chat_returns_document_sources() -> None:
    store = FakeVectorStore([(doc("Come-cotas é semestral.", "come-cotas.md", "Come-cotas"), 0.9)])
    tool_call = {"name": "search_financial_documents", "args": {"query": "come-cotas"}, "id": "s1"}
    llm = fake_llm(
        AIMessage("", tool_calls=[tool_call]),
        AIMessage("O come-cotas é semestral [1]."),
    )
    graph = build_graph(InMemorySaver(), llm, get_tools(settings(), vectorstore=store))  # type: ignore[arg-type]

    with TestClient(create_app(graph=graph)) as client:
        response = client.post("/v1/chat", json={"message": "O que é come-cotas?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("O come-cotas é semestral")
    assert [(s["type"], s["source"]) for s in body["sources"]] == [("document", "come-cotas.md")]
    # O LLM recebeu os trechos numerados como resultado da ferramenta.
    tool_result = llm.calls[1][-1]
    assert tool_result.content.startswith("[1] Come-cotas (come-cotas.md)")


class QueryStore(FakeVectorStore):
    """Devolve resultados diferentes por consulta."""

    def __init__(self, by_query: dict[str, list[tuple[Document, float]]]) -> None:
        super().__init__([])
        self.by_query = by_query

    async def asimilarity_search_with_relevance_scores(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        return self.by_query[query][:k]


def search_call(query: str, call_id: str) -> dict[str, Any]:
    return {"name": "search_financial_documents", "args": {"query": query}, "id": call_id}


async def run_graph(store: FakeVectorStore, *responses: AIMessage) -> tuple[Any, dict[str, Any]]:
    llm = fake_llm(*responses)
    graph = build_graph(InMemorySaver(), llm, get_tools(settings(), vectorstore=store))  # type: ignore[arg-type]
    state = await graph.ainvoke(
        {"messages": [HumanMessage("pergunta")], "turn_sources": []},
        {"configurable": {"thread_id": "t1"}},
    )
    return llm, state


async def test_uncited_document_chunks_are_not_sources() -> None:
    store = FakeVectorStore(
        [
            (doc("Trecho parecido A.", "a.md", "A"), 0.7),
            (doc("Trecho parecido B.", "b.md", "B"), 0.6),
        ]
    )

    _, state = await run_graph(
        store,
        AIMessage("", tool_calls=[search_call("day trade", "s1")]),
        AIMessage("Não encontrei essa informação nas fontes disponíveis."),
    )

    assert state["turn_sources"] == []


async def test_parallel_searches_get_distinct_numbers() -> None:
    store = QueryStore(
        {
            "come-cotas": [
                (doc("Semestral.", "come-cotas.md", "Come-cotas"), 0.9),
                (doc("Maio e novembro.", "come-cotas.md", "Come-cotas"), 0.8),
            ],
            "fgc": [(doc("Até R$ 250 mil.", "fgc.md", "FGC"), 0.9)],
        }
    )

    llm, state = await run_graph(
        store,
        AIMessage("", tool_calls=[search_call("come-cotas", "s1"), search_call("fgc", "s2")]),
        AIMessage("É semestral [1] e o FGC cobre até R$ 250 mil [4]."),
    )

    tool_results = [m.content for m in llm.calls[1] if isinstance(m, ToolMessage)]
    assert tool_results[0].startswith("[1] Come-cotas") and "\n\n[2] Come-cotas" in tool_results[0]
    assert tool_results[1].startswith("[4] FGC (fgc.md)")  # RAG_TOP_K=3
    assert [s.snippet for s in state["turn_sources"]] == ["Semestral.", "Até R$ 250 mil."]


async def test_grouped_citations_are_recognized() -> None:
    store = FakeVectorStore(
        [
            (doc("Um.", "a.md", "A"), 0.9),
            (doc("Dois.", "b.md", "B"), 0.8),
            (doc("Três.", "c.md", "C"), 0.7),
        ]
    )

    _, state = await run_graph(
        store,
        AIMessage("", tool_calls=[search_call("q", "s1")]),
        AIMessage("Resposta [1, 3]."),
    )

    assert [s.source for s in state["turn_sources"]] == ["a.md", "c.md"]


async def test_answer_without_citation_after_search_is_replaced() -> None:
    store = FakeVectorStore([(doc("Tabela regressiva da renda fixa.", "rf.md", "RF"), 0.6)])

    _, state = await run_graph(
        store,
        AIMessage("", tool_calls=[search_call("day trade", "s1")]),
        AIMessage("Day trade paga 20% de IR sobre o lucro."),
    )

    assert state["messages"][-1].content == NOT_FOUND_MESSAGE
    # A resposta foi substituída, não acrescentada.
    assert [type(m).__name__ for m in state["messages"]] == [
        "HumanMessage",
        "AIMessage",
        "ToolMessage",
        "AIMessage",
    ]
    assert state["turn_sources"] == []


async def test_cited_answer_is_kept() -> None:
    store = FakeVectorStore([(doc("Semestral.", "come-cotas.md", "Come-cotas"), 0.9)])

    _, state = await run_graph(
        store,
        AIMessage("", tool_calls=[search_call("come-cotas", "s1")]),
        AIMessage("O come-cotas é semestral [1]."),
    )

    assert state["messages"][-1].content == "O come-cotas é semestral [1]."


async def test_turn_without_search_is_not_touched() -> None:
    _, state = await run_graph(FakeVectorStore([]), AIMessage("Olá! Como posso ajudar?"))

    assert state["messages"][-1].content == "Olá! Como posso ajudar?"


async def test_citation_without_search_in_the_turn_is_replaced() -> None:
    # Acompanhamento respondido com o trecho de um turno anterior: o [1] não teria fonte.
    _, state = await run_graph(FakeVectorStore([]), AIMessage("É cobrado em maio e novembro [1]."))

    assert state["messages"][-1].content == NOT_FOUND_MESSAGE
    assert state["turn_sources"] == []
