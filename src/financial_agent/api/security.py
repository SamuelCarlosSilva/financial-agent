"""Autenticação opcional por `X-API-Key` (ativa só quando `API_KEYS` está definido)."""

import secrets
from typing import Annotated

from fastapi import Depends, Header

from financial_agent.api.errors import UnauthorizedError
from financial_agent.config import Settings, get_settings


async def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.API_KEYS:
        return
    if x_api_key is None or not any(
        secrets.compare_digest(x_api_key, key) for key in settings.API_KEYS
    ):
        raise UnauthorizedError()
