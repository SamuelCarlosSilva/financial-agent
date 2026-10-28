"""Utilitários compartilhados pelos evals com o LLM real."""

import json
import re
import statistics
import unicodedata
from pathlib import Path
from typing import Any

from financial_agent.config import get_settings
from financial_agent.rag.ingest import ingest_directory
from financial_agent.rag.vectorstore import close_vectorstore, get_embeddings, get_vectorstore

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "data" / "docs"
OUT_DIR = Path(__file__).parent / "out"
METRICS_DIR = OUT_DIR / "metrics"


def normalize(text: str) -> str:
    """Minúsculas, sem acentos, espaços colapsados e vírgula decimal ("22.5" → "22,5")."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"(\d)\.(\d)", r"\1,\2", text)
    return " ".join(text.split())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def has_openai_key() -> bool:
    get_settings.cache_clear()
    return bool(get_settings().OPENAI_API_KEY.get_secret_value())


def auth_headers() -> dict[str, str]:
    """`X-API-Key` com a primeira chave de `API_KEYS`; vazio com a autenticação desligada."""
    keys = get_settings().API_KEYS
    return {"X-API-Key": keys[0]} if keys else {}


async def ingest_docs() -> None:
    """Reingere `data/docs/` no Postgres do `.env` (a ingestão é idempotente)."""
    settings = get_settings()
    vectorstore = get_vectorstore(settings, get_embeddings(settings))
    try:
        await ingest_directory(DOCS_DIR, vectorstore)
    finally:
        await close_vectorstore(vectorstore)


def p95(values: list[float]) -> float:
    if len(values) < 2:
        return max(values, default=0.0)
    return statistics.quantiles(values, n=100, method="inclusive")[94]


def pct(value: float) -> str:
    return f"{value:.1%}".replace(".", ",")


def secs(value: float) -> str:
    return f"{value:.2f} s".replace(".", ",")


def record_metric(key: str, result: str, passed: bool) -> None:
    """Grava o resultado de uma métrica para o relatório consolidado (`tests/eval/report.py`).

    Cada eval chama esta função antes do `assert` da meta; a descrição e a meta de cada `key`
    ficam no catálogo do relatório.
    """
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    record = {"key": key, "result": result, "passed": passed}
    (METRICS_DIR / f"{key}.json").write_text(json.dumps(record, ensure_ascii=False), "utf-8")
