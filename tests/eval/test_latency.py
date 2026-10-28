"""Eval de latência ponta a ponta com o LLM real (SC-006).

Mede o tempo de `POST /v1/chat` nas perguntas dos datasets de fundamentação, cálculo e nas
financeiras do escopo, uma de cada vez, e depois com 20 requisições simultâneas. A API roda no
próprio processo (`httpx.ASGITransport`), com o lifespan real: Postgres, OpenAI e AwesomeAPI.

    uv run pytest -m eval tests/eval/test_latency.py
"""

import asyncio
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from financial_agent.api.app import create_app
from tests.eval.common import (
    OUT_DIR,
    auth_headers,
    has_openai_key,
    ingest_docs,
    load_jsonl,
    p95,
    record_metric,
    secs,
)

pytestmark = pytest.mark.eval

DATASETS = Path(__file__).parent / "datasets"
FAILURES = OUT_DIR / "latency_failures.jsonl"
TARGET_SECONDS = 10.0
CONCURRENCY = 20


def questions() -> list[str]:
    grounding = [c["question"] for c in load_jsonl(DATASETS / "grounding.jsonl")]
    calc = [c["question"] for c in load_jsonl(DATASETS / "calc.jsonl")]
    # Só as financeiras sem contexto: as que têm `context` dependem de turnos anteriores.
    scope = [
        c["message"]
        for c in load_jsonl(DATASETS / "scope.jsonl")
        if c["expected"] == "in_scope" and not c.get("context")
    ]
    return grounding + calc + scope


async def timed_post(client: httpx.AsyncClient, message: str) -> dict[str, Any]:
    started = time.perf_counter()
    response = await client.post("/v1/chat", json={"message": message})
    return {
        "message": message,
        "status": response.status_code,
        "seconds": time.perf_counter() - started,
    }


async def measure() -> dict[str, list[dict[str, Any]]]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=transport, base_url="http://api", timeout=120, headers=auth_headers()
        ) as client,
    ):
        sequential = [await timed_post(client, message) for message in questions()]
        burst = questions()[:CONCURRENCY]
        concurrent = await asyncio.gather(*(timed_post(client, m) for m in burst))
    return {"sequential": sequential, "concurrent": list(concurrent)}


@pytest.fixture(scope="module")
def results() -> Iterator[dict[str, list[dict[str, Any]]]]:
    if not has_openai_key():
        pytest.skip("OPENAI_API_KEY não configurada")
    asyncio.run(ingest_docs())
    measured = asyncio.run(measure())

    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES.open("w", encoding="utf-8") as out:
        for scenario, rows in measured.items():
            for row in rows:
                if row["status"] >= 500 or row["seconds"] > TARGET_SECONDS:
                    out.write(json.dumps({"scenario": scenario, **row}, ensure_ascii=False) + "\n")
    yield measured


def test_p95_latency_within_target(results: dict[str, list[dict[str, Any]]]) -> None:
    latency = p95([r["seconds"] for r in results["sequential"]])
    record_metric("sc006_p95", secs(latency), latency <= TARGET_SECONDS)
    assert latency <= TARGET_SECONDS, f"p95 {latency:.2f}s > {TARGET_SECONDS:.0f}s (SC-006)"


def test_concurrent_requests_within_target(results: dict[str, list[dict[str, Any]]]) -> None:
    rows = results["concurrent"]
    errors = [r for r in rows if r["status"] >= 500]
    latency = p95([r["seconds"] for r in rows])
    passed = not errors and latency <= TARGET_SECONDS
    record_metric("sc006_load", f"{secs(latency)}, {len(errors)} erros 5xx", passed)
    assert not errors, f"{len(errors)} de {len(rows)} requisições simultâneas com 5xx: {errors}"
    assert latency <= TARGET_SECONDS, (
        f"p95 com {CONCURRENCY} simultâneas {latency:.2f}s > {TARGET_SECONDS:.0f}s (SC-006)"
    )
