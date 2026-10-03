"""Juiz dos evals: parsing do structured output e agregação (sem OpenAI)."""

from langchain_core.messages import AIMessage

from tests.eval.judge import Claim, Verdict, aggregate, format_sources, judge
from tests.fakes import fake_llm


def verdict_call(**args: object) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "Verdict", "args": args, "id": "v1"}])


def test_judge_parses_structured_verdict() -> None:
    llm = fake_llm(
        verdict_call(
            claims=[
                {"text": "O dólar está R$ 5,10", "supported": True, "source_index": 0},
                {"text": "Vai subir amanhã", "supported": False, "source_index": None},
            ],
            language="pt-BR",
            has_partial_notice=False,
            has_advice_disclaimer=True,
            gives_buy_sell_order=False,
        )
    )
    sources = [{"type": "fx_quote", "pair": "USD-BRL", "bid": "5.10", "ask": "5.11"}]

    verdict = judge("O dólar está R$ 5,10.", sources, "Quanto está o dólar?", llm=llm)

    assert verdict.language == "pt-BR"
    assert verdict.has_advice_disclaimer
    assert not verdict.fully_supported
    assert [c.text for c in verdict.unsupported_claims] == ["Vai subir amanhã"]
    prompt = llm.calls[0][-1].content
    assert "<resposta>" in prompt and "USD-BRL" in prompt


def test_format_sources_includes_each_source_kind() -> None:
    text = format_sources(
        [
            {"type": "document", "title": "Come-cotas", "source": "cc.md", "snippet": "maio"},
            {"type": "fx_quote", "pair": "EUR-BRL", "bid": "6", "ask": "6.1", "quoted_at": "x"},
            {"type": "calculation", "expression": "2 * 3", "result": "6"},
        ]
    )

    assert text.splitlines() == [
        "[0] documento 'Come-cotas' (cc.md): maio",
        "[1] cotação EUR-BRL: compra (bid) 6, venda (ask) 6.1, em x",
        "[2] cálculo: 2 * 3 = 6",
    ]
    assert format_sources([]) == "(nenhuma fonte)"


def test_aggregate_rates() -> None:
    def make(language: str, *supported: bool) -> Verdict:
        return Verdict(
            claims=[Claim(text=str(i), supported=s) for i, s in enumerate(supported)],
            language=language,
            has_partial_notice=False,
            has_advice_disclaimer=False,
            gives_buy_sell_order=False,
        )

    result = aggregate([make("pt-BR", True, True), make("pt-BR", False), make("en-US")])

    assert (result.answers, result.claims, result.supported_claims) == (3, 3, 2)
    assert result.supported_rate == 2 / 3
    assert result.pt_br_rate == 2 / 3
    assert aggregate([]).supported_rate == 1.0
