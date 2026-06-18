# Agent Guide

Harbor is a TrueNAS-hosted OANDA practice-trading research system with a Python backend, React dashboard, PostgreSQL state, and Ahara platform deployment.

## Read First

| Topic | Link |
| ---- | ---- |
| Workspace overview | [README.md](README.md) |
| Implementation plan | [HARBOR-PLAN.md](HARBOR-PLAN.md) |
| Source specification | [oanda-bot-spec.md](oanda-bot-spec.md) |
| Documentation index | [docs/README.md](docs/README.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Development | [docs/development.md](docs/development.md) |
| Architecture decisions | [docs/adr/README.md](docs/adr/README.md) |
| Backlog | [docs/backlog.md](docs/backlog.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## Critical Rules

- Make every strategy decision from closed candles only.
- Keep `strategy_core` pure: no network, database, clock, broker, or UI I/O.
- Drive live trading, paper variants, and backtests through the same strategy core.
- Keep OANDA practice mode as the default runtime mode.
- Require `ALLOW_LIVE=true`, `OANDA_ENV=live`, and explicit trading enablement before live trading can place orders.
- Use America/New_York session definitions and timezone conversion; never hardcode a UTC offset.
- Follow Ahara TrueNAS LAN integration for deployment: shared workflow, Komodo, `secret-paths.yml`, TrueNAS PostgreSQL registration, and compose port publishing on `192.168.66.3`.
- Store real secrets outside the repo. Commit only placeholder examples or SSM paths.
- Use `with-cred -- ...` for commands that require app, deploy, or API secrets such as AWS, database, OANDA, ntfy, Telegram, or GitHub API tokens.
- Normal Git remote operations over the configured repository remote, including `git fetch`, `git pull`, and `git push`, do not use `with-cred`.
- Do not start local dev servers unless the user explicitly asks.

## Code Map

| Path | Purpose |
| ---- | ---- |
| `oanda-bot-spec.md` | Product and strategy source specification |
| `HARBOR-PLAN.md` | Milestone-level implementation plan |
| `backend/` | Python FastAPI bot process scaffold |
| `frontend/` | React observability dashboard scaffold |
| `backend/db/migrations/` | PostgreSQL migration home |
| `docs/` | Current-state project documentation |
| `docs/adr/` | Architecture decisions and trade-offs |
| `infrastructure/` | Platform notes for Ahara/TrueNAS integration |
| `compose.yaml` | TrueNAS Docker Compose stack |
| `secret-paths.yml` | Ahara SSM path mapping for Komodo deployment |
| `platform.yml` | Ahara platform manifest |

## Commands

| Command | Purpose |
| ---- | ---- |
| `make ci` | Canonical verification command |
| `scripts/deploy.sh` | Parameterless local deploy entrypoint |
| `sulion-code help` | Inspect available structural code navigation commands |
| `sulion-retrieve search "<query>"` | Search prior transcript history when available |
