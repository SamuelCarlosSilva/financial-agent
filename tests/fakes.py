"""Fakes compartilhados pelos testes (sem rede, sem OpenAI)."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool

from financial_agent.graph.state import ScopeDecision


class FakeToolChatModel(FakeMessagesListChatModel):
    """Chat model roteirizado que aceita `bind_tools` e registra cada entrada recebida."""

    calls: list[list[BaseMessage]] = []

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        self.calls.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def fake_llm(*responses: BaseMessage) -> FakeToolChatModel:
    return FakeToolChatModel(responses=list(responses), calls=[])


class FakeScopeModel(FakeToolChatModel):
    """Classificador roteirizado: `with_structured_output` devolve (ou lança) cada decisão."""

    decisions: list[ScopeDecision | Exception] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        def classify(messages: list[BaseMessage]) -> ScopeDecision:
            self.calls.append(list(messages))
            decision = self.decisions.pop(0)
            if isinstance(decision, Exception):
                raise decision
            return decision

        return RunnableLambda(classify)


def fake_guardrail(*decisions: ScopeDecision | Exception) -> FakeScopeModel:
    return FakeScopeModel(responses=[], calls=[], decisions=list(decisions))
