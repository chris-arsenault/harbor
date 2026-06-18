# 0002 - Python FastAPI Backend

- Status: Accepted
- Date: 2026-06-16

## Context

The source specification calls for Python 3.12, asyncio, FastAPI, an async OANDA integration, pure strategy functions, a backtester, and Optuna optimization. The backend must run continuously on TrueNAS and expose REST plus WebSocket APIs to the dashboard.

## Decision

Harbor uses a Python 3.12 backend with FastAPI, asyncio, SQLAlchemy/Alembic, and `uv`-managed dependencies.

## Alternatives considered

- **Rust backend** - aligns strongly with many Ahara examples and binary packaging, but adds friction for strategy research, Optuna, and Python-centric trading/data libraries.
- **Node backend** - shares language with the frontend, but provides less advantage for numeric research and broker automation than Python.
- **Split services by module** - can isolate concerns, but increases deployment and state coordination before the single-strategy system proves useful.

## Consequences

The backend image needs Python-specific packaging that works with the Ahara TrueNAS workflow. The first scaffold milestone must make Python linting and tests explicit because the shared workflow only runs Python lint by default. Backend module boundaries must preserve the pure core and keep broker, persistence, and API adapters outside it.
