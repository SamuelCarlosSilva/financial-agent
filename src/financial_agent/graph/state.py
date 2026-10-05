"""Estado do grafo e modelos de fontes citadas (data-model.md §3–§5)."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


class DocumentSource(BaseModel):
    type: Literal["document"] = "document"
    document_id: str
    title: str
    source: str
    page: int | None = None
    snippet: str = Field(max_length=300)
    score: float


class FxQuoteSource(BaseModel):
    type: Literal["fx_quote"] = "fx_quote"
    pair: str = Field(pattern=r"^[A-Z]{3}-[A-Z]{3}$")
    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)
    quoted_at: datetime
    provider: str


class CalculationSource(BaseModel):
    type: Literal["calculation"] = "calculation"
    expression: str = Field(max_length=200)
    result: Decimal


SourceCitation = Annotated[
    DocumentSource | FxQuoteSource | CalculationSource, Field(discriminator="type")
]


class ScopeDecision(BaseModel):
    """Decisão do guardrail sobre o escopo da mensagem do usuário."""

    label: Literal["in_scope", "out_of_scope", "ambiguous"]
    reason: str = Field(max_length=200)


class GraphState(MessagesState):
    scope: ScopeDecision | None
    # Fontes do turno atual; a rota envia [] a cada turno para zerar o valor anterior.
    turn_sources: list[SourceCitation]
