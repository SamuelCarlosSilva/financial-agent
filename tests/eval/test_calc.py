"""Eval da calculadora da US4 com o LLM real (SC-004, FR-007).

Usa a configuração real (`.env`): OpenAI e o Postgres de `DATABASE_URL`. Os cálculos não
dependem da base de documentos nem da cotação ao vivo (as conversões trazem a taxa na pergunta).

    uv run pytest -m eval tests/eval/test_calc.py
"""

import json
import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from financial_agent.api.app import create_app
from tests.eval.common import OUT_DIR, ROOT, has_openai_key, load_jsonl

pytestmark = pytest.mark.eval

DATASET = Path(__file__).parent / "datasets" / "calc.jsonl"
FAILURES = OUT_DIR / "calc_failures.jsonl"

# "11.268,25" (pt-BR com milhar), "11268,25" ou "11268.25".
_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


def numbers(answer: str) -> set[Decimal]:
    values = set()
    for token in _NUMBER.findall(answer):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
            token = token.replace(".", "")
        values.add(Decimal(token.replace(",", ".")))
    return values


def has_result(row: dict[str, Any]) -> bool:
    return Decimal(row["expected_result"]) in numbers(row["answer"])


def has_calculation_source(row: dict[str, Any]) -> bool:
    return any(s.get("type") == "calculation" for s in row["sources"])


@pytest.fixture(scope="module")
def results() -> Iterator[list[dict[str, Any]]]:
    """Roda o dataset inteiro uma vez, cada pergunta em uma thread nova."""
    if not has_openai_key():
        pytest.skip("OPENAI_API_KEY não configurada")

    rows: list[dict[str, Any]] = []
    with TestClient(create_app()) as client:
        for case in load_jsonl(DATASET):
            response = client.post("/v1/chat", json={"message": case["question"]})
            # Uma pergunta com erro conta como falha, sem derrubar o eval inteiro.
            if response.status_code != 200:
                rows.append({**case, "answer": "", "sources": [], "error": response.text})
                continue
            body = response.json()
            rows.append({**case, "answer": body["answer"], "sources": body["sources"]})

    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES.open("w", encoding="utf-8") as out:
        for row in rows:
            if not (has_result(row) and has_calculation_source(row)):
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
    yield rows


def test_numbers_are_parsed_in_both_formats() -> None:
    assert numbers("R$ 11.268,25 ou 11268.25 ou 11268,25") == {Decimal("11268.25")}


def test_answers_contain_expected_result(results: list[dict[str, Any]]) -> None:
    misses = [r["question"] for r in results if not has_result(r)]
    assert not misses, (
        f"{len(misses)} de {len(results)} respostas sem o resultado esperado (SC-004): {misses}; "
        f"detalhes em {FAILURES.relative_to(ROOT)}"
    )


def test_answers_cite_calculation_source(results: list[dict[str, Any]]) -> None:
    misses = [r["question"] for r in results if not has_calculation_source(r)]
    assert not misses, f"respostas sem fonte `calculation` (FR-007): {misses}"
