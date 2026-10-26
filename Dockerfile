FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Roda sem root. Os arquivos de /app continuam do root (só leitura para o app), e o bytecode já
# foi compilado no build.
RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "financial_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
