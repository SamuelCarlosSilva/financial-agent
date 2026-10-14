"""Allowlist do serializador do checkpointer: os tipos do estado voltam intactos, sem aviso."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from financial_agent.api.db import checkpoint_serializer
from financial_agent.graph.state import (
    CalculationSource,
    DocumentSource,
    FxQuoteSource,
    ScopeDecision,
)

STATE_VALUES = [
    ScopeDecision(label="in_scope", reason="pergunta sobre câmbio"),
    DocumentSource(
        document_id="d1", title="Come-cotas", source="come-cotas.md", snippet="...", score=0.8
    ),
    FxQuoteSource(
        pair="USD-BRL",
        bid=Decimal("5.4321"),
        ask=Decimal("5.4330"),
        quoted_at=datetime(2026, 10, 9, 19, 30, tzinfo=UTC),
        provider="awesomeapi",
    ),
    CalculationSource(expression="500 * 5.4321", result=Decimal("2716.05")),
    AIMessage("Resposta", additional_kwargs={"sources": []}),
]


class NotRegistered(BaseModel):
    value: int


@pytest.mark.parametrize("value", STATE_VALUES, ids=lambda v: type(v).__name__)
def test_state_types_round_trip_without_warning(
    value: BaseModel, caplog: pytest.LogCaptureFixture
) -> None:
    serde = checkpoint_serializer()

    with caplog.at_level(logging.WARNING):
        restored = serde.loads_typed(serde.dumps_typed(value))

    assert restored == value
    assert type(restored) is type(value)
    assert "allowed_msgpack_modules" not in caplog.text


def test_unregistered_type_is_blocked() -> None:
    serde = checkpoint_serializer()

    restored = serde.loads_typed(serde.dumps_typed(NotRegistered(value=1)))

    assert not isinstance(restored, NotRegistered)
