FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PATH="/app/.venv/bin:${PATH}" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY db ./db
COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn harbor_bot.api:app --host 0.0.0.0 --port 8080"]
