"""Handlers de erro: toda falha sai no formato `Error` do contrato, com `request_id`."""

import openai
import psycopg
import psycopg_pool
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langgraph.errors import GraphRecursionError
from starlette.exceptions import HTTPException as StarletteHTTPException

from financial_agent.api.schemas import ErrorBody, ErrorDetail
from financial_agent.errors import UpstreamUnavailableError
from financial_agent.logging import get_logger, request_id_var

log = get_logger(__name__)


class NotFoundError(Exception):
    def __init__(self, message: str = "Recurso não encontrado.") -> None:
        super().__init__(message)
        self.message = message


class UnauthorizedError(Exception):
    def __init__(self, message: str = "X-API-Key ausente ou inválida.") -> None:
        super().__init__(message)
        self.message = message


# Falhas do provedor de LLM ou do banco viram 503 upstream_unavailable.
UPSTREAM_ERRORS: tuple[type[Exception], ...] = (
    UpstreamUnavailableError,
    openai.APIError,
    psycopg.OperationalError,
    psycopg_pool.PoolTimeout,
    TimeoutError,
)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorBody(error=ErrorDetail(code=code, message=message, request_id=request_id_var.get()))
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [".".join(str(part) for part in err["loc"]) for err in exc.errors()]
    message = "Entrada inválida: " + ", ".join(fields) if fields else "Entrada inválida."
    return error_response(422, "validation_error", message)


async def _not_found_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, NotFoundError)
    return error_response(404, "not_found", exc.message)


async def _unauthorized_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, UnauthorizedError)
    return error_response(401, "unauthorized", exc.message)


async def _upstream_handler(_: Request, exc: Exception) -> JSONResponse:
    log.warning("upstream_unavailable", error_type=type(exc).__name__)
    return error_response(503, "upstream_unavailable", "Serviço temporariamente indisponível.")


async def _recursion_handler(_: Request, exc: Exception) -> JSONResponse:
    # O agente é limitado por MAX_TOOL_ROUNDS; chegar aqui indica um laço inesperado no grafo.
    log.error("graph_recursion_limit", error_type=type(exc).__name__)
    return error_response(503, "upstream_unavailable", "Serviço temporariamente indisponível.")


async def _http_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = "not_found" if exc.status_code == 404 else "http_error"
    return error_response(exc.status_code, code, str(exc.detail))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.add_exception_handler(UnauthorizedError, _unauthorized_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(GraphRecursionError, _recursion_handler)
    for exc_type in UPSTREAM_ERRORS:
        app.add_exception_handler(exc_type, _upstream_handler)
