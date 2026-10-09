"""Calculadora aritmética com precisão decimal, sem `eval` (contracts/tools.md)."""

import ast
import inspect
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, Overflow, localcontext

from langchain_core.tools import BaseTool, tool

from financial_agent.graph.state import CalculationSource

TOOL_NAME = "calculate"

DIVISION_BY_ZERO = "DIVISAO_POR_ZERO"
INVALID_EXPRESSION = "EXPRESSAO_INVALIDA"
TOO_LARGE = "VALOR_MUITO_GRANDE"

MAX_LENGTH = 200
MAX_EXPONENT = 1000
PRECISION = 28
CENTS = Decimal("0.01")


class _DivisionByZero(Exception):
    pass


class _Invalid(Exception):
    pass


class _TooLarge(Exception):
    pass


class _Evaluator:
    """Avalia só a whitelist de nós; qualquer outro nó da AST é rejeitado."""

    def __init__(self, source: str) -> None:
        self.source = source

    def visit(self, node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Constant):
            return self._number(node)
        if isinstance(node, ast.UnaryOp):
            operand = self.visit(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
        if isinstance(node, ast.BinOp):
            return self._binary(node)
        raise _Invalid(type(node).__name__)

    def _number(self, node: ast.Constant) -> Decimal:
        # `bool` é subclasse de `int`; `complex` e strings ficam de fora.
        if type(node.value) not in (int, float):
            raise _Invalid(type(node.value).__name__)
        # O texto do literal evita o erro binário do float (0.1 vira exatamente 0.1).
        literal = ast.get_source_segment(self.source, node)
        if literal is None:
            raise _Invalid("literal")
        return Decimal(literal)

    def _binary(self, node: ast.BinOp) -> Decimal:
        left, right = self.visit(node.left), self.visit(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div | ast.Mod):
            # O `Decimal` sinaliza `x % 0` como operação inválida; aqui é divisão por zero.
            if right == 0:
                raise _DivisionByZero
            return left / right if isinstance(op, ast.Div) else left % right
        if isinstance(op, ast.Pow):
            if abs(right) > MAX_EXPONENT:
                raise _TooLarge
            return left**right
        raise _Invalid(type(op).__name__)


def evaluate(expression: str) -> Decimal:
    """Resultado arredondado para 2 casas (ROUND_HALF_EVEN). Lança as exceções internas."""
    if len(expression) > MAX_LENGTH:
        raise _Invalid("tamanho")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise _Invalid("sintaxe") from exc

    with localcontext() as ctx:
        ctx.prec = PRECISION
        try:
            result = _Evaluator(expression).visit(tree)
            # Sem casas decimais suficientes na precisão, o `quantize` falharia.
            if result.adjusted() >= PRECISION - 2:
                raise _TooLarge
            return result.quantize(CENTS, rounding=ROUND_HALF_EVEN)
        except Overflow as exc:
            raise _TooLarge from exc
        except (InvalidOperation, RecursionError) as exc:
            raise _Invalid("operação") from exc


def make_calculator_tool() -> BaseTool:
    @tool(response_format="content_and_artifact")
    def calculate(expression: str) -> tuple[str, CalculationSource | None]:
        """Avalia uma expressão aritmética com precisão decimal exata.

        Use para QUALQUER número que precise ser calculado (conversões,
        juros, percentuais, parcelas). Nunca calcule de cabeça.

        Operadores suportados: + - * / ** % e parênteses. Use ponto como
        separador decimal e escreva percentuais como fração (15% → 0.15).
        Exemplo juros compostos: 10000 * (1 + 0.01) ** 12

        Args:
            expression: expressão aritmética (máx. 200 caracteres).

        Returns:
            "expressão = resultado" com o resultado arredondado para 2 casas
            decimais, ou mensagem de erro (divisão por zero, expressão inválida).
        """
        expression = expression.strip()
        try:
            result = evaluate(expression)
        except _DivisionByZero:
            return f"{DIVISION_BY_ZERO}: a expressão divide por zero e não tem resultado.", None
        except _TooLarge:
            return (
                f"{TOO_LARGE}: o resultado é grande demais. Use expoentes de até "
                f"{MAX_EXPONENT} e valores menores.",
                None,
            )
        except _Invalid:
            return (
                f"{INVALID_EXPRESSION}: use só números, + - * / ** %, parênteses e ponto "
                f"decimal, com até {MAX_LENGTH} caracteres. Exemplo: 10000 * (1 + 0.01) ** 12",
                None,
            )
        return f"{expression} = {result}", CalculationSource(expression=expression, result=result)

    # Remove a indentação da docstring na descrição enviada ao LLM.
    calculate.description = inspect.cleandoc(calculate.description)
    return calculate
