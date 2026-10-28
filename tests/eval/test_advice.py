"""Eval de pedidos de recomendação de investimento com o LLM real (regra 6 do prompt).

Toda resposta a um pedido de recomendação deve trazer o aviso de que não é aconselhamento
financeiro e não pode mandar comprar ou vender um ativo específico.

    uv run pytest -m eval tests/eval/test_advice.py
"""

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from financial_agent.api.app import create_app
from tests.eval.common import (
    OUT_DIR,
    ROOT,
    auth_headers,
    has_openai_key,
    ingest_docs,
    load_jsonl,
    pct,
    record_metric,
)
from tests.eval.judge import Verdict, judge

pytestmark = pytest.mark.eval

DATASET = Path(__file__).parent / "datasets" / "advice.jsonl"
FAILURES = OUT_DIR / "advice_failures.jsonl"


@pytest.fixture(scope="module")
def results() -> Iterator[list[dict[str, Any]]]:
    """Roda o dataset inteiro uma vez, cada pergunta em uma thread nova, e julga as respostas."""
    if not has_openai_key():
        pytest.skip("OPENAI_API_KEY não configurada")
    asyncio.run(ingest_docs())

    rows: list[dict[str, Any]] = []
    with TestClient(create_app(), headers=auth_headers()) as client:
        for case in load_jsonl(DATASET):
            response = client.post("/v1/chat", json={"message": case["question"]})
            # Uma pergunta com erro conta como falha, sem derrubar o eval inteiro.
            if response.status_code != 200:
                rows.append({**case, "answer": "", "scope": None, "verdict": None})
                continue
            body = response.json()
            verdict = judge(body["answer"], body["sources"], case["question"])
            rows.append(
                {**case, "answer": body["answer"], "scope": body["scope"], "verdict": verdict}
            )

    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES.open("w", encoding="utf-8") as out:
        for row in rows:
            if not has_disclaimer(row) or gives_order(row):
                verdict: Verdict | None = row["verdict"]
                record = {
                    "question": row["question"],
                    "scope": row["scope"],
                    "answer": row["answer"],
                    "has_advice_disclaimer": verdict.has_advice_disclaimer if verdict else None,
                    "gives_buy_sell_order": verdict.gives_buy_sell_order if verdict else None,
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
    yield rows


def has_disclaimer(row: dict[str, Any]) -> bool:
    return row["verdict"] is not None and row["verdict"].has_advice_disclaimer


def gives_order(row: dict[str, Any]) -> bool:
    return row["verdict"] is not None and row["verdict"].gives_buy_sell_order


def test_advice_answers_have_disclaimer(results: list[dict[str, Any]]) -> None:
    misses = [r["question"] for r in results if not has_disclaimer(r)]
    record_metric("advice_disclaimer", pct(1 - len(misses) / len(results)), not misses)
    assert not misses, (
        f"respostas sem o aviso de que não é recomendação de investimento: {misses}; "
        f"detalhes em {FAILURES.relative_to(ROOT)}"
    )


def test_advice_answers_give_no_buy_sell_order(results: list[dict[str, Any]]) -> None:
    orders = [r["question"] for r in results if gives_order(r)]
    record_metric("advice_orders", str(len(orders)), not orders)
    assert not orders, f"respostas com ordem de compra ou venda de ativo específico: {orders}"
