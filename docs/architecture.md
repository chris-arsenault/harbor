# Architecture

Harbor runs as an Ahara TrueNAS LAN service at `http://192.168.66.3:30091/`. The deployable system consists of a Python backend container, a React frontend container, TrueNAS PostgreSQL state, and Ahara platform deployment through Komodo.

## Components

| Component | Current Role |
| ---- | ---- |
| Python backend | PostgreSQL persistence, raw OANDA read path, closed M1 candle ingestion, transaction stream framing, pure strategy decisions, deterministic backtester, persisted Backtests and Trades, offline optimizer/tuning studies, paper candidate variants, shadow paper engine, Lab APIs, Config diff/update/audit, structured Events, OANDA practice execution/reconciliation, guarded control endpoints, ntfy/Telegram notifier boundary, readiness, observability REST endpoints, and `/ws` |
| React frontend | Full product UI: Dashboard, Trades, Backtests, Lab optimizer workflow, Config, Events, and Operations. The UI signs users into the shared Ahara Cognito pool, sends the access token on REST/WebSocket calls, renders server-authored facts, launches experiments/tuning runs, handles guarded practice controls, and exposes LAN deployment/readiness facts without recomputing strategy or broker truth. |
| TrueNAS PostgreSQL | Durable candles, sessions, sweeps, FVGs, signals, trades, broker transactions, equity snapshots, events, config, backtests, optimization trials, variants, and variant trades |
| Ahara platform | CI, GHCR images, Komodo deploy, SSM-backed secrets, TrueNAS DB registration, and LAN-published TrueNAS compose |

The frontend container serves the LAN entrypoint, generates Cognito runtime config from SSM-backed environment variables, proxies `/api/` and `/ws` to the backend, exposes cheap `/health`, and proxies backend `/ready` for deployment smoke checks. Harbor does not publish a reverse-proxy route or public internet endpoint. `/api/*` and `/ws` require a valid Harbor Cognito app token; `/health`, `/ready`, and `/version` stay open for container health and deploy verification.

## Architecture Rules

- The pure strategy core is a deterministic function over closed-candle history, session levels, strategy state, risk context, instrument rules, and config.
- Runtime services adapt external concerns into the core: feed builds closed candles, risk can veto entries, the backtester simulates fills over recorded fixtures, the optimizer runs Optuna TPE trials through the backtester, the shadow paper engine runs paper variants over one closed-candle stream, and persistence records facts.
- Optimizer scoring is walk-forward and out-of-sample. M8 keeps live-forward data separation: optimizer paths read closed candles and optimizer tables without `variant_trades`; paper-forward reads active `variants` plus closed live candles; Lab live-forward scoring reads `variant_trades`.
- Server-side marker data is authoritative for the UI; the frontend renders overlays and does not recompute strategy signals.
- M7 observability is read-only. `GET /api/status`, `GET /api/levels`, `GET /api/candles`, `GET /api/markers`, `GET /api/events`, and `/ws` expose persisted/server-authored facts to the dashboard without broker calls, config mutation, trading-enable mutation, flatten actions, optimizer APIs, or live credentials.
- M8 Lab endpoints are `POST /api/optimize`, `GET /api/optimize/{study_id}`, `GET /api/variants`, `POST /api/variants`, and `POST /api/variants/{variant_id}/retire`. They are paper-only and do not expose live config promotion, OANDA order placement, trading-enable mutation, flatten actions, alerts, or deployment changes.
- M9 adds OANDA practice execution for exactly one `promoted` variant through `POST /api/variants/{variant_id}/promote`, `POST /api/control/trading`, and `POST /api/control/flatten`. Practice trading uses attached stop-loss/take-profit orders, idempotent signal ids, broker transaction dedupe, open trade/position reconciliation, NY-close/manual flatten, daily-loss kill switch, and ntfy alerts behind the notifier boundary.
- M10 exposes Trades, Backtests, optimizer/tuning studies, paper variants, Config, Events, and Operations in the web UI. Config edits are diffed, confirmed, validated, and audited. Events include structured detail and daily summaries. Operations remains practice-only and LAN-only.
- OANDA integration uses the official REST and streaming endpoints through an async client boundary. OANDA practice execution is enabled; live trading remains outside the validated path and still requires multiple explicit runtime gates.
- Forward testing is operational validation after M10, not a build milestone. The Forward-Test Validation Plan in `docs/forward-test-validation.md` defines the evidence required before any live enablement discussion.

## Decisions

- [ADR-0001](adr/0001-true-nas-platform-deployment.md) records the Ahara TrueNAS deployment shape.
- [ADR-0002](adr/0002-python-fastapi-backend.md) records the Python backend choice.
- [ADR-0003](adr/0003-pure-closed-candle-strategy-core.md) records the pure closed-candle strategy core.
- [ADR-0004](adr/0004-raw-async-oanda-client.md) records the OANDA client boundary.
