"""Ferramenta `get_currency_quote`: sucesso, par não suportado, indisponibilidade e validação."""

from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest
import respx

from financial_agent.config import Settings
from financial_agent.graph.state import FxQuoteSource
from financial_agent.tools.currency_quote import (
    INVALID_CODE,
    PROVIDER_UNAVAILABLE,
    UNSUPPORTED_PAIR,
    make_currency_quote_tool,
)

BASE_URL = "https://fx.test"

USD_BRL = {
    "USDBRL": {
        "code": "USD",
        "codein": "BRL",
        "name": "Dólar Americano/Real Brasileiro",
        "bid": "5.4321",
        "ask": "5.4351",
        "create_date": "2026-10-07 14:30:05",
    }
}


def settings() -> Settings:
    return Settings(FX_API_BASE_URL=BASE_URL, FX_TIMEOUT_SECONDS=5)


@pytest.fixture
def provider() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


async def quote(**args: Any) -> tuple[str, FxQuoteSource | None]:
    tool = make_currency_quote_tool(settings())
    call = {"name": tool.name, "args": args, "id": "c1", "type": "tool_call"}
    message = await tool.ainvoke(call)
    return message.content, message.artifact


async def test_success_returns_quote_and_artifact(provider: respx.MockRouter) -> None:
    provider.get("/json/last/USD-BRL").mock(return_value=httpx.Response(200, json=USD_BRL))

    content, artifact = await quote(base="USD")

    assert "USD-BRL" in content
    assert "5.4321" in content
    assert "5.4351" in content
    assert "2026-10-07T14:30:05-03:00" in content
    assert artifact == FxQuoteSource(
        pair="USD-BRL",
        bid=Decimal("5.4321"),
        ask=Decimal("5.4351"),
        quoted_at=datetime.fromisoformat("2026-10-07T14:30:05-03:00"),
        provider="awesomeapi",
    )
    assert artifact is not None
    assert artifact.quoted_at.utcoffset() is not None


async def test_unsupported_pair(provider: respx.MockRouter) -> None:
    provider.get("/json/last/XYZ-BRL").mock(
        return_value=httpx.Response(404, json={"status": 404, "code": "CoinNotExists"})
    )

    content, artifact = await quote(base="XYZ")

    assert content.startswith(UNSUPPORTED_PAIR)
    for example in ("USD", "EUR", "GBP", "JPY", "ARS", "BTC"):
        assert example in content
    assert artifact is None


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectTimeout("timeout"), httpx.Response(500), httpx.Response(503)],
    ids=["timeout", "500", "503"],
)
async def test_provider_unavailable_after_one_retry(
    provider: respx.MockRouter, failure: Any
) -> None:
    route = provider.get("/json/last/USD-BRL").mock(side_effect=[failure, failure])

    content, artifact = await quote(base="USD")

    assert content.startswith(PROVIDER_UNAVAILABLE)
    assert artifact is None
    assert route.call_count == 2


async def test_retry_recovers_from_a_single_failure(provider: respx.MockRouter) -> None:
    route = provider.get("/json/last/USD-BRL").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json=USD_BRL)]
    )

    content, artifact = await quote(base="USD")

    assert artifact is not None
    assert route.call_count == 2


async def test_malformed_response_is_unavailable(provider: respx.MockRouter) -> None:
    provider.get("/json/last/USD-BRL").mock(return_value=httpx.Response(200, json={}))

    content, artifact = await quote(base="USD")

    assert content.startswith(PROVIDER_UNAVAILABLE)
    assert artifact is None


@pytest.mark.parametrize(("base", "quote_code"), [("US", "BRL"), ("usd1", "BRL"), ("USD", "R$")])
async def test_invalid_codes_are_rejected_without_http(
    provider: respx.MockRouter, base: str, quote_code: str
) -> None:
    content, artifact = await quote(base=base, quote=quote_code)

    assert content.startswith(INVALID_CODE)
    assert artifact is None
    assert not provider.calls


async def test_lowercase_codes_are_normalized(provider: respx.MockRouter) -> None:
    route = provider.get("/json/last/USD-BRL").mock(return_value=httpx.Response(200, json=USD_BRL))

    _, artifact = await quote(base="usd", quote="brl")

    assert route.called
    assert artifact is not None
    assert artifact.pair == "USD-BRL"


async def test_uses_injected_http_client(provider: respx.MockRouter) -> None:
    provider.get("/json/last/EUR-BRL").mock(
        return_value=httpx.Response(
            200, json={"EURBRL": {**USD_BRL["USDBRL"], "code": "EUR", "bid": "6.1", "ask": "6.2"}}
        )
    )
    async with httpx.AsyncClient(timeout=5) as client:
        tool = make_currency_quote_tool(settings(), http_client=client)
        message = await tool.ainvoke(
            {"name": tool.name, "args": {"base": "EUR"}, "id": "c1", "type": "tool_call"}
        )

    assert message.artifact.pair == "EUR-BRL"


def test_docstring_matches_contract() -> None:
    tool = make_currency_quote_tool(settings())

    assert tool.name == "get_currency_quote"
    assert tool.description.startswith("Obtém a cotação atual (em tempo real) de um par de moedas.")
    assert "chame esta ferramenta e depois `calculate`" in tool.description
    assert "use o valor de compra (bid)" in tool.description
