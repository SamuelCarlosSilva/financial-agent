"""Eval de fundamentação da US1 com o LLM real (SC-002, SC-003, FR-014).

Usa a configuração real (`.env`): OpenAI e o Postgres de `DATABASE_URL`, onde `data/docs/` é
reingerido antes da execução (a ingestão é idempotente).

    uv run pytest -m eval tests/eval/test_grounding.py
"""

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from financial_agent.api.app import create_app
from financial_agent.graph.nodes.agent import cited_markers
from financial_agent.logging import truncate
from financial_agent.rag.ingest import load_directory, split_documents
from financial_agent.tools.document_search import SNIPPET_MAX_CHARS
from tests.eval.common import (
    DOCS_DIR,
    OUT_DIR,
    ROOT,
    has_openai_key,
    ingest_docs,
    load_jsonl,
    normalize,
    pct,
    record_metric,
)
from tests.eval.judge import Verdict, aggregate, judge

pytestmark = pytest.mark.eval

DATASET = Path(__file__).parent / "datasets" / "grounding.jsonl"
FAILURES = OUT_DIR / "grounding_failures.jsonl"

NOT_FOUND_MARKERS = (
    "nao encontrei",
    "nao encontrou",
    "nao localizei",
    "nao ha informac",
    "nao tenho informac",
    "nao consta",
)


def fact_present(fact: str | list[str], answer: str) -> bool:
    """Um fato é uma string ou uma lista de alternativas equivalentes."""
    alternatives = [fact] if isinstance(fact, str) else fact
    normalized = normalize(answer)
    return any(normalize(alt) in normalized for alt in alternatives)


def says_not_found(answer: str) -> bool:
    normalized = normalize(answer)
    return any(marker in normalized for marker in NOT_FOUND_MARKERS)


def document_sources(sources: list[dict[str, Any]]) -> list[str]:
    return [s["source"] for s in sources if s.get("type") == "document"]


def chunk_texts() -> dict[tuple[str, str], str]:
    """(source, snippet) → texto completo do trecho, reconstruído a partir de `data/docs/`."""
    texts = {}
    for chunk in split_documents(load_directory(DOCS_DIR)):
        snippet = truncate(" ".join(chunk.page_content.split()), SNIPPET_MAX_CHARS)
        texts[(chunk.metadata["source"], snippet)] = chunk.page_content
    return texts


def with_full_text(
    sources: list[dict[str, Any]], texts: dict[tuple[str, str], str]
) -> list[dict[str, Any]]:
    """O juiz precisa do trecho inteiro que o agente leu, não só do snippet de 300 caracteres."""
    expanded = []
    for source in sources:
        key = (source.get("source", ""), source.get("snippet", ""))
        if source.get("type") == "document" and key in texts:
            source = {**source, "snippet": texts[key]}
        expanded.append(source)
    return expanded


def without_not_found_claims(verdict: Verdict) -> Verdict:
    """Garante que "não encontrei" não conte como afirmação, mesmo se o juiz a extrair."""
    claims = [c for c in verdict.claims if not says_not_found(c.text)]
    return verdict.model_copy(update={"claims": claims})


@pytest.fixture(scope="module")
def results() -> Iterator[list[dict[str, Any]]]:
    """Roda o dataset inteiro uma vez (cada pergunta em uma thread nova) e julga as respostas."""
    if not has_openai_key():
        pytest.skip("OPENAI_API_KEY não configurada")
    asyncio.run(ingest_docs())

    texts = chunk_texts()
    rows: list[dict[str, Any]] = []
    with TestClient(create_app()) as client:
        for case in load_jsonl(DATASET):
            response = client.post("/v1/chat", json={"message": case["question"]})
            # Uma pergunta com erro conta como falha, sem derrubar o eval inteiro.
            if response.status_code != 200:
                rows.append(
                    {**case, "answer": "", "sources": [], "verdict": None, "error": response.text}
                )
                continue
            body = response.json()
            verdict = judge(
                body["answer"], with_full_text(body["sources"], texts), case["question"]
            )
            verdict = without_not_found_claims(verdict)
            rows.append(
                {**case, "answer": body["answer"], "sources": body["sources"], "verdict": verdict}
            )

    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES.open("w", encoding="utf-8") as out:
        for row in rows:
            if row.get("error"):
                record = {"question": row["question"], "error": row["error"]}
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                continue
            verdict: Verdict = row["verdict"]
            if not verdict.fully_supported:
                record = {
                    "question": row["question"],
                    "answer": row["answer"],
                    "sources": row["sources"],
                    "unsupported_claims": [c.text for c in verdict.unsupported_claims],
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
    yield rows


def answerable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if not r.get("expect_not_found")]


def unanswerable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("expect_not_found")]


def test_all_requests_succeed(results: list[dict[str, Any]]) -> None:
    errors = {r["question"]: r["error"] for r in results if r.get("error")}
    assert not errors, f"perguntas com erro na API: {errors}"


def test_answerable_questions_accuracy(results: list[dict[str, Any]]) -> None:
    rows = answerable(results)
    misses = [
        r["question"]
        for r in rows
        if not (
            all(fact_present(f, r["answer"]) for f in r["expected_facts"])
            and r["expected_source"] in document_sources(r["sources"])
        )
    ]
    accuracy = 1 - len(misses) / len(rows)
    record_metric("sc003_answerable", pct(accuracy), accuracy >= 0.90)
    assert accuracy >= 0.90, f"acerto {accuracy:.0%} < 90% (SC-003); erros: {misses}"


def test_unanswerable_questions_say_not_found(results: list[dict[str, Any]]) -> None:
    rows = unanswerable(results)
    misses = [r["question"] for r in rows if not says_not_found(r["answer"])]
    rate = 1 - len(misses) / len(rows)
    record_metric("sc003_not_found", pct(rate), rate >= 0.95)
    assert rate >= 0.95, f'"não encontrei" em {rate:.0%} < 95% (SC-003); erros: {misses}'


def test_unanswerable_questions_cite_no_documents(results: list[dict[str, Any]]) -> None:
    cited = {
        r["question"]: document_sources(r["sources"])
        for r in unanswerable(results)
        if document_sources(r["sources"])
    }
    assert not cited, f"perguntas sem resposta com fontes de documento: {cited}"


def test_document_markers_match_citations(results: list[dict[str, Any]]) -> None:
    # Cada [n] da resposta tem uma fonte de documento com `marker == n`, e vice-versa.
    mismatches = {}
    for row in results:
        if row.get("error"):
            continue
        markers = [s.get("marker") for s in row["sources"] if s.get("type") == "document"]
        if None in markers or set(markers) != cited_markers(row["answer"]):
            mismatches[row["question"]] = {
                "markers": markers,
                "cited": sorted(cited_markers(row["answer"])),
            }
    assert not mismatches, f"marcadores sem fonte ou fontes sem marcador: {mismatches}"


def test_all_claims_supported_and_in_pt_br(results: list[dict[str, Any]]) -> None:
    summary = aggregate([r["verdict"] for r in results if r["verdict"] is not None])
    record_metric("sc002_supported", pct(summary.supported_rate), summary.supported_rate == 1.0)
    record_metric("fr014_grounding", pct(summary.pt_br_rate), summary.pt_br_rate == 1.0)
    assert summary.supported_rate == 1.0, (
        f"{summary.claims - summary.supported_claims} de {summary.claims} afirmações sem "
        f"fonte (SC-002); detalhes em {FAILURES.relative_to(ROOT)}"
    )
    assert summary.pt_br_rate == 1.0, f"pt-BR em {summary.pt_br_rate:.0%} das respostas (FR-014)"
