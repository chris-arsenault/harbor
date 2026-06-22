# Strategy Research Improvements — Implementation Plan

Evolve Harbor's sweep-to-FVG strategy through the research system, gated on first proving a
conditional edge exists and survives honest fills. The early milestones are a decision gate:
measure the raw edge and re-baseline backtests on bid/ask fills. Only if the edge survives do
the strategy-expansion milestones (market-structure-shift gate, decoupled exits, new levels and
filters) proceed. Out of scope: live order management for non-bracket exits, and the
order/position-book recorder — both are backlogged. This plan is milestone altitude; expand one
phase with `plan-phase` before executing it.

## Confirmed decisions

- The base-rate edge study is a first-class research artifact: a pure backend module, an API
  endpoint, and a Lab UI surface — not an offline script. (ADR 0005)
- Backtest fill realism uses **real bid/ask (`price=BA`) candles** with touch detection on true
  bid/ask, not a half-spread approximation on midpoint. Accuracy was chosen over cost. (ADR 0006)
- New strategy features land in the pure core for backtest + paper-forward + the variant
  pipeline first; live execution stays on static brackets and live order management is deferred.
  (ADR 0007)
- M1 and M2 are a decision gate; M3–M5 are contingent on the edge verdict and fill-survival.

## Context / reuse map

Reuse as-is:
- `strategy/sweeps.py` — sweep detection (penetration + close-back-inside) feeds the edge study.
- `strategy/sessions.py`, `strategy/models.py` — session-level computation and `LevelName`.
- `strategy/fvgs.py`, `strategy/signals.py` — FVG and entry/stop/target, extended by M3/M4.
- `backtester/{run,fills,models,stats}.py` — fill engine and stats, reworked in M2.
- `optimizer/{config.py,defaults.yaml,objective.py,walkforward.py,research_protocol.py}` —
  search space, objective (`expectancy / max_drawdown`), walk-forward, holdout. New params are
  added here as categorical priors.
- Variant/promotion + paper-forward pipeline — carries M3/M4 features to forward evidence.
- `oanda/client.py` — historical candle fetch (`price=M` today) extended for `price=BA`.
- Lab view (`frontend/src/views/lab/`) — host for the edge-study panel.

Build new:
- `backend/src/harbor_bot/research/` — pure base-rate edge module (home reserved).
- Bid/ask candle store + import path + migration (`db/migrations/`).
- MSS/BOS detector in the strategy core.
- Exit-mode simulators (partial+runner, ATR trail, time stop) in the backtester core.
- Tick-volume filter and PDH/PDL level computation.

Source-of-truth ADRs: 0003 (pure core), 0005 (edge gate), 0006 (bid/ask fills), 0007
(research-first evolution).

## Cross-cutting constraints

- **Pure strategy core.** MSS gate, exit modes, volume filter, and PDH/PDL levels are computed
  from closed candles only — no network, database, clock, broker, or UI I/O. The research module
  is held to the same purity (data passed in).
- **One core across live/paper/backtest.** Every new feature flows through the same evaluate
  path; live and research share identical core logic even while live execution is frozen.
- **Practice default and live gating unchanged.** `ALLOW_LIVE` / `OANDA_ENV` / explicit
  enablement still guard live; no milestone here relaxes them.
- **Search discipline.** New parameters are categorical priors, not free dimensions; net search
  dimensionality must not balloon — M5 prunes the session-offset micro-timing dims to offset
  additions.
- **Verification.** Every phase exit gate is `make ci` green plus the phase condition.

## Milestones

### M0 — Baseline capture
Record the current (midpoint) backtest expectancy and trade stats across the research universe
as the "before" reference, so the M2 fill-realism delta is measurable.
- Snapshot per-instrument expectancy / win-rate / max-drawdown from the existing midpoint
  backtest on a fixed window; store as a committed reference artifact.
- Exit: `make ci` green; baseline numbers recorded and reproducible.

