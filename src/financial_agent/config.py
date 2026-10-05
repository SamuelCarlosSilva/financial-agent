"""Configuração da aplicação, lida de variáveis de ambiente e do `.env`."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI
    OPENAI_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = "gpt-4o-mini"
    GUARDRAIL_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_TIMEOUT_SECONDS: float = Field(default=30, gt=0)

    # Banco
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/financial_agent"

    # RAG
    RAG_MIN_SCORE: float = Field(default=0.35, ge=0, le=1)
    RAG_TOP_K: int = Field(default=4, ge=1)

    # Cotação de moedas
    FX_API_BASE_URL: str = "https://economia.awesomeapi.com.br"
    FX_TIMEOUT_SECONDS: float = Field(default=5, gt=0)

    # Retenção de conversas
    THREAD_RETENTION_DAYS: int = Field(default=30, ge=1)

    # Chaves da API (vazio = autenticação desativada). NoDecode evita o parsing como JSON.
    API_KEYS: Annotated[list[str], NoDecode] = Field(default_factory=list)

    LOG_LEVEL: str = "INFO"

    @field_validator("API_KEYS", mode="before")
    @classmethod
    def _split_api_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return [key.strip() for key in value.split(",") if key.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
