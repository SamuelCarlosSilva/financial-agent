"""Registro das ferramentas do agente.

Cada ferramenta é criada por uma fábrica `make_<nome>_tool(...)` que fecha sobre suas
dependências e devolve o `@tool` com a docstring do contrato (contracts/tools.md).
Cada história registra sua fábrica em `get_tools`.
"""

import httpx
from langchain_core.tools import BaseTool
from langchain_core.vectorstores import VectorStore

from financial_agent.config import Settings
from financial_agent.tools.calculator import make_calculator_tool
from financial_agent.tools.currency_quote import make_currency_quote_tool
from financial_agent.tools.document_search import make_search_tool


def get_tools(
    settings: Settings,
    vectorstore: VectorStore | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> list[BaseTool]:
    tools: list[BaseTool] = []
    if vectorstore is not None:
        tools.append(make_search_tool(vectorstore, settings))
    tools.append(make_currency_quote_tool(settings, http_client))
    tools.append(make_calculator_tool())
    return tools
