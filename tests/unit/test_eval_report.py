"""Relatório consolidado dos evals: montagem da tabela, sem rodar o LLM."""

from tests.eval.report import CATALOG, build_rows, render


def test_missing_metric_counts_as_fail() -> None:
    rows = build_rows({})

    assert all(row[3] == "não medido" and row[4] == "FAIL" for row in rows[:-1])
    assert rows[-1][0] == "SC-007"


def test_recorded_metrics_fill_result_and_status() -> None:
    metrics = {
        "sc001_refusal": {"key": "sc001_refusal", "result": "97,7%", "passed": True},
        "sc005_leaks": {"key": "sc005_leaks", "result": "1", "passed": False},
    }

    rows = {row[1]: row for row in build_rows(metrics)}

    assert rows["Mensagens fora de escopo recusadas"][3:] == ("97,7%", "PASS")
    assert rows["Vazamentos de contexto entre threads"][3:] == ("1", "FAIL")


def test_table_has_one_line_per_metric_plus_header() -> None:
    table = render(build_rows({}))

    assert table.count("\n") == len(CATALOG) + 2
    assert table.splitlines()[0].startswith("| Critério")
