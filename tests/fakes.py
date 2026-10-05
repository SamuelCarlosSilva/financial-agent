"""Fakes compartilhados pelos testes (sem rede, sem OpenAI)."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


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
