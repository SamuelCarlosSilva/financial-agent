"""Fábricas de embeddings e do vector store (PGVector, coleção `financial_docs`)."""

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector

from financial_agent.config import Settings

COLLECTION_NAME = "financial_docs"


def to_psycopg_url(database_url: str) -> str:
    """Converte a URL do Postgres para o driver psycopg3 do SQLAlchemy."""
    for prefix in ("postgresql://", "postgres://"):
        if database_url.startswith(prefix):
            return "postgresql+psycopg://" + database_url.removeprefix(prefix)
    return database_url


def get_embeddings(settings: Settings) -> Embeddings:
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        request_timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=1,
        openai_api_key=settings.OPENAI_API_KEY,
    )


def get_vectorstore(settings: Settings, embeddings: Embeddings) -> PGVector:
    """PGVector assíncrono. As tabelas são criadas no primeiro uso (lazy init)."""
    return PGVector(
        embeddings=embeddings,
        connection=to_psycopg_url(settings.DATABASE_URL),
        collection_name=COLLECTION_NAME,
        use_jsonb=True,
        async_mode=True,
    )


async def close_vectorstore(vectorstore: PGVector) -> None:
    """Fecha as conexões do engine assíncrono criado pelo PGVector."""
    engine = vectorstore._async_engine
    if engine is not None:
        await engine.dispose()
