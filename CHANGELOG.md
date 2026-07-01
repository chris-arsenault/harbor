# Changelog

All notable user-visible changes are recorded here.

## Unreleased

### Fixed

- Backtester ATR-trailing stops now advance only from candles closed before the current one, removing an intrabar lookahead that inflated `atr_trail` results.
- Backtester positions still open at a trading-date rollover are force-closed as `day_rollover` trades instead of being silently dropped when `force_ny_close` is off.
- Take-profit, runner-target, and partial scale-out fills are modeled as limit orders without adverse slippage; stop-side and forced exits keep slippage.
- Research daily aggregation groups candles by the New York 17:00 trading day instead of the raw UTC date, removing bogus Sunday part-days from H109/H110/H112 inputs.
- The H112 lead/lag probe applies Benjamini-Hochberg FDR across its ~168 pair/lag tests before flagging candidates; H109 records stride by the holding horizon so t-stats are not overlap-inflated.
- Sweep detection prefers the outermost level when one candle clears several stacked levels; compressed-range and volatility conditioning use prior-only baselines; position-book scale detection uses total book mass.

### Added

- Two-tier multiple-testing control in the edge framework: BH-FDR (`bh_q_value`) for exploratory scans, Bonferroni retained for the confirmatory single study; optional ATR-normalized outcomes.
- Pooled multi-instrument panel edge scan (`POST /api/research/edge/pooled`) with day-clustered errors over ATR-normalized observations.
- Triple-barrier first-touch scoring for event algorithms (`POST /api/research/edge/barriers`) as the H116 groundwork for meta-labeling.
- H113 `cs_reversal_20d_5d_tranched`: vol-scaled, 5-tranche cross-sectional reversal promoted from the inverted H100 momentum result.
- H114 `sweep_divergence_probe`: splits sweep events by cross-pair sibling confirmation (divergent→reversal, confirmed→continuation).
- H115 `multi_candle_sweep_reclaim_reversal`: breach-then-reclaim sweep population invisible to the single-candle definition.
- H106 `month_end_fix_probe`: month-end London-fix retracement computed from the clock, no external calendar needed.
- H108 weekend probe now reports separate reopen-gap and post-reopen-drift legs; H110 upgraded to an expanding out-of-sample HAR range model; H111 adds an underwater-long fade interaction row.

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
