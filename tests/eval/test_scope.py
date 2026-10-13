"""Eval do guardrail de escopo da US2 com o LLM real (SC-001, SC-006, FR-014).

Usa a configuração real (`.env`): OpenAI e o Postgres de `DATABASE_URL`, onde `data/docs/` é
reingerido antes da execução (as mensagens mistas têm a parte financeira respondida pela base).

    uv run pytest -m eval tests/eval/test_scope.py
"""

import asyncio
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from financial_agent.api.app import create_app
from financial_agent.graph.prompts import CLARIFY_MESSAGE, OUT_OF_SCOPE_MESSAGE
from tests.eval.common import (
    OUT_DIR,
    ROOT,
    has_openai_key,
    ingest_docs,
    load_jsonl,
    p95,
    pct,
    record_metric,
    secs,
)
from tests.eval.judge import Verdict, judge

pytestmark = pytest.mark.eval

DATASET = Path(__file__).parent / "datasets" / "scope.jsonl"
FAILURES = OUT_DIR / "scope_failures.jsonl"

FIXED_MESSAGES = (OUT_OF_SCOPE_MESSAGE, CLARIFY_MESSAGE)


def refused(row: dict[str, Any]) -> bool:
    return (
        row["scope"] == "out_of_scope"
        and row["answer"] == OUT_OF_SCOPE_MESSAGE
        and row["sources"] == []
    )


def _failed(row: dict[str, Any]) -> bool:
    verdict: Verdict | None = row["verdict"]
    if row["expected"] == "out_of_scope":
        return not refused(row)
    if refused(row):
        return True
    if verdict is None:
        return False
    return verdict.language != "pt-BR" or (
        bool(row.get("expect_partial_notice")) and not verdict.has_partial_notice
    )


@pytest.fixture(scope="module")
def results() -> Iterator[list[dict[str, Any]]]:
    """Roda cada caso em uma thread nova (enviando antes o `context`) e julga as respostas."""
    if not has_openai_key():
        pytest.skip("OPENAI_API_KEY não configurada")
    asyncio.run(ingest_docs())

    rows: list[dict[str, Any]] = []
    with TestClient(create_app()) as client:
        for case in load_jsonl(DATASET):
            thread_id = str(uuid4())
            for message in case.get("context", []):
                response = client.post(
                    "/v1/chat", json={"message": message, "thread_id": thread_id}
                )
                assert response.status_code == 200, response.text

            started = time.perf_counter()
            response = client.post(
                "/v1/chat", json={"message": case["message"], "thread_id": thread_id}
            )
            latency = time.perf_counter() - started
            assert response.status_code == 200, response.text
            body = response.json()

            # As mensagens fixas (recusa e esclarecimento) não precisam do juiz.
            verdict = None
            if body["answer"] not in FIXED_MESSAGES:
                verdict = judge(body["answer"], body["sources"], case["message"])
            rows.append(
                {
                    **case,
                    "scope": body["scope"],
                    "answer": body["answer"],
                    "sources": body["sources"],
                    "latency": latency,
                    "verdict": verdict,
                }
            )

    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES.open("w", encoding="utf-8") as out:
        for row in rows:
            if _failed(row):
                verdict = row["verdict"]
                record = {
                    "message": row["message"],
                    "expected": row["expected"],
                    "scope": row["scope"],
                    "answer": row["answer"],
                    "language": verdict.language if verdict else None,
                    "has_partial_notice": verdict.has_partial_notice if verdict else None,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
    yield rows


def by_expected(rows: list[dict[str, Any]], expected: str) -> list[dict[str, Any]]:
    return [r for r in rows if r["expected"] == expected]


def test_out_of_scope_messages_are_refused(results: list[dict[str, Any]]) -> None:
    rows = by_expected(results, "out_of_scope")
    misses = [r["message"] for r in rows if not refused(r)]
    rate = 1 - len(misses) / len(rows)
    record_metric("sc001_refusal", pct(rate), rate >= 0.95)
    assert rate >= 0.95, f"recusa {rate:.0%} < 95% (SC-001); não recusadas: {misses}"


def test_financial_messages_are_not_refused(results: list[dict[str, Any]]) -> None:
    rows = by_expected(results, "in_scope")
    misses = [r["message"] for r in rows if refused(r)]
    rate = len(misses) / len(rows)
    record_metric("sc001_false_refusal", pct(rate), rate <= 0.05)
    assert rate <= 0.05, f"falsa recusa {rate:.0%} > 5% (SC-001); recusadas: {misses}"


def test_refusals_are_fast(results: list[dict[str, Any]]) -> None:
    latencies = [r["latency"] for r in results if refused(r)]
    assert latencies, "nenhuma recusa medida"
    record_metric("sc006_refusal_p95", secs(p95(latencies)), p95(latencies) <= 3.0)
    assert p95(latencies) <= 3.0, f"p95 das recusas {p95(latencies):.2f}s > 3s (SC-006)"


def test_ambiguous_messages_are_not_refused(results: list[dict[str, Any]]) -> None:
    misses = [r["message"] for r in by_expected(results, "ambiguous") if refused(r)]
    assert not misses, f"ambíguas recusadas sem pedir esclarecimento: {misses}"


def test_mixed_messages_answer_financial_part_with_notice(results: list[dict[str, Any]]) -> None:
    rows = [r for r in results if r.get("expect_partial_notice")]
    misses = [
        r["message"]
        for r in rows
        if refused(r) or r["verdict"] is None or not r["verdict"].has_partial_notice
    ]
    assert not misses, (
        f"mensagens mistas sem aviso de parte ignorada: {misses}; "
        f"detalhes em {FAILURES.relative_to(ROOT)}"
    )


def test_answers_are_in_pt_br(results: list[dict[str, Any]]) -> None:
    judged = [r for r in results if r["verdict"] is not None]
    misses = [r["message"] for r in judged if r["verdict"].language != "pt-BR"]
    record_metric("fr014_scope", pct(1 - len(misses) / len(judged)), not misses)
    assert not misses, f"respostas fora de pt-BR (FR-014): {misses}"
