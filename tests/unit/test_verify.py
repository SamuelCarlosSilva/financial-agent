"""Verificação de fundamentação: respostas com documentos citados conferidas contra os trechos."""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver

from financial_agent.graph.builder import build_graph
from financial_agent.graph.nodes.verify import GroundingCheck, make_grounding_verifier
from financial_agent.graph.prompts import NOT_FOUND_MESSAGE
from financial_agent.tools import get_tools
from tests.fakes import fake_llm
from tests.unit.test_chat_log import usage
from tests.unit.test_document_search import FakeVectorStore, doc, search_call, settings


class FakeChecker:
    """Verificador roteirizado: devolve (ou lança) cada veredito e registra as entradas."""

    def __init__(self, *verdicts: GroundingCheck | Exception) -> None:
        self.verdicts = list(verdicts)
        self.calls: list[Any] = []

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        async def check(messages: Any) -> GroundingCheck:
            self.calls.append(messages)
            verdict = self.verdicts.pop(0)
            if isinstance(verdict, Exception):
                raise verdict
            return verdict

        return RunnableLambda(check)


STORE = [(doc("A taxa Selic é definida pelo Copom.", "glossario.md", "Glossário"), 0.7)]


async def run(checker: FakeChecker, *responses: AIMessage) -> dict[str, Any]:
    llm = fake_llm(*responses)
    tools = get_tools(settings(), vectorstore=FakeVectorStore(STORE))  # type: ignore[arg-type]
    verifier = make_grounding_verifier(checker)  # type: ignore[arg-type]
    graph = build_graph(InMemorySaver(), llm, tools, verifier=verifier)
    return await graph.ainvoke(
        {"messages": [HumanMessage("O que é o IGP-M?")], "turn_sources": []},
        {"configurable": {"thread_id": "t1"}},
    )


def search_then(answer: str) -> tuple[AIMessage, AIMessage]:
    return AIMessage("", tool_calls=[search_call("IGP-M", "s1")]), AIMessage(answer)


async def test_unsupported_cited_answer_is_replaced_without_sources() -> None:
    checker = FakeChecker(GroundingCheck(supported=False, unsupported=["O IGP-M é da FGV."]))
    search, answer = search_then("O IGP-M é calculado pela FGV [1].")
    answer.usage_metadata = usage(120, 15)

    state = await run(checker, search, answer)

    replaced = state["messages"][-1]
    assert replaced.content == NOT_FOUND_MESSAGE
    # O uso de tokens da resposta descartada continua no log do turno.
    assert replaced.usage_metadata == usage(120, 15)
    assert state["turn_sources"] == []
    assert replaced.additional_kwargs["sources"] == []
    # O verificador recebe a pergunta, o trecho recuperado e a resposta.
    prompt = checker.calls[0][1].content
    assert "O que é o IGP-M?" in prompt
    assert "definida pelo Copom" in prompt
    assert "calculado pela FGV [1]" in prompt


async def test_supported_answer_is_kept() -> None:
    checker = FakeChecker(GroundingCheck(supported=True))

    state = await run(checker, *search_then("A Selic é definida pelo Copom [1]."))

    assert state["messages"][-1].content == "A Selic é definida pelo Copom [1]."
    assert [s.type for s in state["turn_sources"]] == ["document"]


async def test_answer_without_document_sources_is_not_checked() -> None:
    checker = FakeChecker()

    state = await run(checker, AIMessage("Olá! Como posso ajudar?"))

    assert state["messages"][-1].content == "Olá! Como posso ajudar?"
    assert checker.calls == []


async def test_checker_failure_keeps_the_answer() -> None:
    checker = FakeChecker(TimeoutError())

    state = await run(checker, *search_then("A Selic é definida pelo Copom [1]."))

    assert state["messages"][-1].content == "A Selic é definida pelo Copom [1]."
