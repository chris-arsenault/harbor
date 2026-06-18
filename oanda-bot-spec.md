# Implementation Spec — Session Sweep + FVG Reversal Bot (OANDA, self-hosted)

**Audience:** the coding agents building this.
**Status:** demo/paper only until forward-tested. Live is a config flip, not a rewrite.
**Prime directive:** every strategy decision is made on **closed candles only**. No logic may read the currently-forming candle. Repainting is the #1 way this silently lies in backtest.

---

## 1. Goal & scope

Build a headless, containerized bot that runs 24/5 on a TrueNAS SCALE box. It trades a single ICT-style strategy on OANDA: mark Asia/London session liquidity, wait for a sweep, take a 1-min FVG reversal, target 1:2 RR. It exposes a local REST+WebSocket API and ships a custom React dashboard for observability. Paper trading via OANDA practice is the default and only initially-enabled mode.

Non-goals: multi-strategy framework, ML, multi-broker abstraction. Build this one thing well; keep the strategy core pure and swappable later.

---

## 2. Architecture

```
                         TrueNAS SCALE (Docker)
 ┌──────────────────────────────────────────────────────────────┐
 │                                                              │
 │  ┌────────────┐   prices   ┌──────────────────────────────┐  │
 │  │  OANDA v20 │──stream────▶│  bot (Python, asyncio)       │  │
 │  │  practice  │◀──orders────│                              │  │
 │  └────────────┘            │  feed → strategy → risk →     │  │
 │        ▲ candles (REST)    │  execution                   │  │
 │        │                   │  + FastAPI (REST + WS)        │  │
 │        │                   └───────┬──────────────┬───────┘  │
 │        │ backtest                  │ writes       │ serves   │
 │        │                           ▼              ▼          │
 │        │                   ┌────────────┐   ┌──────────────┐ │
 │        └───────────────────│ PostgreSQL │   │ React UI     │ │
 │                            │  (state)   │   │ (nginx)      │ │
 │                            └────────────┘   └──────────────┘ │
 │                                   │                          │
 │                            ┌──────▼───────┐                  │
 │                            │ ntfy/Telegram│  fills, errors,  │
 │                            │  (alerts)    │  kill-switch,    │
 │                            └──────────────┘  heartbeat       │
 └──────────────────────────────────────────────────────────────┘
```

The **strategy core is a pure function** of (candle history, session levels, current state) → decisions. No I/O inside it. The same core is driven live by the feed service and offline by the backtester. This is the single most important design constraint — it's what makes the backtest trustworthy.

---

## 3. Tech stack

