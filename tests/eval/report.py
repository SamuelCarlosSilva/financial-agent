"""Relatório consolidado dos evals: SC-001..SC-006, FR-014 e aviso de recomendação.

Roda `pytest -m eval tests/eval` (LLM real: custa tokens) e imprime uma tabela PASS/FAIL com as
métricas que cada eval gravou em `tests/eval/out/metrics/`. Uma métrica que não foi gravada
(eval que não rodou ou quebrou antes do `assert`) aparece como "não medido" e conta como FAIL.

    uv run python -m tests.eval.report              # roda os evals e imprime a tabela
    uv run python -m tests.eval.report --no-run     # só imprime a tabela da última execução
"""

import argparse
import json
import shutil
import subprocess
import sys

from tests.eval.common import METRICS_DIR, ROOT

# (critério, métrica, meta, chave gravada por `record_metric`), na ordem da tabela.
CATALOG: list[tuple[str, str, str, str]] = [
    ("SC-001", "Mensagens fora de escopo recusadas", "≥ 95%", "sc001_refusal"),
    ("SC-001", "Mensagens financeiras recusadas por engano", "≤ 5%", "sc001_false_refusal"),
    ("SC-002", "Afirmações sustentadas pelas fontes", "100%", "sc002_supported"),
    ("SC-003", "Acerto nas perguntas respondíveis", "≥ 90%", "sc003_answerable"),
    ("SC-003", '"Não encontrei" nas perguntas sem resposta', "≥ 95%", "sc003_not_found"),
    ("SC-004", "Cálculos com o resultado esperado", "100%", "sc004_result"),
    ("SC-004", "Cálculos com fonte `calculation`", "100%", "sc004_source"),
    ("SC-005", "Acompanhamentos interpretados corretamente", "≥ 90%", "sc005_followup"),
    ("SC-005", "Vazamentos de contexto entre threads", "0", "sc005_leaks"),
    ("SC-006", "p95 das respostas completas", "≤ 10 s", "sc006_p95"),
    ("SC-006", "p95 com 20 requisições simultâneas, sem 5xx", "≤ 10 s", "sc006_load"),
    ("SC-006", "p95 das recusas de escopo", "≤ 3 s", "sc006_refusal_p95"),
    ("FR-014", "Respostas em pt-BR (fundamentação)", "100%", "fr014_grounding"),
    ("FR-014", "Respostas em pt-BR (escopo)", "100%", "fr014_scope"),
    ("Aviso", "Pedidos de recomendação com o aviso", "100%", "advice_disclaimer"),
    ("Aviso", "Respostas com ordem de compra ou venda", "0", "advice_orders"),
]
SC_007 = (
    "SC-007",
    "Histórico disponível após reinício",
    "100%",
    "coberto por tests/integration/test_thread_memory.py (T043)",
)


def run_evals() -> int:
    shutil.rmtree(METRICS_DIR, ignore_errors=True)
    command = [sys.executable, "-m", "pytest", "-m", "eval", "tests/eval", "-q"]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def load_metrics() -> dict[str, dict[str, object]]:
    if not METRICS_DIR.exists():
        return {}
    metrics = (json.loads(path.read_text("utf-8")) for path in METRICS_DIR.glob("*.json"))
    return {metric["key"]: metric for metric in metrics}


def build_rows(metrics: dict[str, dict[str, object]]) -> list[tuple[str, str, str, str, str]]:
    rows = []
    for criterion, name, target, key in CATALOG:
        metric = metrics.get(key)
        if metric is None:
            rows.append((criterion, name, target, "não medido", "FAIL"))
        else:
            status = "PASS" if metric["passed"] else "FAIL"
            rows.append((criterion, name, target, str(metric["result"]), status))
    rows.append((*SC_007, "—"))
    return rows


def render(rows: list[tuple[str, str, str, str, str]]) -> str:
    header = ("Critério", "Métrica", "Meta", "Resultado", "Status")
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]

    def line(cells: tuple[str, ...]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths, strict=True)) + " |"

    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    return "\n".join([line(header), separator, *(line(row) for row in rows)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--no-run", action="store_true", help="não roda os evals; usa as métricas já gravadas"
    )
    args = parser.parse_args()

    if not args.no_run:
        run_evals()

    rows = build_rows(load_metrics())
    print(render(rows))
    failed = [row for row in rows if row[4] == "FAIL"]
    print(f"\n{len(rows) - 1 - len(failed)} de {len(rows) - 1} metas atingidas.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
