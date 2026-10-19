"""Trava de fundamentação: resposta sem fonte no turno, após busca ou citando trechos, não sai."""

from typing import Any

from langchain_core.messages import AIMessage

from financial_agent.graph.nodes.agent import cited_markers, current_turn
from financial_agent.graph.prompts import NOT_FOUND_MESSAGE
from financial_agent.graph.state import GraphState
from financial_agent.logging import get_logger, truncate
from financial_agent.tools.document_search import TOOL_NAME as SEARCH_TOOL

log = get_logger(__name__)


def enforce_grounding(state: GraphState) -> dict[str, Any]:
    """Troca pela mensagem padrão a resposta sem fontes de um turno que buscou ou citou trechos.

    Sem trecho citado e sem outra fonte (cotação, cálculo), o que o agente afirmou não veio das
    ferramentas: ou ele não encontrou a informação, ou respondeu de cabeça. Também vale para
    uma resposta que cita [n] sem ter buscado neste turno: o trecho é de um turno anterior e
    não seria devolvido em `sources`. Roda depois de `collect_sources`, que só mantém os trechos
    citados.
    """
    turn = current_turn(state["messages"])
    searched = any(
        call["name"] == SEARCH_TOOL
        for message in turn
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    )
    final = next((m for m in reversed(turn) if isinstance(m, AIMessage)), None)
    if final is None or state.get("turn_sources"):
        return {}
    if not (searched or cited_markers(final.text)):
        return {}

    log.warning("ungrounded_answer_replaced", answer=truncate(final.text))
    # Mesmo id: o reducer `add_messages` substitui a resposta em vez de acrescentar outra.
    # Os `additional_kwargs` (fontes e horário do histórico) vêm de `collect_sources`.
    replacement = AIMessage(
        content=NOT_FOUND_MESSAGE,
        id=final.id,
        additional_kwargs=final.additional_kwargs,
        usage_metadata=final.usage_metadata,
    )
    return {"messages": [replacement]}
