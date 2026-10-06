"""Ingestão offline da base de documentos: `python -m financial_agent.rag.ingest <dir>`.

Lê PDF (por página), Markdown e TXT, divide em trechos e grava no vector store. Os ids dos
trechos são determinísticos (data-model.md §6), então reingerir não duplica nada.
"""

import argparse
import asyncio
import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from financial_agent.config import get_settings
from financial_agent.logging import configure_logging, get_logger
from financial_agent.rag.vectorstore import close_vectorstore, get_embeddings, get_vectorstore

log = get_logger(__name__)

SUPPORTED_SUFFIXES = (".pdf", ".md", ".txt")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

_MD_TITLE = re.compile(r"^#\s+(.+?)\s*#*\s*$", re.MULTILINE)


@dataclass(frozen=True)
class IngestResult:
    files: int
    chunks: int


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_id(source: str) -> str:
    return _sha256(source)


def chunk_id(source: str, chunk_index: int, content: str) -> str:
    return _sha256(source + str(chunk_index) + content)


def _title(path: Path, text: str) -> str:
    if path.suffix == ".md" and (match := _MD_TITLE.search(text)):
        return match.group(1)
    return path.stem


def load_file(path: Path, source: str) -> list[Document]:
    if path.suffix == ".pdf":
        title = path.stem
        documents = []
        for number, page in enumerate(PdfReader(path).pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                metadata = {"source": source, "title": title, "page": number}
                documents.append(Document(page_content=text, metadata=metadata))
        return documents

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    metadata = {"source": source, "title": _title(path, text)}
    return [Document(page_content=text, metadata=metadata)]


def load_directory(directory: Path) -> list[Document]:
    """Carrega os arquivos suportados; `source` é o caminho relativo ao diretório."""
    paths = sorted(
        p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )
    documents: list[Document] = []
    for path in paths:
        documents.extend(load_file(path, path.relative_to(directory).as_posix()))
    return documents


def split_documents(documents: Sequence[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    next_index: defaultdict[str, int] = defaultdict(int)
    chunks = splitter.split_documents(list(documents))
    for chunk in chunks:
        source: str = chunk.metadata["source"]
        index = next_index[source]
        next_index[source] += 1
        chunk.metadata["chunk_index"] = index
        chunk.metadata["document_id"] = document_id(source)
        chunk.id = chunk_id(source, index, chunk.page_content)
    return chunks


async def ingest_directory(directory: Path, vectorstore: VectorStore) -> IngestResult:
    documents = load_directory(directory)
    chunks = split_documents(documents)
    if chunks:
        await vectorstore.aadd_documents(chunks, ids=[chunk.id for chunk in chunks])
    result = IngestResult(
        files=len({doc.metadata["source"] for doc in documents}), chunks=len(chunks)
    )
    log.info("ingest_done", directory=str(directory), files=result.files, chunks=result.chunks)
    return result


async def _run(directory: Path) -> IngestResult:
    settings = get_settings()
    vectorstore = get_vectorstore(settings, get_embeddings(settings))
    try:
        return await ingest_directory(directory, vectorstore)
    finally:
        await close_vectorstore(vectorstore)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingere documentos financeiros no pgvector.")
    parser.add_argument("directory", type=Path, help="diretório com arquivos .pdf, .md e .txt")
    args: Any = parser.parse_args(argv)

    configure_logging(get_settings().LOG_LEVEL)
    directory: Path = args.directory
    if not directory.is_dir():
        parser.error(f"diretório não encontrado: {directory}")
    asyncio.run(_run(directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
