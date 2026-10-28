"""Guardrail de escopo: classifica a mensagem antes de qualquer ferramenta (Princípio II)."""

import asyncio
import re
from collections.abc import Sequence
from typing import Any, Literal, Protocol

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from financial_agent.errors import UpstreamUnavailableError
from financial_agent.graph.prompts import ADVICE_CHECK_PROMPT, GUARDRAIL_SYSTEM_PROMPT
from financial_agent.graph.state import AdviceCheck, GraphState, ScopeDecision
from financial_agent.logging import get_logger, truncate

log = get_logger(__name__)

# Trocas anteriores enviadas ao classificador, para que acompanhamentos como "E o euro?"
# não sejam recusados.
HISTORY_EXCHANGES = 2
HISTORY_MESSAGE_CHARS = 500

# O texto do usuário não pode abrir nem fechar os delimitadores do prompt.
_DELIMITER = re.compile(r"<\s*/?\s*(?:mensagem_usuario|historico)\s*>", re.IGNORECASE)


class GuardrailNode(Protocol):
    async def __call__(self, state: GraphState) -> dict[str, Any]: ...


def _clean(text: str) -> str:
    return _DELIMITER.sub("", text).strip()


def _history(messages: Sequence[BaseMessage]) -> list[tuple[str, str]]:
    """Últimas trocas como (papel, texto), sem `ToolMessage` nem chamadas de ferramenta."""
    exchanges: list[list[tuple[str, str]]] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            exchanges.append([("Usuário", message.text)])
        elif isinstance(message, AIMessage) and message.text and not message.tool_calls:
            if exchanges:
                exchanges[-1].append(("Assistente", message.text))
    return [line for exchange in exchanges[-HISTORY_EXCHANGES:] for line in exchange]


def classifier_input(messages: Sequence[BaseMessage]) -> str:
    """Monta a entrada do classificador: histórico curto e a mensagem atual, delimitados."""
    last = next(
        i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)
    )
    parts = []
    history = _history(messages[:last])
    if history:
        lines = [
            f"{role}: {_clean(truncate(text, HISTORY_MESSAGE_CHARS))}" for role, text in history
        ]
        parts.append("<historico>\n" + "\n".join(lines) + "\n</historico>")
    parts.append(f"<mensagem_usuario>\n{_clean(messages[last].text)}\n</mensagem_usuario>")
    return "\n\n".join(parts)


def make_guardrail_node(llm: BaseChatModel) -> GuardrailNode:
    classifier = llm.with_structured_output(ScopeDecision)
    advice_classifier = llm.with_structured_output(AdviceCheck)

    async def classify(user_input: str) -> ScopeDecision:
        prompt = [SystemMessage(GUARDRAIL_SYSTEM_PROMPT), HumanMessage(user_input)]
        try:
            decision = await classifier.ainvoke(prompt)
            if not isinstance(decision, ScopeDecision):
                decision = ScopeDecision.model_validate(decision)
        except Exception as exc:
            # Nenhuma ferramenta roda sem uma classificação válida, mas a falha sai como
            # indisponibilidade (503), e não como uma recusa que parece intencional (FR-012).
            log.warning("guardrail_error", error=type(exc).__name__)
            raise UpstreamUnavailableError() from exc
        return decision

    async def is_advice_request(user_input: str) -> bool:
        prompt = [SystemMessage(ADVICE_CHECK_PROMPT), HumanMessage(user_input)]
        try:
            check = await advice_classifier.ainvoke(prompt)
            if not isinstance(check, AdviceCheck):
                check = AdviceCheck.model_validate(check)
        except Exception as exc:
            # Sem a marcação, o aviso ainda vem da regra 6 do prompt do agente.
            log.warning("advice_check_error", error=type(exc).__name__)
            return False
        return check.advice_request

    async def guardrail(state: GraphState) -> dict[str, Any]:
        user_input = classifier_input(state["messages"])
        # Em paralelo: a checagem de recomendação não aumenta a latência do guardrail.
        decision, advice_request = await asyncio.gather(
            classify(user_input), is_advice_request(user_input)
        )
        return {"scope": decision, "advice_request": advice_request, "turn_sources": []}

    return guardrail


def route_after_guardrail(state: GraphState) -> Literal["agent", "refuse", "clarify"]:
    scope = state.get("scope")
    if scope is None or scope.label == "out_of_scope":
        return "refuse"
    if scope.label == "ambiguous":
        return "clarify"
    return "agent"
