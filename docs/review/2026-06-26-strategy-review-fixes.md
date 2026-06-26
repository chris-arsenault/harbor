# Strategy Review — Fix Tracker (2026-06-26)

Findings from a review of the trading algorithm implementation. Each item has a
severity, evidence, the intended fix, and a status. Update status as work lands.

Status legend: `todo` / `in-progress` / `done`

---

## 1. (Critical) Live paper-forward rebuilds the engine per candle → intraday state lost
- Evidence: `backend/src/harbor_bot/paper_engine/service.py:143` constructs a new
  `ShadowPaperEngine` on every `run_closed_candles` call. The live stream feeds
  one candle at a time (`backend/src/harbor_bot/api.py:620-635`), so `day_history`,
  `active_sweep`, `position`, `candle_index`, `session_levels`, and `nav` reset each
  candle. FVG detection can never fire, sweeps never persist, and once a candle
  enters the NY window `compute_session_levels` raises on a 1-candle history and
  kills the stream task.
- Fix: keep a persistent `ShadowPaperEngine` per instrument inside the service so
  state carries across calls; rebuild only when the active variant set changes.
- Status: done

## 2. (High) Practice execution is never wired to the live feed
- Evidence: `PracticeExecutionService.process_closed_candle` is only referenced by
  the service module and tests; the live stream drives the paper service instead.
- Fix: provide an explicit runtime path (callback) that drives practice execution
  from closed candles with persistent day state, alongside paper-forward.
- Status: done

## 3. (High) Execution default RiskContext/DayState bypass hard guards and mis-size
- Evidence: `backend/src/harbor_bot/execution/service.py:97,104,245` —
  `DayState(trading_date=candle.ts.date())` (UTC date, not the NY trading date),
  `_default_risk_context` with `nav=10000`, `day_start_nav=10000`, `spread_pips=0`.
  Result: position size off a hardcoded NAV, spread filter dead, daily-loss dead,
  NY-close flatten computed for the wrong day.
- Fix: require/thread a real `RiskContext` (account NAV, day-start NAV, live spread)
  and a correct trading-date `DayState`; remove the unsafe silent defaults.
- Status: done

## 4. (Low) Dead/duplicated branch in bracket exit pricing
- Evidence: `backend/src/harbor_bot/backtester/fills.py:402` `_bracket_exit_price`
  has identical `take_profit` and fallback branches.
- Fix: collapse to a single adverse-slippage adjustment.
- Status: done

## 5. (Medium) Position sizing can exceed intended risk
- Evidence: `backend/src/harbor_bot/strategy/signals.py:146`
  `max(stepped, minimum_trade_size)` bumps undersized trades up to broker minimum,
  raising realized risk above `risk_per_trade_pct` with no veto.
- Fix: when the minimum lot exceeds the risk budget, veto the trade instead of
  silently over-risking; keep the `max_units` clamp.
- Status: done

## 6. (Medium) "First sweep of a level per day" not fully enforced
- Evidence: a level is marked taken only on entry (`sweeps.py mark_level_taken`),
  so a vetoed/expired sweep lets the same level re-trigger later that day.
- Fix: record swept levels for the day and skip already-swept levels in
  `detect_sweep` when `one_trade_per_level` is set.
- Status: done

## 7. (Low) Liquidity target does not exclude already-swept/taken levels
- Evidence: `signals.py choose_target` / `_opposite_liquidity_targets` selects the
  opposite session levels purely by distance, ignoring whether they are untapped.
- Fix: thread day state's swept/taken levels and exclude tapped pools from target
  selection.
- Status: done

## 8. (Low) Sweeps detected outside the NY entry window
- Evidence: `detect_sweep` has no window check; only `detect_fvg` enforces the NY
  window, so sweeps churn after 11:30 ET.
- Fix: gate sweep detection to the NY trade window.
- Status: done
