@AGENTS.md

## Claude-specific

- Use `feature-start` for architecture-level planning before large Harbor changes.
- Use `plan-phase` to expand one milestone from [HARBOR-PLAN.md](HARBOR-PLAN.md) before implementation.
- Use `repo-docs` when touching README, AGENTS, CLAUDE, docs, ADRs, backlog, or changelog together.
- Do not wrap normal Git remote operations like `git fetch`, `git pull`, or `git push` in `with-cred`; the configured repository remote handles those without the secret broker.
