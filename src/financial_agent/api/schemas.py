"""Schemas da API conforme contracts/openapi.yaml."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from financial_agent.graph.state import SourceCitation

ScopeLabel = Literal["in_scope", "out_of_scope", "ambiguous"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    thread_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a mensagem não pode ser composta apenas de espaços")
        return value


class ChatResponse(BaseModel):
    thread_id: UUID
    answer: str
    scope: ScopeLabel
    sources: list[SourceCitation]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = None
    sources: list[SourceCitation] | None = None


class ThreadHistory(BaseModel):
    thread_id: UUID
    messages: list[ChatMessage]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorBody(BaseModel):
    error: ErrorDetail
