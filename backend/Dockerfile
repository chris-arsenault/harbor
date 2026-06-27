FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG HARBOR_GIT_SHA=unknown
ARG HARBOR_BUILD_TIME=unknown

LABEL org.opencontainers.image.title="Harbor Backend" \
    org.opencontainers.image.version="0.1.0" \
    org.opencontainers.image.revision="${HARBOR_GIT_SHA}" \
    org.opencontainers.image.created="${HARBOR_BUILD_TIME}"

ENV PATH="/app/.venv/bin:${PATH}" \
    HARBOR_GIT_SHA="${HARBOR_GIT_SHA}" \
    HARBOR_BUILD_TIME="${HARBOR_BUILD_TIME}" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY db ./db
COPY src ./src

RUN uv sync --frozen --no-dev
RUN date -u +"%Y-%m-%dT%H:%M:%SZ" > /app/.build_time

EXPOSE 8080

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn harbor_bot.api:app --host 0.0.0.0 --port 8080"]
