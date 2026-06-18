# Harbor

Harbor is a self-hosted OANDA practice-trading research system for a closed-candle session sweep and FVG reversal strategy.

## Quickstart

Run the local verification gate:

```bash
make ci
```

The scaffold includes a Python FastAPI backend, Vite React frontend, Ahara platform manifest, TrueNAS compose files, and deployment scripts. Feature work continues from [HARBOR-PLAN.md](HARBOR-PLAN.md).

## Documentation

| Topic | Link |
| ---- | ---- |
| Implementation plan | [HARBOR-PLAN.md](HARBOR-PLAN.md) |
| Source specification | [oanda-bot-spec.md](oanda-bot-spec.md) |
| Documentation index | [docs/README.md](docs/README.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Development | [docs/development.md](docs/development.md) |
| Architecture decisions | [docs/adr/README.md](docs/adr/README.md) |
| Backlog | [docs/backlog.md](docs/backlog.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Agent guide | [AGENTS.md](AGENTS.md) |

## License

MIT. See [LICENSE](LICENSE).
