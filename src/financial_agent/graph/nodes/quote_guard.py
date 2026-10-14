"""Trava de cotação: cálculo com a cotação de um turno anterior não roda (Princípio I)."""

import re
from collections.abc import Iterable, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from financial_agent.graph.nodes.agent import current_turn, to_sources
from financial_agent.graph.state import GraphState
from financial_agent.logging import get_logger
from financial_agent.tools.calculator import TOOL_NAME as CALC_TOOL
from financial_agent.tools.currency_quote import TOOL_NAME as QUOTE_TOOL

log = get_logger(__name__)

STALE_QUOTE = "COTACAO_DE_TURNO_ANTERIOR"
NOT_RUN = "CHAMADA_NAO_EXECUTADA"

# Números como 5.5831, 5,5831 ou 500. O usuário pode escrever a cotação com vírgula.
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[Decimal]:
    values: set[Decimal] = set()
    for literal in _NUMBER.findall(text):
        try:
            values.add(Decimal(literal.replace(",", ".")))
        except InvalidOperation:
            continue
    return values


def _quote_values(messages: Iterable[BaseMessage]) -> set[Decimal]:
    """Compra e venda das cotações devolvidas por `get_currency_quote` nessas mensagens.

    Lido do checkpoint, o artefato de um turno anterior volta como `dict`; `to_sources` valida
    os dois formatos.
    """
    values: set[Decimal] = set()
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        for source in to_sources(message.artifact):
            if source.type == "fx_quote":
                values |= {source.bid, source.ask}
    return values


def stale_values(messages: Sequence[BaseMessage], expression: str) -> set[Decimal]:
    """Cotações de turnos anteriores usadas na expressão sem terem sido consultadas de novo.

    Um valor que o usuário escreveu na pergunta atual é dele (regra 4 do prompt) e passa.
    """
    turn = current_turn(messages)
    start = len(messages) - len(turn)
    question = messages[start - 1].text if start > 0 else ""
    earlier = _quote_values(messages[:start]) - _quote_values(turn)
    return (_numbers(expression) & earlier) - _numbers(question)


def guard_stale_quotes(state: GraphState) -> dict[str, Any]:
    """Responde às chamadas da rodada sem executá-las quando um `calculate` usa cotação antiga.

    O agente recebe o erro como resultado da ferramenta e volta a consultar a cotação neste
    turno; assim a conversão sai com a fonte `fx_quote` em `sources`. Como o `ToolNode` executa
    todas as chamadas da mensagem, as outras chamadas da rodada também são respondidas.
    """
    messages = state["messages"]
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return {}

    stale = {
        call["id"]: stale_values(messages, str(call["args"].get("expression", "")))
        for call in last.tool_calls
        if call["name"] == CALC_TOOL
    }
    stale = {call_id: values for call_id, values in stale.items() if values}
    if not stale:
        return {}

    log.warning("stale_quote_blocked", values=sorted(str(v) for vs in stale.values() for v in vs))
    replies = []
    for call in last.tool_calls:
        if call["id"] in stale:
            used = ", ".join(sorted(str(v) for v in stale[call["id"]]))
            content = (
                f"{STALE_QUOTE}: a expressão usa a cotação {used}, de um turno anterior. Chame "
                f"`{QUOTE_TOOL}` neste turno e refaça o cálculo com o valor de compra (bid) novo."
            )
        else:
            content = (
                f"{NOT_RUN}: outra chamada desta rodada usou uma cotação de um turno anterior. "
                "Refaça esta chamada se ainda for necessária."
            )
        replies.append(ToolMessage(content, tool_call_id=call["id"], name=call["name"]))
    return {"messages": replies}


def route_after_quote_guard(state: GraphState) -> Literal["tools", "agent"]:
    """Chamadas já respondidas pela trava voltam ao agente; as demais seguem para as ferramentas."""
    return "agent" if isinstance(state["messages"][-1], ToolMessage) else "tools"