- **Language:** Python 3.12, `asyncio`.
- **OANDA client:** `oandapyV20` (or raw `httpx` against the v20 REST/stream endpoints). Bearer-token auth.
- **API server:** FastAPI + Uvicorn (REST + WebSocket on the same app).
- **DB:** PostgreSQL 16 (SQLite acceptable for v1, but Postgres for concurrent UI reads). SQLModel/SQLAlchemy + Alembic migrations.
- **UI:** React 18 + Vite + TypeScript, TailwindCSS, TanStack Query (REST), native WebSocket for live, **`lightweight-charts`** (TradingView's OSS lib) for the candle/level/trade overlay.
- **Packaging:** Docker; `docker compose`; deploy as a TrueNAS SCALE Custom App.
- **Alerts:** ntfy (self-host on the NAS) or a Telegram bot.

### OANDA v20 endpoints (verify against current official docs before coding)
- REST base (practice): `https://api-fxpractice.oanda.com/v3`
- Stream base (practice): `https://stream-fxpractice.oanda.com/v3`
- Live bases swap `fxpractice` → `fxtrade`. **This is the only meaningful diff between paper and live.**
- Historical candles: `GET /instruments/{instrument}/candles?granularity=M1&price=M&count=...&from=...`
- Price stream: `GET /accounts/{accountID}/pricing/stream?instruments=...`
- Place order: `POST /accounts/{accountID}/orders`
- Open trades / positions: `GET /accounts/{accountID}/openTrades`, `/positions`
- Transaction stream (fills, etc.): `GET /accounts/{accountID}/transactions/stream`
- Account summary (equity/NAV): `GET /accounts/{accountID}/summary`

---

## 4. Strategy specification (formalize exactly — no ambiguity)

All times are anchored to **America/New_York** and converted to UTC at runtime so DST is handled automatically. Never hardcode a UTC offset.

### 4.1 Sessions (defaults; make them config)
| Session | Window (ET) | Purpose |
|---|---|---|
| Asia | 20:00 (prev day) – 00:00 | mark `asia_high`, `asia_low` |
| London | 02:00 – 05:00 | mark `london_high`, `london_low` |
| NY trade window | 09:30 – 11:30 | the only window where entries are allowed |

At the **start of the NY window**, compute the four levels as the highest high / lowest low of the M1 candles within each completed session. These four prices are the **liquidity pools**. Persist them.

### 4.2 Sweep (the trigger condition)
A **sweep** is a *closed* M1 candle that takes a level and rejects it:
- **High sweep (→ bearish bias):** `candle.high > level + buffer` AND `candle.close < level`.
- **Low sweep (→ bullish bias):** `candle.low < level - buffer` AND `candle.close > level`.

`buffer` = `sweep_buffer_pips` (default 1–2 pips; instrument-dependent). On a sweep, record: which level, direction, the sweep candle's extreme (`sweep_high`/`sweep_low`), and a **deadline** = now + `fvg_window` candles (default 8). Only the *first* sweep of a given level per day is actionable (config: `one_trade_per_level`).

### 4.3 Fair Value Gap (the entry pattern)
3-candle imbalance on closed candles (indices i, i-1, i-2):
- **Bullish FVG:** `low[i] > high[i-2]` (gap up). Valid only when current bias is **bullish** (a low was swept).
- **Bearish FVG:** `high[i] < low[i-2]` (gap down). Valid only when current bias is **bearish** (a high was swept).

The FVG must form **within `fvg_window` candles after the sweep** and inside the NY window. Record the gap's top/bottom/midpoint.

### 4.4 Entry
**Decision: market entry.** The moment the qualifying FVG candle closes, enter at the next price. Deterministic and backtest-faithful; no resting limit orders. Direction = the sweep bias (long after a low sweep, short after a high sweep).

### 4.5 Stop, target, sizing
- **Stop:** beyond the sweep extreme — `sweep_low - buffer` (long) or `sweep_high + buffer` (short). Optionally widen to the swing low/high over the last `swing_lookback` candles. `risk = abs(entry - stop)`.
- **Target: `rr_or_liquidity` — take whichever is closer**, the 1:2 RR level (`entry ± 2 * risk`) or the opposite untapped session level (next draw on liquidity). Banking at the nearer objective is the lower-risk choice and matches the stated goal. The `rr` floor stays at 2.0; if the nearer liquidity draw yields less than 1:1, skip the trade rather than take poor RR.
- **Position size:** computed from `risk_per_trade_pct` of account NAV and the stop distance in price → units. Never a fixed lot. Clamp to broker min/step and a hard `max_units`.

### 4.6 State machine (per instrument, per day)
```
IDLE
  → (NY window opens) MARK_LEVELS        # compute 4 levels
  → WAIT_SWEEP                           # scan closed candles
  → SWEPT{dir, deadline, sweep_extreme}  # on sweep
  → WAIT_FVG                             # scan for reversal FVG until deadline
  → IN_TRADE{entry, stop, target}        # order placed & filled
  → manage (broker-side SL/TP brackets)
  → FLAT → COOLDOWN(level marked taken)  # back to WAIT_SWEEP for other levels
On NY window close: cancel pending, flatten any open position, → IDLE (reset next day).
```

### 4.7 Hard guards (non-negotiable)
- Max **1 concurrent position**.
- `max_trades_per_day` (default 2–3).
- One trade per level per day.
- **Flatten everything at NY window close.**
- **Daily-loss kill switch:** if NAV drops `max_daily_loss_pct` below day-start equity → flatten, disable trading until next session, fire an alert.
- **Spread filter:** skip entries when spread > `max_spread_pips`.
- **News filter (optional, v2):** pause ±N min around configured high-impact times.

---

## 5. Services / modules (inside the bot process)

| Module | Responsibility |
|---|---|
| `feed` | Maintain OANDA price stream + build/confirm M1 candles (or poll candles endpoint). Emits **closed** candles only to the strategy. Handles reconnect with backoff. |
| `strategy_core` | **Pure.** `(candles, levels, state, config) → Decision[]` (mark/sweep/fvg/enter/exit). No I/O. Fully unit-tested on fixtures. |
| `risk` | Position sizing, kill switch, spread/news/limit checks. Can veto any entry decision. |
| `execution` | Translate decisions → OANDA orders with attached SL/TP brackets. Idempotent (dedupe by signal id). Reconciles bot state vs broker truth via transaction stream. |
| `persistence` | Write candles cache, levels, sweeps, FVGs, signals, trades, equity snapshots, events. |
| `api` | FastAPI: REST for history/config/control + WebSocket for live push. |
| `notifier` | ntfy/Telegram: fills, errors, kill-switch trips, daily summary, heartbeat. |
| `backtester` | Replays historical candles through the **same `strategy_core`**; simulates fills/spread/slippage; outputs stats + trade list. |
| `optimizer` | Offline Optuna study that sweeps strategy params via the backtester under walk-forward validation; emits robust candidate param sets. See §15. |
| `paper_engine` | In-process shadow fill simulator. Runs many param-set variants in parallel off the **one** live price stream, attributes P&L per variant to the DB. The live-forward stage of §15. |

---

## 6. Data model (Postgres)

- `candles(instrument, ts, o,h,l,c, volume, complete)` — cache; unique (instrument, ts).
- `sessions(date, instrument, asia_high, asia_low, london_high, london_low)`.
- `sweeps(id, ts, instrument, level_name, level_price, direction, sweep_extreme)`.
- `fvgs(id, ts, instrument, type, top, bottom, midpoint, sweep_id)`.
- `signals(id, ts, instrument, direction, entry, stop, target, risk, rr, status)` — status: pending/filled/cancelled.
- `trades(id, signal_id, broker_trade_id, side, units, entry_price, entry_ts, exit_price, exit_ts, pnl, r_multiple, exit_reason)`.
- `equity_snapshots(ts, nav, balance, unrealized_pnl, open_positions)`.
- `events(ts, level, module, type, message, data_json)` — structured event log for the UI.
- `config(key, value_json, updated_ts)` — live-editable params (the *promoted* live param set).
- `backtest_runs(id, created_ts, params_json, stats_json)` + `backtest_trades(run_id, ...)`.
- `opt_studies(id, created_ts, search_space_json, walkforward_json, status)` — an Optuna study.
- `opt_trials(study_id, trial_no, params_json, is_score, oos_score, robustness_score, pruned)` — every evaluated param set (in-sample, out-of-sample, robustness).
- `variants(id, label, params_json, source_trial_id, status)` — status: `paper` (forward-testing) / `promoted` / `retired`. The live bot reads the single `promoted` variant.
- `variant_trades(...)` — same shape as `trades`, keyed by `variant_id`; populated by the paper engine so every forward-tested variant has its own journal and equity curve.

---

## 7. Internal API surface (FastAPI)

**REST**
- `GET /api/status` → bot state, session phase, connection health, mode (paper/live), trading_enabled, kill-switch state, day P&L, last heartbeat.
- `GET /api/levels?date=` → today's four levels + which are swept/taken.
- `GET /api/candles?instrument=&from=&to=` → M1 candles for the chart.
- `GET /api/markers?date=` → sweeps, FVG boxes, entries/exits for chart overlay.
- `GET /api/trades?from=&to=` → trade journal + R multiples.
- `GET /api/equity?from=` → equity curve points.
- `GET /api/events?level=&limit=` → recent events/logs.
- `GET/PUT /api/config` → read/update strategy params (PUT requires confirm flag; logs an event).
- `POST /api/control/flatten` → flatten now (manual kill).
- `POST /api/control/trading {enabled: bool}` → enable/disable entries (does not close open).
- `POST /api/backtest` → run a backtest with params; `GET /api/backtest/{id}` → results.
- `POST /api/optimize` → launch an Optuna study (search space + walk-forward config); `GET /api/optimize/{id}` → progress + ranked trials.
- `GET /api/variants` → all variants with live-forward stats; `POST /api/variants` → promote a trial to a paper variant; `POST /api/variants/{id}/promote` → make it the single live `config` (guarded confirm); `POST /api/variants/{id}/retire`.

**WebSocket** `/ws` — server pushes JSON events: `candle`, `level_update`, `sweep`, `fvg`, `signal`, `trade`, `equity`, `status`, `log`. UI subscribes and updates live without polling.

---

## 8. React observability UI

Vite + TS + Tailwind + TanStack Query + `lightweight-charts`. Single-page app behind nginx. Connects to the bot's REST + `/ws`. Read-mostly, with a few guarded control actions.

**Pages**

1. **Dashboard** (default)
   - Status strip: bot state (IDLE/WAIT_SWEEP/…), current session phase, OANDA connection health, paper/live badge, **trading enabled toggle**, kill-switch state, time-to-NY-window.
   - Cards: today's realized P&L, open position (side/size/unreal P&L/entry/stop/target), trades today vs cap, account NAV.
   - **Heartbeat indicator** — goes red if no WS message in N seconds.
   - Big red **FLATTEN NOW** button (confirm modal).

2. **Live Chart** — the centerpiece for trust.
   - M1 candlestick chart with the four session levels drawn as horizontal lines (Asia orange, London blue), labeled.
   - **Sweep markers** (▲/▼ at the sweep candle), **FVG boxes** (shaded rectangles), entry/stop/target lines, exit markers. Live position overlay.
   - Updates in real time from `/ws`. This is how you visually confirm the bot "sees" what you see — and catch repaint/logic bugs fast.

3. **Trades / Journal** — sortable/filterable table: time, side, size, entry, exit, R multiple, P&L, exit reason. Equity curve chart above it. Summary stats: win rate, avg R, expectancy, profit factor, max drawdown, trades/day.

4. **Backtest** — form to set params + date range, run, and view results (equity curve, stat table, trade list, the same chart-overlay replay). Save/compare runs.

5. **Config** — view/edit strategy params (sessions, buffers, rr, target_mode, risk %, caps, filters). Edits require a confirm and are logged as events. Show param diffs.

6. **Events / Logs** — live-streaming structured log with level filters (info/warn/error) and module filter.

7. **Lab** (optimization & variants) — launch/monitor Optuna studies (live progress, best-trial history, in-sample vs out-of-sample scatter so overfit trials are visible). Below it, the **variant leaderboard**: every paper-forward variant with its live-forward equity curve, R stats, and trade count, ranked by out-of-sample-then-live performance. Promote a trial → paper variant, or promote the leader → the single live config (guarded confirm). One variant is marked `promoted` and drives the real account.

UI principles: real-time first (WS, not polling); the chart must render exactly what the strategy core computed (server sends the markers, UI doesn't recompute strategy); destructive actions gated behind confirms; mobile-readable dashboard so you can glance from your phone.

---

## 9. Observability beyond the UI

- **Structured JSON logging** to stdout (Docker captures it) + `events` table.
- **Alerts** (ntfy/Telegram): every fill, every error/disconnect, kill-switch trip, and a **daily summary** (trades, P&L, R). A **heartbeat** ping every N minutes; if it stops, you know the bot died *before* you have a naked position.
- Optional `/metrics` Prometheus endpoint (signals, fills, latency, reconnects) if you run Grafana on the NAS.

---

## 10. Config & secrets

- `.env` (Docker secrets in prod): `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`, `OANDA_ENV=practice|live`, DB creds, ntfy/Telegram creds.
- Strategy params live in the `config` table (hot-editable via UI), seeded from a `defaults.yaml`.
- **`OANDA_ENV` is the only switch between paper and live.** Default `practice`. Going live should also require `trading_enabled=true` *and* an explicit `ALLOW_LIVE=true` env guard so it can't happen by accident.

---

## 11. Deployment (TrueNAS SCALE)

`docker compose` with services: `bot` (strategy+execution+FastAPI), `db` (postgres, persistent volume), `ui` (nginx serving the built React bundle, reverse-proxying `/api` and `/ws` to `bot`), optional `ntfy`. Deploy as a **Custom App** on SCALE (compose import) or via the apps UI. Persist Postgres data and a config volume. Set `restart: unless-stopped` on `bot` and `db`. Expose only the UI port on the LAN (keep it off the public internet; if you need remote access, go through your existing VPN/Tailscale, not a port-forward).

---

## 12. Testing strategy

- **Unit:** `strategy_core` against hand-built candle fixtures — every case: clean sweep, failed sweep (no close-back-inside), FVG in/out of window, wrong-direction FVG, sizing math, kill switch. Deterministic, no network.
- **Property/regression:** feed a recorded day of M1 candles, assert the exact signals/trades produced (snapshot test) so refactors can't silently change behavior.
- **Backtest as integration:** run over months of OANDA history; sanity-check stats and look for look-ahead leakage (results too good = repaint bug).
- **Paper e2e:** run against OANDA practice for weeks; reconcile bot's recorded trades vs OANDA's transaction history exactly.

---

## 13. Build order (milestones)

1. OANDA client + candle cache + M1 candle builder (closed-bar correctness first).
2. `strategy_core` + full unit tests. No execution yet.
3. Backtester over historical data → first read on whether there's an edge. **Gate: if no edge, stop and rethink the rules before building more.**
4. `optimizer` (Optuna + walk-forward) on top of the backtester → produces robust candidate param sets (§15, stages 1–2).
5. Persistence + FastAPI read endpoints.
6. React Dashboard + Live Chart wired to real data (paper, no orders).
7. `paper_engine` + Lab page: forward-test the candidates in parallel off the live stream (§15, stage 3).
8. Execution + risk/kill-switch against OANDA practice; alerts + heartbeat — wired to the single `promoted` variant.
9. Trades/Backtest/Config/Events pages; control actions.
10. Forward-test the promoted variant on paper for weeks; reconcile. Only then discuss live + minimum size.

---

## 14. Locked decisions

These are decided. Build to them; don't re-litigate.

- **Instrument:** single — **EUR_USD** for v1 (deep liquidity, tight spreads, fewer gaps than indices → lowest-risk substrate for the sweep logic). Multi-instrument is a deliberate v2.
- **Entry:** `market` (§4.4). **Target:** `rr_or_liquidity` (§4.5).
- **Risk:** `risk_per_trade_pct = 0.5`, `max_daily_loss_pct = 2.0`. Conservative by design, per the lower-risk goal.
- **Session/NY windows:** the §4.1 defaults are the *starting* values. They are **not** hand-tuned — they're parameters the optimizer (§15) searches within bounded ranges and the walk-forward validation locks in. Do not hardcode "tuned" times by eyeballing charts.

---

## 15. Optimization & multi-variant forward-testing

This is the committed parameter-tuning pipeline. One path, three stages. No alternative knobs.

**Objective function (the only one):** `out-of-sample expectancy ÷ max-drawdown`, with a hard floor of a minimum trade count per window (reject param sets that trade too rarely to be significant). This is risk-adjusted by construction and matches the lower-risk goal. Raw P&L is never the objective.

### Stage 1 — Offline search (the optimizer container)
- **Optuna**, TPE sampler, median pruner. Not hand-rolled hill-climbing or annealing — TPE converges in fewer evaluations on this kind of noisy, expensive objective and gives parallelism + pruning for free.
- Search space = the strategy params: session-window offsets (bounded), `sweep_buffer_pips`, `fvg_window`, `swing_lookback`, `rr` floor, `max_spread_pips`, `max_trades_per_day`. Keep it small — fewer dimensions, less overfit.
- Each trial = a backtest through the **same `strategy_core`** (§5). No separate logic, ever.

### Stage 2 — Walk-forward validation (overfit defense, mandatory)
- Every trial is scored by **walk-forward**, not a single backtest: optimize on window N, score on the untouched window N+1, roll forward across the full history. The trial's score is its aggregate **out-of-sample** performance.
- Reject sharp peaks; **prefer plateaus** — a param set whose neighbors also score well (robustness score from the local neighborhood). A lone spike is a noise-fit and is discarded even if its in-sample score is the highest.
- Output: a short ranked list (≈3–5) of **robust** candidate param sets written to `opt_trials` → promoted to `variants` as `paper`.

### Stage 3 — Parallel live-forward via the shadow paper engine
- The `paper_engine` consumes the **one** OANDA price stream and runs **all** candidate variants simultaneously, simulating fills (with spread + a slippage assumption) for each independently. Per-variant P&L lands in `variant_trades`.
- This is how "simultaneous strategies" actually happen: not N broker accounts, but N variants scored against the same live tick feed inside one process — unlimited variants, zero broker constraints, clean attribution.
- The real OANDA practice account is touched by **exactly one** variant: the `promoted` one (§4–§9 bot path). Its only job is validating that real fills/slippage match what the paper engine simulated for that variant.

### Promotion rule (no discretion)
A variant is eligible to be `promoted` only after it leads the live-forward leaderboard on the **out-of-sample-then-live** ranking for a sustained window (config `min_forward_days`, default 20 trading days) **and** its live-forward stats stay within tolerance of its backtest stats (drift beyond tolerance = the edge was a backtest artifact → retire it). Promotion is a guarded action in the Lab page and swaps the single live `config`. Only one variant is ever live.

### Hard rule against the overfit trap
The optimizer may **never** see the data the promoted variant is judged on. In-sample (Stage 1) → out-of-sample walk-forward (Stage 2) → live-forward (Stage 3) are strictly separated. If you ever re-optimize on the forward data, you've burned it; advance the window, don't reuse it.

---

*This describes engineering for a paper-trading research tool. It is not trading advice, and an automated strategy is not low-risk by virtue of being automated — least of all an auto-optimized one, which can fit noise with great confidence. Validate out-of-sample and on demo before risking real money.*
