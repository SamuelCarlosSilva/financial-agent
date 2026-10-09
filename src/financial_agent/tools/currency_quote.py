"""Ferramenta de cotação de moedas em tempo real (AwesomeAPI), contracts/tools.md."""

import inspect
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from langchain_core.tools import BaseTool, tool

from financial_agent.config import Settings
from financial_agent.graph.state import FxQuoteSource
from financial_agent.logging import get_logger

log = get_logger(__name__)

TOOL_NAME = "get_currency_quote"
PROVIDER = "awesomeapi"

UNSUPPORTED_PAIR = "PAR_NAO_SUPORTADO"
PROVIDER_UNAVAILABLE = "PROVEDOR_INDISPONIVEL"
INVALID_CODE = "CODIGO_INVALIDO"
SUPPORTED_EXAMPLES = "USD, EUR, GBP, JPY, ARS, BTC"

# Uma nova tentativa em timeout, falha de conexão ou 5xx.
ATTEMPTS = 2

# A AwesomeAPI informa `create_date` no horário de Brasília, sem fuso.
PROVIDER_TZ = ZoneInfo("America/Sao_Paulo")

_CODE = re.compile(r"^[A-Z]{3}$")


class _Unavailable(Exception):
    pass


class _UnsupportedPair(Exception):
    pass


def _parse(payload: Any, base: str, quote: str) -> FxQuoteSource:
    try:
        data = payload[f"{base}{quote}"]
        created = datetime.strptime(data["create_date"], "%Y-%m-%d %H:%M:%S")
        return FxQuoteSource(
            pair=f"{base}-{quote}",
            bid=Decimal(data["bid"]),
            ask=Decimal(data["ask"]),
            quoted_at=created.replace(tzinfo=PROVIDER_TZ),
            provider=PROVIDER,
        )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise _Unavailable("resposta inesperada do provedor") from exc


async def _fetch(client: httpx.AsyncClient, base_url: str, base: str, quote: str) -> Any:
    url = f"{base_url.rstrip('/')}/json/last/{base}-{quote}"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = await client.get(url)
        except httpx.TransportError as exc:
            log.warning("fx_request_failed", attempt=attempt, error=type(exc).__name__)
            continue
        if response.status_code == 404:
            raise _UnsupportedPair
        if response.status_code >= 500:
            log.warning("fx_request_failed", attempt=attempt, status=response.status_code)
            continue
        if response.status_code != 200:
            raise _Unavailable(f"status {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise _Unavailable("resposta não é JSON") from exc
    raise _Unavailable("tentativas esgotadas")


def _content(source: FxQuoteSource) -> str:
    return (
        f"Par: {source.pair}\n"
        f"Compra (bid): {source.bid}\n"
        f"Venda (ask): {source.ask}\n"
        f"Data/hora da cotação: {source.quoted_at.isoformat()} (horário de Brasília)\n"
        "Fonte: AwesomeAPI"
    )


def make_currency_quote_tool(
    settings: Settings, http_client: httpx.AsyncClient | None = None
) -> BaseTool:
    @tool(response_format="content_and_artifact")
    async def get_currency_quote(base: str, quote: str = "BRL") -> tuple[str, FxQuoteSource | None]:
        """Obtém a cotação atual (em tempo real) de um par de moedas.

        Use sempre que o usuário pedir valor de moeda ou conversão cambial;
        para converter um montante, chame esta ferramenta e depois `calculate`.
        Para conversões, use o valor de compra (bid) e informe isso ao usuário.

        Args:
            base: código ISO 4217 da moeda de origem (ex.: "USD", "EUR").
            quote: código ISO 4217 da moeda de destino. Padrão "BRL".

        Returns:
            Par, valor de compra (bid), venda (ask) e data/hora da cotação;
            ou mensagem de erro se o par não for suportado ou o provedor
            estiver indisponível.
        """
        base, quote = base.strip().upper(), quote.strip().upper()
        if not (_CODE.match(base) and _CODE.match(quote)):
            return (
                f"{INVALID_CODE}: use códigos ISO 4217 de 3 letras, por exemplo "
                f"{SUPPORTED_EXAMPLES}.",
                None,
            )

        try:
            if http_client is not None:
                payload = await _fetch(http_client, settings.FX_API_BASE_URL, base, quote)
            else:
                async with httpx.AsyncClient(timeout=settings.FX_TIMEOUT_SECONDS) as client:
                    payload = await _fetch(client, settings.FX_API_BASE_URL, base, quote)
            source = _parse(payload, base, quote)
        except _UnsupportedPair:
            return (
                f"{UNSUPPORTED_PAIR}: o par {base}-{quote} não é suportado. Exemplos de moedas "
                f"suportadas: {SUPPORTED_EXAMPLES}.",
                None,
            )
        except _Unavailable as exc:
            log.warning("fx_unavailable", pair=f"{base}-{quote}", reason=str(exc))
            return (
                f"{PROVIDER_UNAVAILABLE}: a cotação de {base}-{quote} está indisponível no "
                "momento. Não informe nem estime valores.",
                None,
            )
        return _content(source), source

    # Remove a indentação da docstring na descrição enviada ao LLM.
    get_currency_quote.description = inspect.cleandoc(get_currency_quote.description)
    return get_currency_quote
