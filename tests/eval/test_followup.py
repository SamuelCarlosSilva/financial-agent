"""Eval de perguntas de acompanhamento com o LLM real (SC-005, FR-008, FR-010).

Cada conversa roda em uma thread nova. O último turno só faz sentido com o contexto dos
anteriores ("E o euro?", "E se fossem 24 meses?"): a interpretação é conferida pela chamada de
ferramenta e pelos argumentos gravados no estado da thread. Na variante de controle, o último
turno vai sozinho para outra thread, que não pode mostrar nada do contexto da primeira.

    uv run pytest -m eval tests/eval/test_followup.py
"""

import asyncio
import json
import unicodedata
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from financial_agent.api.app import create_app
from tests.eval.common import (
    OUT_DIR,
    ROOT,
    has_openai_key,
    ingest_docs,
    load_jsonl,
    pct,
    record_metric,
)

pytestmark = pytest.mark.eval

DATASET = Path(__file__).parent / "datasets" / "followup.jsonl"
FAILURES = OUT_DIR / "followup_failures.jsonl"


def compact(text: str) -> str:
    """Minúsculas, sem acentos e sem espaços: "10000 * (1 + 0.01)" → "10000*(1+0.01)"."""
    text = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch) and not ch.isspace())


def contains(value: Any, expected: str | list[str]) -> bool:
    """`expected` é um trecho ou uma lista de trechos alternativos."""
    alternatives = [expected] if isinstance(expected, str) else expected
    return any(compact(alt) in compact(value) for alt in alternatives)


def last_turn_calls(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    start = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    return [
        {"name": call["name"], "args": call["args"]}
        for m in messages[start + 1 :]
        if isinstance(m, AIMessage)
        for call in m.tool_calls
    ]


def called(calls: list[dict[str, Any]], tool: str, args_contains: dict[str, Any]) -> bool:
    return any(
        call["name"] == tool
        and all(
            contains(call["args"].get(arg, ""), piece)
            for arg, pieces in args_contains.items()
            for piece in pieces
        )
        for call in calls
    )


def interpreted(case: dict[str, Any], calls: list[dict[str, Any]]) -> bool:
    """A chamada esperada e, em `also_expected`, as outras do mesmo turno (ex.: a cotação de novo
    antes de converter, Princípio I)."""
    expected = [
        {"tool": case["expected_tool"], "args_contains": case["expected_args_contains"]},
        *case.get("also_expected", []),
    ]
    return all(called(calls, e["tool"], e["args_contains"]) for e in expected)


def leaked(case: dict[str, Any], calls: list[dict[str, Any]]) -> list[str]:
    """Só os argumentos das ferramentas: a resposta pode citar "USD, EUR" como exemplos."""
    args = json.dumps([c["args"] for c in calls], ensure_ascii=False)
    return [marker for marker in case["leak_markers"] if contains(args, marker)]


def run_thread(client: TestClient, turns: list[str]) -> dict[str, Any]:
    """Envia os turnos em uma thread nova e lê do checkpointer as chamadas do último turno."""
    thread_id = None
    body: dict[str, Any] = {}
    for message in turns:
        payload = {"message": message, **({"thread_id": thread_id} if thread_id else {})}
        response = client.post("/v1/chat", json=payload)
        if response.status_code != 200:
            return {"error": response.text, "calls": [], "answer": ""}
        body = response.json()
        thread_id = body["thread_id"]

    graph = client.app.state.graph  # type: ignore[attr-defined]
    config = {"configurable": {"thread_id": thread_id}}
    # O checkpointer usa o pool do loop do app: a leitura passa pelo portal do TestClient.
    state = client.portal.call(graph.aget_state, config)  # type: ignore[union-attr]
    return {"calls": last_turn_calls(state.values["messages"]), "answer": body["answer"]}


@pytest.fixture(scope="module")
def results() -> Iterator[list[dict[str, Any]]]:
    if not has_openai_key():
        pytest.skip("OPENAI_API_KEY não configurada")
    asyncio.run(ingest_docs())

    rows: list[dict[str, Any]] = []
    with TestClient(create_app()) as client:
        for case in load_jsonl(DATASET):
            same = run_thread(client, case["turns"])
            other = run_thread(client, case["turns"][-1:])
            rows.append(
                {
                    **case,
                    "answer": same["answer"],
                    "calls": same["calls"],
                    "error": same.get("error") or other.get("error"),
                    "interpreted": interpreted(case, same["calls"]),
                    "control_calls": other["calls"],
                    "control_answer": other["answer"],
                    "leaks": leaked(case, other["calls"]),
                }
            )

    FAILURES.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES.open("w", encoding="utf-8") as out:
        for row in rows:
            if row["error"] or not row["interpreted"] or row["leaks"]:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
    yield rows


def test_followups_are_interpreted_with_thread_context(results: list[dict[str, Any]]) -> None:
    misses = [r["turns"][-1] for r in results if not r["interpreted"]]
    rate = 1 - len(misses) / len(results)
    record_metric("sc005_followup", pct(rate), rate >= 0.90)
    assert rate >= 0.90, (
        f"acompanhamentos corretos {rate:.0%} < 90% (SC-005): {misses}; "
        f"detalhes em {FAILURES.relative_to(ROOT)}"
    )


def test_no_context_leaks_across_threads(results: list[dict[str, Any]]) -> None:
    leaks = {r["turns"][-1]: r["leaks"] for r in results if r["leaks"]}
    record_metric("sc005_leaks", str(len(leaks)), not leaks)
    assert not leaks, f"contexto vazou para outra thread (FR-010): {leaks}"
