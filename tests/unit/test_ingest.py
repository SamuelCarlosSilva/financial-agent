"""Ingestão: leitura dos arquivos, chunking, metadados e idempotência."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from financial_agent.rag import ingest
from financial_agent.rag.ingest import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    chunk_id,
    document_id,
    ingest_directory,
    load_directory,
    split_documents,
)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def long_text(words: int = 600) -> str:
    return " ".join(f"palavra{i:04d}" for i in range(words))


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    (tmp_path / "come-cotas.md").write_text("# Come-cotas\n\n" + long_text(), encoding="utf-8")
    (tmp_path / "glossario.txt").write_text("CDI é a taxa dos depósitos.", encoding="utf-8")
    (tmp_path / "planilha.csv").write_text("a,b\n1,2", encoding="utf-8")
    return tmp_path


def test_chunk_parameters() -> None:
    assert (CHUNK_SIZE, CHUNK_OVERLAP) == (1000, 150)


def test_loads_only_supported_files_with_metadata(docs_dir: Path) -> None:
    documents = load_directory(docs_dir)

    by_source = {d.metadata["source"]: d for d in documents}
    assert sorted(by_source) == ["come-cotas.md", "glossario.txt"]
    # Markdown usa o título de nível 1; os demais, o nome do arquivo sem extensão.
    assert by_source["come-cotas.md"].metadata["title"] == "Come-cotas"
    assert by_source["glossario.txt"].metadata["title"] == "glossario"
    assert "page" not in by_source["glossario.txt"].metadata


def test_pdf_is_read_per_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        def __init__(self, path: Any) -> None:
            self.pages = [FakePage("Página um."), FakePage("   "), FakePage("Página três.")]

    monkeypatch.setattr(ingest, "PdfReader", FakeReader)
    (tmp_path / "lamina.pdf").write_bytes(b"%PDF-fake")

    documents = load_directory(tmp_path)

    assert [(d.page_content, d.metadata["page"]) for d in documents] == [
        ("Página um.", 1),
        ("Página três.", 3),
    ]
    assert {d.metadata["title"] for d in documents} == {"lamina"}


def test_split_sets_ids_and_chunk_metadata(docs_dir: Path) -> None:
    chunks = split_documents(load_directory(docs_dir))

    md_chunks = [c for c in chunks if c.metadata["source"] == "come-cotas.md"]
    assert len(md_chunks) >= 3
    assert all(len(c.page_content) <= CHUNK_SIZE for c in chunks)
    # Trechos vizinhos do mesmo parágrafo se sobrepõem.
    assert md_chunks[2].page_content[:30] in md_chunks[1].page_content

    for index, chunk in enumerate(md_chunks):
        assert chunk.metadata["chunk_index"] == index
        assert chunk.metadata["document_id"] == sha256("come-cotas.md")
        assert chunk.metadata["title"] == "Come-cotas"
        assert chunk.id == sha256("come-cotas.md" + str(index) + chunk.page_content)
        assert chunk.id == chunk_id("come-cotas.md", index, chunk.page_content)

    assert document_id("glossario.txt") == sha256("glossario.txt")
    assert len({c.id for c in chunks}) == len(chunks)


async def test_ingestion_is_idempotent(docs_dir: Path) -> None:
    store = InMemoryVectorStore(DeterministicFakeEmbedding(size=32))

    first = await ingest_directory(docs_dir, store)
    second = await ingest_directory(docs_dir, store)

    assert first.files == second.files == 2
    assert first.chunks == second.chunks
    assert len(store.store) == first.chunks


async def test_empty_directory_ingests_nothing(tmp_path: Path) -> None:
    store = InMemoryVectorStore(DeterministicFakeEmbedding(size=32))

    result = await ingest_directory(tmp_path, store)

    assert (result.files, result.chunks) == (0, 0)
    assert store.store == {}
