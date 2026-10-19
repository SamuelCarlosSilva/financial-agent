"""Verificação de fundamentação: resposta com trechos citados que não a sustentam não sai."""

from typing import Any, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from financial_agent.graph.nodes.agent import current_turn
from financial_agent.graph.prompts import GROUNDING_CHECK_PROMPT, NOT_FOUND_MESSAGE
from financial_agent.graph.state import GraphState, history_metadata
from financial_agent.logging import get_logger, truncate

log = get_logger(__name__)


class GroundingCheck(BaseModel):
    """Veredito do verificador sobre a resposta do agente."""

    supported: bool
    unsupported: list[str] = Field(default_factory=list)


class VerifierNode(Protocol):
    async def __call__(self, state: GraphState) -> dict[str, Any]: ...


def verifier_input(state: GraphState) -> str | None:
    """Pergunta, resultados das ferramentas do turno e resposta; `None` se não há o que conferir.

    Só respostas com trecho de documento citado passam pela verificação: cotação e cálculo já
    saem prontos das ferramentas.
    """
    if not any(source.type == "document" for source in state.get("turn_sources") or []):
        return None
    messages = state["messages"]
    turn = current_turn(messages)
    final = next((m for m in reversed(turn) if isinstance(m, AIMessage)), None)
    if final is None:
        return None
    start = len(messages) - len(turn)
    question = messages[start - 1].text if start > 0 else ""
    results = "\n\n".join(m.text for m in turn if isinstance(m, ToolMessage))
    return (
        f"<pergunta>\n{question}\n</pergunta>\n\n"
        f"<resultados_ferramentas>\n{results}\n</resultados_ferramentas>\n\n"
        f"<resposta>\n{final.text}\n</resposta>"
    )


def make_grounding_verifier(llm: BaseChatModel) -> VerifierNode:
    checker = llm.with_structured_output(GroundingCheck)

    async def verify_grounding(state: GraphState) -> dict[str, Any]:
        """Troca pela mensagem padrão a resposta com afirmações que os trechos não sustentam.

        A busca pode trazer trechos parecidos com a pergunta sem respondê-la, e o agente às vezes
        responde de cabeça citando esses trechos (SC-002). Se o verificador falhar, a resposta
        segue como está: ela já passou pela trava de citação de `enforce_grounding`.
        """
        prompt = verifier_input(state)
        if prompt is None:
            return {}
        try:
            check = await checker.ainvoke(
                [SystemMessage(GROUNDING_CHECK_PROMPT), HumanMessage(prompt)]
            )
            if not isinstance(check, GroundingCheck):
                check = GroundingCheck.model_validate(check)
        except Exception as exc:
            log.warning("grounding_check_error", error=type(exc).__name__)
            return {}
        if check.supported:
            return {}

        final = next(
            m for m in reversed(current_turn(state["messages"])) if isinstance(m, AIMessage)
        )
        log.warning(
            "unsupported_answer_replaced",
            answer=truncate(final.text),
            unsupported=[truncate(claim) for claim in check.unsupported],
        )
        # Mesmo id: o reducer `add_messages` substitui a resposta em vez de acrescentar outra.
        # Sem fontes: a mensagem padrão não se apoia nos trechos que foram descartados.
        replacement = AIMessage(
            content=NOT_FOUND_MESSAGE,
            id=final.id,
            additional_kwargs=history_metadata(),
            usage_metadata=final.usage_metadata,
        )
        return {"messages": [replacement], "turn_sources": []}

    return verify_grounding
