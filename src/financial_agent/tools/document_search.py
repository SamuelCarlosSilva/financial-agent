"""Ferramenta de busca na base de documentos financeiros (RAG), contracts/tools.md."""

import inspect
import warnings
from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, tool
from langchain_core.vectorstores import VectorStore
from langgraph.prebuilt import InjectedState
from pydantic import Field

from financial_agent.config import Settings
from financial_agent.graph.nodes.agent import current_turn
from financial_agent.graph.state import DocumentSource
from financial_agent.logging import truncate

TOOL_NAME = "search_financial_documents"
NO_RESULTS = "NENHUM_RESULTADO_RELEVANTE"
SNIPPET_MAX_CHARS = 300

# A similaridade de cosseno pode ser negativa para textos sem relação; o limiar já os descarta.
warnings.filterwarnings("ignore", message="Relevance scores must be between 0 and 1")

Query = Annotated[str, Field(min_length=1, max_length=500, pattern=r"\S")]


def _header(index: int, metadata: dict[str, Any]) -> str:
    source = metadata.get("source", "")
    title = metadata.get("title") or source
    page = metadata.get("page")
    origin = f"{source}, p.{page}" if page is not None else source
    return f"[{index}] {title} ({origin})"


def _first_index(state: dict[str, Any] | None, query: str, top_k: int) -> int:
    """Primeiro número dos trechos desta busca, único no turno.

    Cada busca do turno recebe uma faixa própria ([1–4], [5–8], ...) conforme sua posição
    entre as chamadas da ferramenta, para que o agente cite os trechos sem ambiguidade.
    """
    if not state:
        return 1
    queries = [
        call["args"].get("query")
        for message in current_turn(state["messages"])
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call["name"] == TOOL_NAME
    ]
    position = queries.index(query) if query in queries else 0
    return position * top_k + 1


def _to_source(document: Document, score: float) -> DocumentSource:
    metadata = document.metadata
    snippet = truncate(" ".join(document.page_content.split()), SNIPPET_MAX_CHARS)
    return DocumentSource(
        document_id=metadata.get("document_id", ""),
        title=metadata.get("title") or metadata.get("source", ""),
        source=metadata.get("source", ""),
        page=metadata.get("page"),
        snippet=snippet,
        score=score,
    )


def make_search_tool(vectorstore: VectorStore, settings: Settings) -> BaseTool:
    @tool(response_format="content_and_artifact")
    async def search_financial_documents(
        query: Query, state: Annotated[dict[str, Any] | None, InjectedState] = None
    ) -> tuple[str, list[DocumentSource]]:
        """Busca trechos relevantes na base de documentos financeiros do projeto
        (regulamentos, lâminas de fundos, glossários, políticas).

        Use para perguntas conceituais ou sobre produtos/regras financeiras.
        NÃO use para cotações de moedas nem para cálculos.

        Args:
            query: pergunta ou termos de busca em português, autocontida
                (resolva referências do histórico antes de chamar).

        Returns:
            Até 4 trechos numerados com título e origem, ou a mensagem
            "NENHUM_RESULTADO_RELEVANTE" se nada superar o limiar de relevância.
        """
        results = await vectorstore.asimilarity_search_with_relevance_scores(
            query, k=settings.RAG_TOP_K
        )
        relevant = [(doc, score) for doc, score in results if score >= settings.RAG_MIN_SCORE]
        if not relevant:
            return NO_RESULTS, []

        first = _first_index(state, query, settings.RAG_TOP_K)
        blocks = [
            f"{_header(index, doc.metadata)}\n{doc.page_content}"
            for index, (doc, _) in enumerate(relevant, start=first)
        ]
        return "\n\n".join(blocks), [_to_source(doc, score) for doc, score in relevant]

    # Remove a indentação da docstring na descrição enviada ao LLM.
    search_financial_documents.description = inspect.cleandoc(
        search_financial_documents.description
    )
    return search_financial_documents
