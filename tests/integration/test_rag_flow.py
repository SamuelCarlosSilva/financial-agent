"""Fluxo de RAG no Postgres real: ingestão no pgvector e busca pela ferramenta."""

from collections.abc import AsyncIterator
from pathlib import Path

import psycopg
import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import ToolMessage
from langchain_postgres import PGVector

from financial_agent.config import Settings
from financial_agent.rag.ingest import ingest_directory, load_directory, split_documents
from financial_agent.rag.vectorstore import COLLECTION_NAME, close_vectorstore, get_vectorstore
from financial_agent.tools.document_search import NO_RESULTS, make_search_tool

FUNDOS = "# Tributação de fundos\n\nFundos de ações pagam 15% de IR no resgate, sem come-cotas."
FGC = "# FGC\n\nO FGC garante até R$ 250 mil por CPF e por instituição financeira."


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    (tmp_path / "fundos.md").write_text(FUNDOS, encoding="utf-8")
    (tmp_path / "fgc.md").write_text(FGC, encoding="utf-8")
    return tmp_path


@pytest.fixture
async def vectorstore(postgres_url: str) -> AsyncIterator[PGVector]:
    settings = Settings(DATABASE_URL=postgres_url)
    store = get_vectorstore(settings, DeterministicFakeEmbedding(size=1536))
    yield store
    await close_vectorstore(store)


def stored_metadata(postgres_url: str) -> list[dict[str, object]]:
    with psycopg.connect(postgres_url) as conn:
        rows = conn.execute(
            """
            SELECT e.cmetadata
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON c.uuid = e.collection_id
            WHERE c.name = %s
            """,
            (COLLECTION_NAME,),
        ).fetchall()
    return [row[0] for row in rows]


async def test_ingest_and_search_in_pgvector(
    docs_dir: Path, vectorstore: PGVector, postgres_url: str
) -> None:
    result = await ingest_directory(docs_dir, vectorstore)
    # Reingerir não duplica trechos (ids determinísticos + upsert).
    await ingest_directory(docs_dir, vectorstore)

    metadata = stored_metadata(postgres_url)
    assert len(metadata) == result.chunks == 2
    by_source = {m["source"]: m for m in metadata}
    assert by_source["fgc.md"]["title"] == "FGC"
    assert by_source["fgc.md"]["document_id"]

    tool = make_search_tool(vectorstore, Settings(RAG_MIN_SCORE=0.35, RAG_TOP_K=4))
    # Com embeddings determinísticos, só o texto idêntico ao trecho tem similaridade alta.
    fgc_chunk = next(
        c for c in split_documents(load_directory(docs_dir)) if "FGC" in c.page_content
    )
    call = {"type": "tool_call", "name": tool.name, "args": {"query": fgc_chunk.page_content}}
    message = await tool.ainvoke({**call, "id": "c1"})

    assert isinstance(message, ToolMessage)
    assert message.content.startswith("[1] FGC (fgc.md)\n")
    assert [s.source for s in message.artifact] == ["fgc.md"]
    assert message.artifact[0].score == pytest.approx(1.0, abs=1e-3)

    miss = await tool.ainvoke({**call, "args": {"query": "assunto sem relação"}, "id": "c2"})
    assert miss.content == NO_RESULTS
    assert miss.artifact == []
