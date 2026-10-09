"""Ferramenta `calculate`: precisão decimal, erros e rejeição do que não for aritmética."""

from decimal import Decimal
from pathlib import Path

import pytest

from financial_agent.graph.state import CalculationSource
from financial_agent.tools import calculator
from financial_agent.tools.calculator import (
    DIVISION_BY_ZERO,
    INVALID_EXPRESSION,
    TOO_LARGE,
    make_calculator_tool,
)


async def calculate(expression: str) -> tuple[str, CalculationSource | None]:
    tool = make_calculator_tool()
    call = {"name": tool.name, "args": {"expression": expression}, "id": "c1", "type": "tool_call"}
    message = await tool.ainvoke(call)
    return message.content, message.artifact


@pytest.mark.parametrize(
    ("expression", "result"),
    [
        ("10000 * (1 + 0.01) ** 12", "11268.25"),
        ("2340 * 0.15", "351.00"),
        ("0.1 + 0.2", "0.30"),
        ("-5 + +2", "-3.00"),
        ("10 % 3", "1.00"),
        ("1000 * (1 + 0.1) ** -2", "826.45"),
        ("1_000 / 8", "125.00"),
        # Meio exato arredonda para o par (ROUND_HALF_EVEN).
        ("0.125 + 0", "0.12"),
        ("0.135 + 0", "0.14"),
    ],
)
async def test_exact_decimal_results(expression: str, result: str) -> None:
    content, artifact = await calculate(expression)

    assert content == f"{expression} = {result}"
    assert artifact == CalculationSource(expression=expression, result=Decimal(result))


@pytest.mark.parametrize("expression", ["1/0", "5 % 0", "1 / (2 - 2)"])
async def test_division_by_zero(expression: str) -> None:
    content, artifact = await calculate(expression)

    assert content.startswith(DIVISION_BY_ZERO)
    assert artifact is None


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "abs(1)",
        "x",
        "x + 1",
        "(1).real",
        "lambda: 1",
        "'a'",
        "'a' * 3",
        "True + 1",
        "1j",
        "2 // 1",
        "1 < 2",
        "[1, 2]",
        "1 +",
        "",
        "1, 2",
        "(-8) ** 0.5",
    ],
)
async def test_invalid_expressions(expression: str) -> None:
    content, artifact = await calculate(expression)

    assert content.startswith(INVALID_EXPRESSION)
    assert artifact is None


async def test_expression_longer_than_200_chars_is_rejected() -> None:
    expression = "1 + " * 50 + "1"
    assert len(expression) > 200

    content, artifact = await calculate(expression)

    assert content.startswith(INVALID_EXPRESSION)
    assert artifact is None


@pytest.mark.parametrize("expression", ["2 ** 1001", "2 ** -1001", "10 ** 999 * 10 ** 999 * 1e999"])
async def test_too_large(expression: str) -> None:
    content, artifact = await calculate(expression)

    assert content.startswith(TOO_LARGE)
    assert artifact is None


async def test_exponent_at_the_limit_is_allowed() -> None:
    _, artifact = await calculate("1.0001 ** 1000")

    assert artifact is not None
    assert artifact.result == Decimal("1.11")


def test_no_eval_or_exec() -> None:
    source = Path(calculator.__file__).read_text(encoding="utf-8")

    assert "eval(" not in source
    assert "exec(" not in source


def test_docstring_matches_contract() -> None:
    tool = make_calculator_tool()

    assert tool.name == "calculate"
    assert tool.description.startswith("Avalia uma expressão aritmética com precisão decimal")
    assert "Nunca calcule de cabeça." in tool.description
    assert "Exemplo juros compostos: 10000 * (1 + 0.01) ** 12" in tool.description
