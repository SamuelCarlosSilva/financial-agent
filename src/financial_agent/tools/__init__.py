"""Registro das ferramentas do agente.

Cada ferramenta é criada por uma fábrica `make_<nome>_tool(...)` que fecha sobre suas
dependências e devolve o `@tool` com a docstring do contrato (contracts/tools.md).
Cada história registra sua fábrica em `get_tools`.
"""

from typing import Any

from langchain_core.tools import BaseTool
from langchain_core.vectorstores import VectorStore

from financial_agent.config import Settings
from financial_agent.tools.document_search import make_search_tool


def get_tools(
    settings: Settings,
    vectorstore: VectorStore | None = None,
    http_client: Any | None = None,
) -> list[BaseTool]:
    tools: list[BaseTool] = []
    if vectorstore is not None:
        tools.append(make_search_tool(vectorstore, settings))
    return tools
