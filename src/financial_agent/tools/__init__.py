"""Registro das ferramentas do agente.

Cada ferramenta é criada por uma fábrica `make_<nome>_tool(...)` que fecha sobre suas
dependências e devolve o `@tool` com a docstring do contrato (contracts/tools.md).
Cada história registra sua fábrica em `get_tools`.
"""

from typing import Any

from langchain_core.tools import BaseTool

from financial_agent.config import Settings


def get_tools(
    settings: Settings,
    vectorstore: Any | None = None,
    http_client: Any | None = None,
) -> list[BaseTool]:
    tools: list[BaseTool] = []
    return tools
