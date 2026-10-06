"""Juiz LLM dos evals: fundamentação das afirmações, idioma, aviso parcial e disclaimer."""

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

JUDGE_MODEL = "gpt-4o-mini"

JUDGE_SYSTEM_PROMPT = """\
Você avalia respostas de um assistente financeiro. Receberá a pergunta, a resposta e as \
fontes numeradas que o assistente usou.

1. Extraia cada afirmação factual da resposta (números, taxas, regras, cotações, datas). \
Para cada uma, marque `supported=true` somente se ela estiver sustentada por alguma fonte e \
informe `source_index` (base 0); caso contrário, `supported=false` e `source_index=null`. \
Não são afirmações factuais: dizer que não encontrou a informação ou que ela está \
indisponível, sugestões ao usuário (ex.: "consulte sua corretora"), ofertas de ajuda e a \
própria lista de fontes e o aviso de que a resposta não constitui recomendação de \
investimento. Não as inclua em `claims`.
2. `language`: idioma da resposta no formato ISO 639-1 com região (ex.: "pt-BR", "pt-PT", "en-US").
3. `has_partial_notice`: a resposta avisa que parte da pergunta foi ignorada por estar fora \
do escopo financeiro?
4. `has_advice_disclaimer`: a resposta avisa que não constitui recomendação de investimento?
5. `gives_buy_sell_order`: a resposta manda comprar ou vender um ativo específico?
"""


class Claim(BaseModel):
    text: str
    supported: bool
    source_index: int | None = None


class Verdict(BaseModel):
    """Avaliação estruturada de uma resposta do assistente."""

    claims: list[Claim] = Field(default_factory=list)
    language: str
    has_partial_notice: bool
    has_advice_disclaimer: bool
    gives_buy_sell_order: bool

    @property
    def unsupported_claims(self) -> list[Claim]:
        return [claim for claim in self.claims if not claim.supported]

    @property
    def fully_supported(self) -> bool:
        return not self.unsupported_claims


class Aggregate(BaseModel):
    answers: int
    claims: int
    supported_claims: int
    supported_rate: float
    pt_br_rate: float


def format_sources(sources: Sequence[dict[str, Any]]) -> str:
    """Texto das fontes para o juiz: trechos, valores de cotação e resultados de cálculo."""
    if not sources:
        return "(nenhuma fonte)"
    lines = []
    for index, source in enumerate(sources):
        kind = source.get("type")
        if kind == "document":
            body = (
                f"documento '{source.get('title')}' ({source.get('source')}): "
                f"{source.get('snippet')}"
            )
        elif kind == "fx_quote":
            body = (
                f"cotação {source.get('pair')}: compra (bid) {source.get('bid')}, "
                f"venda (ask) {source.get('ask')}, em {source.get('quoted_at')}"
            )
        elif kind == "calculation":
            body = f"cálculo: {source.get('expression')} = {source.get('result')}"
        else:
            body = json.dumps(source, ensure_ascii=False, default=str)
        lines.append(f"[{index}] {body}")
    return "\n".join(lines)


def default_judge_llm() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    from financial_agent.config import get_settings

    # A chave vem do Settings (que lê o `.env`), como no app; o SDK só olharia o ambiente.
    return ChatOpenAI(model=JUDGE_MODEL, temperature=0, api_key=get_settings().OPENAI_API_KEY)


def judge(
    answer: str,
    sources: Sequence[dict[str, Any]],
    question: str,
    llm: BaseChatModel | None = None,
) -> Verdict:
    model = (llm or default_judge_llm()).with_structured_output(Verdict)
    prompt = (
        f"<pergunta>\n{question}\n</pergunta>\n\n"
        f"<resposta>\n{answer}\n</resposta>\n\n"
        f"<fontes>\n{format_sources(sources)}\n</fontes>"
    )
    result = model.invoke([SystemMessage(JUDGE_SYSTEM_PROMPT), HumanMessage(prompt)])
    if not isinstance(result, Verdict):
        result = Verdict.model_validate(result)
    return result


def aggregate(verdicts: Sequence[Verdict]) -> Aggregate:
    claims = [claim for verdict in verdicts for claim in verdict.claims]
    supported = sum(claim.supported for claim in claims)
    pt_br = sum(verdict.language == "pt-BR" for verdict in verdicts)
    return Aggregate(
        answers=len(verdicts),
        claims=len(claims),
        supported_claims=supported,
        supported_rate=supported / len(claims) if claims else 1.0,
        pt_br_rate=pt_br / len(verdicts) if verdicts else 1.0,
    )
