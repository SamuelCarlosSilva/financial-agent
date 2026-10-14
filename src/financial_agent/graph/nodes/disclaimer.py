"""Aviso de recomendação: pedidos marcados pelo guardrail sempre saem com o aviso."""

from typing import Any

from langchain_core.messages import AIMessage

from financial_agent.graph.nodes.agent import current_turn
from financial_agent.graph.prompts import ADVICE_DISCLAIMER
from financial_agent.graph.state import GraphState
from financial_agent.logging import get_logger

log = get_logger(__name__)

# Trecho que identifica o aviso mesmo com outra pontuação ou maiúsculas.
_DISCLAIMER_CORE = "não constitui recomendação de investimento"


def add_advice_disclaimer(state: GraphState) -> dict[str, Any]:
    """Acrescenta o aviso à resposta final de um pedido de recomendação que saiu sem ele.

    O guardrail marca o pedido em `advice_request`. A regra 6 do prompt já pede o aviso, mas o
    modelo às vezes o omite; aqui ele é garantido no código.
    """
    if not state.get("advice_request"):
        return {}
    final = next(
        (m for m in reversed(current_turn(state["messages"])) if isinstance(m, AIMessage)), None
    )
    if final is None or _DISCLAIMER_CORE in final.text.casefold():
        return {}

    log.info("advice_disclaimer_added")
    # Mesmo id: o reducer `add_messages` substitui a resposta em vez de acrescentar outra.
    content = f"{final.text.rstrip()}\n\n{ADVICE_DISCLAIMER}"
    return {"messages": [final.model_copy(update={"content": content})]}