### M1 — Base-rate conditional-edge study  (ADR 0005)
Measure whether reversals follow sweeps better than chance, before any strategy change.
- Pure `research` module: reuse sweep detection over persisted candles; compute forward
  N-minute return distributions in the reversal direction, conditioned by level type
  (asia/london high/low), session, and volatility (ATR bucket), against a chance baseline.
- API endpoint exposing per-instrument distributions and summary stats (skew, conditional vs
  baseline hit-rate, sample sizes) across the 8-pair universe.
- Lab UI panel: histograms and a per-instrument edge verdict.
- **[DECISION]** the edge-verdict thresholds — what skew / sample size counts as "edge present."
- Exit: `make ci` green; the study runs across the research universe and produces a per-instrument
  verdict surfaced in the Lab.

### M2 — Bid/ask fill realism  (ADR 0006)
Re-baseline backtests on honest fills and quantify how much expectancy survives.
- Add a `price=BA` historical import path and bid/ask candle storage (`db/migrations/`),
  parallel to the midpoint store.
- Rework backtester touch detection and fills to use true bid/ask instead of midpoint OHLC.
- Re-run the M0 baseline on bid/ask candles; report the expectancy survival delta per instrument.
- On ship, add the AGENTS critical rule that backtest fills use bid/ask, not midpoint.
- **[DECISION]** if honest expectancy collapses to non-positive, whether to halt the
  strategy-expansion milestones (M3–M5) rather than build on a dead edge.
- Exit: `make ci` green; backtests and the optimizer run on bid/ask candles; survival delta reported.

### M3 — Market-structure-shift entry gate  (CONTINGENT on M1 verdict + M2 survival; ADR 0007)
Require a break of structure after the sweep before entering, instead of a bare FVG.
- Pure core: after a sweep, require a break of the most-recent swing before the FVG entry;
  expose as a binary categorical search parameter (`require_mss`).
- Wire into the optimizer search space and config application.
- Reachable in backtest, paper-forward, and the variant pipeline; live execution unchanged.
- Exit: `make ci` green; `require_mss` is searchable and an A/B (gate on vs off) is measurable on
  bid/ask backtests.

### M4 — Exit decoupling  (CONTINGENT on M1 verdict + M2 survival; ADR 0007)  [depends on M2]
Decouple the exit from the entry and test exit modes as categorical priors.
- Pure core + backtester: categorical `exit_mode` — bracket (current), partial-at-1R-plus-runner,
  ATR-trailing, time-stop — simulated honestly on bid/ask candles.
- Add `exit_mode` to the optimizer search space.
- Backtest and paper-forward only; a variant whose exit mode needs active management is marked
  not live-eligible (live order management is backlogged).
- **[DECISION]** which exit modes to admit into the search space.
- Exit: `make ci` green; `exit_mode` is searchable and each mode is honored in backtest and
  paper-forward.

### M5 — Structural adds and search-space pruning  (CONTINGENT on M1 verdict + M2 survival)
Cheap, well-motivated additions, paired with a dimensionality cut to fight overfit.
- Tick-volume displacement filter using the already-collected `volume` (threshold/categorical
  param).
- PDH/PDL (previous-day high/low) levels alongside Asia/London in the session-level computation
  and `LevelName`.
- Prune the six session-offset micro-timing search dimensions (fix or remove) to offset the
  parameters added in M3–M5.
- **[DECISION]** keep vs drop the session-offset dimensions.
- Exit: `make ci` green; new filters/levels are searchable; net search dimensionality is not
  larger than before M3.

### Decisions needing your input
| Where | Decision you own |
| ----- | ---------------- |
| M1 | Edge-verdict thresholds — what conditional skew and sample size count as "edge present." |
| M2 | If honest bid/ask expectancy is non-positive, halt M3–M5 rather than build on a dead edge. |
| M4 | Which exit modes to admit into the search space. |
| M5 | Keep or drop the six session-offset micro-timing search dimensions. |
