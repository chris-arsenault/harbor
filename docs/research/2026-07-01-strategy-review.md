# 2026-07-01 Strategy Review — Findings and Fix Tracker

Full review of strategy implementation correctness and research-framework power,
plus the next wave of strategy work. Each item is checked off when implemented
with tests.

## A. Mechanical fixes

### A1. Research framework power (the "why no fruit" fixes)

- [x] A1a. ATR-normalized outcomes in the edge study (`outcome_unit="atr"`), so
      pooled/conditioned tests gain power from variance reduction.
- [x] A1b. Benjamini-Hochberg FDR for the exploratory scan family (Bonferroni is
      reserved for the single confirmatory study); expose `bh_q_value`.
- [x] A1c. Pooled multi-instrument panel scan: pool ATR-normalized sweep
      observations across instruments per (algorithm, horizon), cluster by
      trading day, to multiply effective sample size.

### A2. ATR-trail intrabar lookahead (backtester)

- [x] `_advance_trailing` is fed `day_history` including the current candle, so
      the trail ratchets on the current candle's extreme and is then tested
      against the same candle. Advance the trail from candles up to the prior
      close only.

### A3. Silent position drop at day rollover (backtester)

- [x] `engine.run_backtest` sets `position = None` on a new trading date without
      booking a closing trade when `force_ny_close=false`. Force-close at the
      last candle of the outgoing day with exit reason `day_rollover`.

### A4. UTC-date daily aggregation (research)

- [x] `daily_closes` / `daily_bars` group by raw UTC calendar date, creating
      bogus Sunday part-days. Group by the New York 17:00 trading-day convention
      (via ZoneInfo, no hardcoded offsets). Rerun-sensitive: H109/H110/H112.

### A5. H108 weekend probe measures only the drift leg

- [x] Split into two labeled legs: gap leg (Friday close → first reopen price vs
      weekend proxy return) and drift leg (reopen → Monday close vs the same
      proxy return).

### A6. H112 lead-lag multiple-testing

- [x] 168 correlations, top-12 by |corr|, no correction. Apply BH-FDR across the
      whole family; `candidate` only when the adjusted q-value survives.

### A7. H109 overlapping-window t-stats

- [x] 5-day forward windows sampled daily with an iid t-stat (~sqrt(5)
      inflation). Use non-overlapping stride = horizon records.

### A8. Minor correctness items

- [x] Take-profit fills (bracket target, runner target, partial 1R bank) are
      limit orders: stop applying adverse slippage to them. Stops, forced and
      time exits keep slippage.
- [x] `_volatility_bucket` uses the full-sample median (in-sample conditioning);
      use prior-observations-only expanding median.
- [x] `_compressed_range_events` includes the current session range in its
      median baseline; use prior-only.
- [x] `detect_sweep` returns the first level in tuple order when one candle
      sweeps several; prefer the outermost swept level.
- [x] `_position_states` net scale heuristic (`abs(net) <= 1.5`) misparses a
      legitimately small net book; infer scale from total long+short mass.

## B. Strategy work

- [x] B1. **H113 cross-sectional reversal** — promote the inverted H100 momentum
      result to a first-class algorithm: inverse-vol-weighted legs, 5 staggered
      daily tranches (kills window overlap, smooths the curve), daily portfolio
      returns. New hypothesis doc + active lifecycle.
- [x] B2. **H114 cross-pair sweep divergence** — condition sweep events on
      whether a currency-linked sibling pair swept its own level in the same
      window: divergent sweep = idiosyncratic stop-run (reversion), confirmed
      sweep = common repricing (continuation). New direction probe + doc.
- [x] B3. **H115 multi-candle sweep reclaim** — sweep population extension: a
      breach candle followed by a close back inside the level within k candles
      (the current definition only sees single-candle wick-and-reclaim). New
      edge algorithm + doc.
- [x] B4. **H116 triple-barrier sweep outcomes** — score sweep events by first
      touch of ±k·ATR barriers (matches the actual trade payoff shape; lower
      variance than fixed-horizon means). Groundwork for a future meta-labeling
      gate. New edge-framework scan + doc.
- [x] B5. **H110 upgrade** — replace lag-1 range autocorrelation with a HAR-style
      range model (1d/5d/22d averages, expanding out-of-sample refit); report
      OOS correlation and top-tercile hit rate.
- [x] B6. **H106 unblock** — month-end/London-fix flow needs no external
      calendar: compute last-business-day and 16:00 Europe/London from the
      clock. Probe: pre-fix drift (15:40→16:00) vs post-fix reversal
      (16:00→16:30), month-end vs normal days.
- [x] B7. **H111 extension** — underwater-crowd fade interaction row: condition
      bearish sweep fades on the share of long positions held above current
      price (trapped supply) from the position book.

## C. Documentation

- [x] Hypothesis docs for H113–H116; update H106, H108, H109, H110, H111, H112.
- [x] Update `docs/research/hypotheses/README.md` index.
- [x] CHANGELOG entry.
- [x] `make ci` green.
