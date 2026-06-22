# Changelog

All notable user-visible changes are recorded here.

## v0.2.0 - 2026-06-22

### Changed

- Rebuilt the dashboard around a new information architecture: a persistent command bar with live account vitals, mode, heartbeat, and armed state, plus a grouped sidebar (Monitor, Research, System) replacing the flat tab bar.
- Reorganised the views into Cockpit (live chart, lifecycle pipeline, session levels, guarded trading, activity ticker), Journal (composite trading-health score with metric tiles and equity curve), Validation (backtest metric banner, equity curve, trade and run history), Lab (candle source, walk-forward preflight, in/out-of-sample candidate scatter, variant leaderboard, trial diagnostics), Operations, Config, and Events.
- Restyled the interface as a dark trading-terminal theme with a tokenised colour and typography system, monospace tabular figures, SVG data visualisations, and live value flashes; the candlestick chart matches the new palette.

### Removed

- Removed the standalone Workflow view; its strategy-lifecycle status now lives on the Cockpit pipeline strip.

### Scaffold

- Added the executable backend, frontend, platform, compose, and verification scaffold for Harbor.

### Documentation

- Established the Harbor source specification, architecture decisions, and implementation plan.
