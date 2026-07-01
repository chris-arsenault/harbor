"""Creative next-wave research probes for H108-H112 (pure)."""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import erfc, log, sqrt
from typing import Any
from zoneinfo import ZoneInfo

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.cross_instrument import DailyClose, daily_closes, ny_trading_day
from harbor_bot.strategy.models import Bias, require_closed_candle

FX_MAJORS = {
    "AUD_JPY",
    "AUD_USD",
    "EUR_GBP",
    "EUR_JPY",
    "EUR_USD",
    "GBP_JPY",
    "GBP_USD",
    "USD_JPY",
}
RISK_PROXIES = ("BTC_USD", "ETH_USD", "SPX500_USD", "NAS100_USD")


@dataclass(frozen=True)
class DailyBar:
    day: date
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class DirectionStats:
    count: int
    effect: float
    secondary: float
    t_stat: float

    def to_jsonable(self) -> dict[str, int | str]:
        return {
            "count": self.count,
            "effect": f"{self.effect:.8f}",
            "secondary": f"{self.secondary:.8f}",
            "t_stat": f"{self.t_stat:.8f}",
        }


@dataclass(frozen=True)
class DirectionRow:
    hypothesis_id: str
    algorithm_id: str
    label: str
    status: str
    subject: str
    metric: str
    unit: str
    stats: DirectionStats
    details: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "algorithm_id": self.algorithm_id,
            "label": self.label,
            "status": self.status,
            "subject": self.subject,
            "metric": self.metric,
            "unit": self.unit,
            "stats": self.stats.to_jsonable(),
            "details": self.details,
        }


@dataclass(frozen=True)
class SweepProbeEvent:
    instrument: str
    index: int
    ts: datetime
    bias: Bias
    pip_size: Decimal


@dataclass(frozen=True)
class BookState:
    book_type: str
    instrument: str
    snapshot_time: datetime
    net_long_pct: float
    buckets: tuple[tuple[float, float, float], ...] = ()  # (price, long_pct, short_pct)


def available_direction_algorithms() -> tuple[dict[str, str], ...]:
    return (
        {
            "algorithm_id": "weekend_risk_gap_probe",
            "hypothesis_id": "H108",
            "label": "Weekend risk-asset gap lead",
            "description": "Use 24/7 risk proxy weekend returns to explain Monday FX gaps.",
        },
        {
            "algorithm_id": "regime_resurrection_probe",
            "hypothesis_id": "H109",
            "label": "Regime-conditioned dead-signal resurrection",
            "description": "Retest inverted cross-sectional momentum by volatility regime.",
        },
        {
            "algorithm_id": "range_forecast_probe",
            "hypothesis_id": "H110",
            "label": "Next-session range forecast",
            "description": "Predict next daily high-low range from prior range persistence.",
        },
        {
            "algorithm_id": "book_conditioner_readiness",
            "hypothesis_id": "H111",
            "label": "Book-conditioned sweep readiness",
            "description": (
                "Check H103 coverage and score first book-conditioned sweep interaction."
            ),
        },
        {
            "algorithm_id": "lead_lag_network_probe",
            "hypothesis_id": "H112",
            "label": "Currency-network lead/lag propagation",
            "description": "Find stable daily lead-lag correlations across instruments.",
        },
        {
            "algorithm_id": "sweep_divergence_probe",
            "hypothesis_id": "H114",
            "label": "Cross-pair sweep divergence",
            "description": (
                "Split sweep reversals by whether a currency-linked sibling pair "
                "swept in the same window: divergent sweeps are idiosyncratic "
                "stop-runs, confirmed sweeps are common repricing."
            ),
        },
        {
            "algorithm_id": "month_end_fix_probe",
            "hypothesis_id": "H106",
            "label": "Month-end London fix reversal",
            "description": (
                "Pre-fix drift (15:40→16:00 London) faded after the fix "
                "(16:00→16:30), month-end days versus normal days."
            ),
        },
    )


def default_direction_algorithm_ids() -> tuple[str, ...]:
    return tuple(algorithm["algorithm_id"] for algorithm in available_direction_algorithms())


def run_direction_scan(
    candles_by_instrument: dict[str, list[ClosedCandle]],
    *,
    algorithm_ids: tuple[str, ...] | None = None,
    book_coverage: list[dict[str, Any]] | None = None,
    book_snapshots: list[dict[str, Any]] | None = None,
    sweep_events_by_instrument: dict[str, list[SweepProbeEvent]] | None = None,
) -> list[DirectionRow]:
    requested = set(algorithm_ids or default_direction_algorithm_ids())
    closes = {
        instrument: daily_closes(candles)
        for instrument, candles in candles_by_instrument.items()
        if candles
    }
    bars = {
        instrument: daily_bars(candles)
        for instrument, candles in candles_by_instrument.items()
        if candles
    }
    rows: list[DirectionRow] = []
    if "weekend_risk_gap_probe" in requested:
        rows.extend(_weekend_gap(closes, candles_by_instrument))
    if "regime_resurrection_probe" in requested:
        rows.extend(_regime_resurrection(closes))
    if "range_forecast_probe" in requested:
        rows.extend(_range_forecast(bars))
    if "book_conditioner_readiness" in requested:
        rows.extend(
            _book_readiness(
                book_coverage or [],
                book_snapshots or [],
                candles_by_instrument,
                sweep_events_by_instrument or {},
            )
        )
    if "lead_lag_network_probe" in requested:
        rows.extend(_lead_lag(closes))
    if "sweep_divergence_probe" in requested:
        rows.extend(_sweep_divergence(candles_by_instrument, sweep_events_by_instrument or {}))
    if "month_end_fix_probe" in requested:
        rows.extend(_month_end_fix(candles_by_instrument))
    return _rank_rows(rows)


def daily_bars(candles: list[ClosedCandle]) -> list[DailyBar]:
    grouped: dict[date, list[ClosedCandle]] = {}
    for candle in sorted(candles, key=lambda item: item.ts):
        require_closed_candle(candle)
        grouped.setdefault(ny_trading_day(candle.ts), []).append(candle)
    return [
        DailyBar(
            day=day,
            high=float(max(c.h for c in rows)),
            low=float(min(c.low for c in rows)),
            close=float(rows[-1].c),
        )
        for day, rows in sorted(grouped.items())
        if rows
    ]


def _rank_rows(rows: list[DirectionRow]) -> list[DirectionRow]:
    status_rank = {"candidate": 0, "ready": 1, "weak": 2, "collecting": 3, "data_required": 4}
    return sorted(
        rows,
        key=lambda row: (status_rank.get(row.status, 9), -abs(row.stats.t_stat), -row.stats.count),
    )


def _daily_maps(closes: dict[str, list[DailyClose]]) -> dict[str, dict[date, float]]:
    return {
        instrument: {item.day: item.close for item in rows} for instrument, rows in closes.items()
    }


def _common_days(maps: dict[str, dict[date, float]], instruments: list[str]) -> list[date]:
    if not instruments or any(instrument not in maps for instrument in instruments):
        return []
    days = set(maps[instruments[0]])
    for instrument in instruments[1:]:
        days &= set(maps[instrument])
    return sorted(days)


def _returns(series: list[DailyClose]) -> dict[date, float]:
    ordered = sorted(series, key=lambda item: item.day)
    return {
        ordered[idx].day: log(ordered[idx].close / ordered[idx - 1].close)
        for idx in range(1, len(ordered))
        if ordered[idx - 1].close > 0 and ordered[idx].close > 0
    }


def _weekend_gap(
    closes: dict[str, list[DailyClose]],
    candles_by_instrument: dict[str, list[ClosedCandle]],
) -> list[DirectionRow]:
    proxy = next((instrument for instrument in RISK_PROXIES if instrument in closes), None)
    if proxy is None:
        return [
            _row(
                "H108",
                "weekend_risk_gap_probe",
                "Weekend risk-asset gap lead",
                "data_required",
                "BTC_USD/ETH_USD/SPX500_USD/NAS100_USD",
                "proxy_available",
                "flag",
                count=0,
                effect=0,
                secondary=0,
                t_stat=0,
                details=(
                    "No 24/7 risk proxy candles found; add crypto/index data before "
                    "testing weekend information gaps."
                ),
            )
        ]

    maps = _daily_maps(closes)
    proxy_by_day = maps[proxy]
    rows: list[DirectionRow] = []
    for instrument in sorted(FX_MAJORS & closes.keys()):
        fx = maps[instrument]
        reopen_by_day = _first_open_by_trading_day(candles_by_instrument.get(instrument, []))
        proxy_xs: list[float] = []
        gap_ys: list[float] = []
        drift_ys: list[float] = []
        for day in sorted(fx):
            if day.weekday() != 0:
                continue
            friday = date.fromordinal(day.toordinal() - 3)
            sunday = date.fromordinal(day.toordinal() - 1)
            reopen = reopen_by_day.get(day)
            if (
                friday not in proxy_by_day
                or sunday not in proxy_by_day
                or friday not in fx
                or reopen is None
                or reopen <= 0
            ):
                continue
            proxy_xs.append(log(proxy_by_day[sunday] / proxy_by_day[friday]))
            gap_ys.append(log(reopen / fx[friday]))
            drift_ys.append(log(fx[day] / reopen))
        rows.append(
            _corr_row(
                "H108",
                "weekend_risk_gap_probe",
                "Weekend risk-asset gap lead",
                instrument,
                "corr(weekend_proxy,reopen_gap)",
                proxy_xs,
                gap_ys,
                threshold=0.15,
                details=(
                    f"Proxy={proxy}; gap leg: Friday close to first Monday-session "
                    "price. High correlation here means the weekend information is "
                    "repriced instantly at reopen (not tradable by itself)."
                ),
            )
        )
        rows.append(
            _corr_row(
                "H108",
                "weekend_risk_gap_probe",
                "Weekend risk-asset gap lead",
                instrument,
                "corr(weekend_proxy,post_reopen_drift)",
                proxy_xs,
                drift_ys,
                threshold=0.15,
                details=(
                    f"Proxy={proxy}; drift leg: first Monday-session price to Monday "
                    "close. Correlation here is the tradable underreaction component."
                ),
            )
        )
    return rows


def _first_open_by_trading_day(candles: list[ClosedCandle]) -> dict[date, float]:
    firsts: dict[date, float] = {}
    for candle in sorted(candles, key=lambda item: item.ts):
        firsts.setdefault(ny_trading_day(candle.ts), float(candle.o))
    return firsts


def _regime_resurrection(closes: dict[str, list[DailyClose]]) -> list[DirectionRow]:
    maps = _daily_maps({k: v for k, v in closes.items() if k in FX_MAJORS})
    instruments = sorted(maps)
    days = _common_days(maps, instruments)
    if len(instruments) < 4 or len(days) < 80:
        return [_data_required("H109", "regime_resurrection_probe", "FX universe")]
    lookback, horizon = 20, 5
    records: list[tuple[float, float]] = []
    # Stride by the holding horizon: daily-sampled 5d forward windows overlap,
    # which inflates iid t-stats ~sqrt(5); non-overlapping records are honest.
    for idx in range(lookback, len(days) - horizon, horizon):
        scores = []
        abs_returns = []
        for instrument in instruments:
            prior = maps[instrument][days[idx - lookback]]
            current = maps[instrument][days[idx]]
            yesterday = maps[instrument][days[idx - 1]]
            scores.append((instrument, log(current / prior)))
            abs_returns.append(abs(log(current / yesterday)))
        ranked = sorted(scores, key=lambda item: item[1], reverse=True)
        leg_count = max(1, len(instruments) // 4)
        longs = [instrument for instrument, _ in ranked[:leg_count]]
        shorts = [instrument for instrument, _ in ranked[-leg_count:]]
        records.append(
            (
                sum(abs_returns) / len(abs_returns),
                -_basket_forward(maps, days, idx, horizon, longs=longs, shorts=shorts) * 10_000,
            )
        )
    return _tercile_rows(records)


def _basket_forward(
    maps: dict[str, dict[date, float]],
    days: list[date],
    idx: int,
    horizon: int,
    *,
    longs: list[str],
    shorts: list[str],
) -> float:
    start, end = days[idx], days[idx + horizon]
    long_return = sum(log(maps[instrument][end] / maps[instrument][start]) for instrument in longs)
    short_return = sum(
        log(maps[instrument][end] / maps[instrument][start]) for instrument in shorts
    )
    return (long_return / len(longs)) - (short_return / len(shorts))


_HAR_WEEK = 5
_HAR_MONTH = 22
_HAR_MIN_TRAIN = 40


def _range_forecast(bars_by_instrument: dict[str, list[DailyBar]]) -> list[DirectionRow]:
    """H110 as a HAR-style range model: next daily range regressed on the
    1d/5d/22d average ranges with an expanding out-of-sample refit, instead of
    raw lag-1 autocorrelation."""
    rows: list[DirectionRow] = []
    for instrument, bars in sorted(bars_by_instrument.items()):
        if instrument not in FX_MAJORS:
            continue
        ordered = sorted(bars, key=lambda item: item.day)
        ranges = [
            log(bar.high / bar.low) * 10_000
            for bar in ordered
            if bar.high > 0 and bar.low > 0 and bar.high >= bar.low
        ]
        predictions, realized = _har_oos_forecast(ranges)
        rows.append(
            _corr_row(
                "H110",
                "range_forecast_probe",
                "Next-session range forecast",
                instrument,
                "har_oos_corr(next_daily_range)",
                predictions,
                realized,
                threshold=0.15,
                secondary=_top_tercile_hit(predictions, realized),
                details=(
                    "HAR(1d,5d,22d) expanding out-of-sample forecast of the next "
                    "daily high-low range. Effect is corr(prediction, realized); "
                    "secondary is top-tercile range hit-rate among predicted "
                    "high-range days."
                ),
            )
        )
    return sorted(rows, key=lambda row: float(row.stats.secondary), reverse=True)[:8]


def _har_oos_forecast(ranges: list[float]) -> tuple[list[float], list[float]]:
    """Expanding-window HAR forecasts: features at day t are the last range and
    the 5d/22d average ranges; the target is day t+1's range. Coefficients are
    refit on data through t-1 only, so every prediction is out-of-sample."""
    features: list[tuple[float, float, float]] = []
    targets: list[float] = []
    for idx in range(_HAR_MONTH - 1, len(ranges) - 1):
        week = ranges[idx - _HAR_WEEK + 1 : idx + 1]
        month = ranges[idx - _HAR_MONTH + 1 : idx + 1]
        features.append((ranges[idx], sum(week) / len(week), sum(month) / len(month)))
        targets.append(ranges[idx + 1])
    predictions: list[float] = []
    realized: list[float] = []
    for idx in range(_HAR_MIN_TRAIN, len(targets)):
        beta = _ols(features[:idx], targets[:idx])
        if beta is None:
            continue
        predictions.append(
            beta[0] + sum(coef * value for coef, value in zip(beta[1:], features[idx], strict=True))
        )
        realized.append(targets[idx])
    return predictions, realized


def _ols(features: list[tuple[float, ...]], targets: list[float]) -> list[float] | None:
    """Least squares with intercept via normal equations; None when singular."""
    size = len(features[0]) + 1
    xtx = [[0.0] * size for _ in range(size)]
    xty = [0.0] * size
    for feature, target in zip(features, targets, strict=True):
        row = (1.0, *feature)
        for i in range(size):
            xty[i] += row[i] * target
            for j in range(size):
                xtx[i][j] += row[i] * row[j]
    return _solve_linear(xtx, xty)


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    augmented = [row[:] + [vector[idx]] for idx, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(augmented[r][col]))
        if abs(augmented[pivot][col]) < 1e-12:
            return None
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col] / augmented[col][col]
            for k in range(col, size + 1):
                augmented[row][k] -= factor * augmented[col][k]
    return [augmented[idx][size] / augmented[idx][idx] for idx in range(size)]


def _book_readiness(
    book_coverage: list[dict[str, Any]],
    book_snapshots: list[dict[str, Any]],
    candles_by_instrument: dict[str, list[ClosedCandle]],
    sweep_events_by_instrument: dict[str, list[SweepProbeEvent]],
) -> list[DirectionRow]:
    if not book_coverage:
        return [
            _row(
                "H111",
                "book_conditioner_readiness",
                "Book-conditioned sweep readiness",
                "collecting",
                "OANDA books",
                "paired_snapshots",
                "snapshots",
                count=0,
                effect=0,
                secondary=0,
                t_stat=0,
                details="No book coverage rows yet; let H103 recorder accumulate snapshots.",
            )
        ]
    coverage_rows = _book_coverage_rows(book_coverage)
    interaction_rows = _book_interaction_rows(
        book_snapshots, candles_by_instrument, sweep_events_by_instrument
    )
    return [*interaction_rows, *coverage_rows]


def _book_coverage_rows(book_coverage: list[dict[str, Any]]) -> list[DirectionRow]:
    by_instrument: dict[str, dict[str, int]] = {}
    for row in book_coverage:
        by_instrument.setdefault(str(row["instrument"]), {})[str(row["book_type"])] = int(
            row.get("snapshot_count") or 0
        )
    rows = []
    for instrument, counts in sorted(by_instrument.items()):
        paired = min(counts.get("order", 0), counts.get("position", 0))
        status = "ready" if paired >= 500 else "collecting"
        rows.append(
            _row(
                "H111",
                "book_conditioner_readiness",
                "Book-conditioned sweep readiness",
                status,
                instrument,
                "paired_order_position_snapshots",
                "snapshots",
                count=paired,
                effect=float(paired),
                secondary=float(counts.get("order", 0) + counts.get("position", 0)),
                t_stat=0,
                details=(
                    "Effect/N are paired snapshot count; secondary is total order+position "
                    "snapshots. Interaction rows below are decision-relevant."
                ),
            )
        )
    return rows


def _book_interaction_rows(
    book_snapshots: list[dict[str, Any]],
    candles_by_instrument: dict[str, list[ClosedCandle]],
    sweep_events_by_instrument: dict[str, list[SweepProbeEvent]],
) -> list[DirectionRow]:
    states = _position_states(book_snapshots)
    rows: list[DirectionRow] = []
    horizon_minutes = 60
    for instrument, events in sorted(sweep_events_by_instrument.items()):
        if instrument not in candles_by_instrument or instrument not in states:
            continue
        candles = sorted(candles_by_instrument[instrument], key=lambda candle: candle.ts)
        by_ts = {candle.ts: candle for candle in candles}
        instrument_states = states[instrument]
        conditioned: list[float] = []
        unconditioned: list[float] = []
        underwater: list[float] = []
        for event in events:
            entry = candles[event.index]
            exit_candle = by_ts.get(entry.ts + timedelta(minutes=horizon_minutes))
            if exit_candle is None:
                continue
            signed = exit_candle.c - entry.c
            reversal = signed if event.bias == Bias.BULLISH else -signed
            reversal_pips = float(reversal / event.pip_size)
            unconditioned.append(reversal_pips)
            state = _latest_state_before(instrument_states, entry.ts)
            if state is None:
                continue
            underwater_share = _underwater_long_share(state, float(entry.c))
            if (
                event.bias == Bias.BEARISH
                and underwater_share is not None
                and underwater_share >= 0.6
            ):
                # Fading a rally into trapped long supply: longs holding above
                # current price are future break-even sellers.
                underwater.append(reversal_pips)
            if abs(state.net_long_pct) < 10:
                continue
            # Crowd trapped against reversal: bullish reversal with net-short crowd, or vice versa.
            if (event.bias == Bias.BULLISH and state.net_long_pct < 0) or (
                event.bias == Bias.BEARISH and state.net_long_pct > 0
            ):
                conditioned.append(reversal_pips)
        if not unconditioned:
            continue
        rows.append(
            _values_row(
                "H111",
                "book_conditioner_readiness",
                "Book-conditioned sweep interaction",
                _status_from_values(conditioned),
                instrument,
                "trapped_crowd_sweep_60m_reversal",
                "pips",
                conditioned,
                secondary=_mean(unconditioned),
                details=(
                    "Effect is 60m reversal pips after generic sweeps where latest position "
                    "book crowd was trapped against reversal by >=10 percentage points. "
                    "Secondary is unconditioned sweep mean pips."
                ),
            )
        )
        if underwater:
            rows.append(
                _values_row(
                    "H111",
                    "book_conditioner_readiness",
                    "Book-conditioned sweep interaction",
                    _status_from_values(underwater),
                    instrument,
                    "underwater_long_fade_60m_reversal",
                    "pips",
                    underwater,
                    secondary=_mean(unconditioned),
                    details=(
                        "Effect is 60m reversal pips for bearish sweeps where >=60% of "
                        "position-book long mass sat above the sweep price (underwater "
                        "longs are trapped supply). Secondary is unconditioned mean."
                    ),
                )
            )
    return rows


def _underwater_long_share(state: BookState, price: float) -> float | None:
    """Share of long position mass with cost basis above ``price``."""
    total_long = sum(long_pct for bucket_price, long_pct, _ in state.buckets if bucket_price > 0)
    if total_long <= 0:
        return None
    above = sum(long_pct for bucket_price, long_pct, _ in state.buckets if bucket_price > price)
    return above / total_long


def _position_states(book_snapshots: list[dict[str, Any]]) -> dict[str, list[BookState]]:
    by_instrument: dict[str, list[BookState]] = {}
    for row in book_snapshots:
        if row.get("book_type") != "position":
            continue
        buckets = row.get("buckets_json") or []
        net = 0.0
        total = 0.0
        bucket_rows: list[tuple[float, float, float]] = []
        for bucket in buckets:
            long_pct = float(bucket.get("long_pct") or 0)
            short_pct = float(bucket.get("short_pct") or 0)
            net += long_pct - short_pct
            total += long_pct + short_pct
            bucket_rows.append((float(bucket.get("price") or 0), long_pct, short_pct))
        # Detect fraction-scaled books from the total long+short mass (~2 for
        # fractions, ~200 for percents), not from the net, which can be near
        # zero for a legitimately balanced percent book.
        by_instrument.setdefault(str(row["instrument"]), []).append(
            BookState(
                book_type="position",
                instrument=str(row["instrument"]),
                snapshot_time=row["snapshot_time"],
                net_long_pct=net * 100 if 0 < total <= 3 else net,
                buckets=tuple(bucket_rows),
            )
        )
    return {
        instrument: sorted(rows, key=lambda state: state.snapshot_time)
        for instrument, rows in by_instrument.items()
    }


def _latest_state_before(states: list[BookState], ts: datetime) -> BookState | None:
    latest = None
    for state in states:
        if state.snapshot_time > ts:
            break
        latest = state
    return latest


def _lead_lag(closes: dict[str, list[DailyClose]]) -> list[DirectionRow]:
    returns = {
        instrument: _returns(rows) for instrument, rows in closes.items() if instrument in FX_MAJORS
    }
    instruments = sorted(returns)
    candidates: list[tuple[str, list[float], list[float]]] = []
    for leader in instruments:
        for lagger in instruments:
            if leader == lagger:
                continue
            for lag in (1, 2, 5):
                xs: list[float] = []
                ys: list[float] = []
                for day, lead_return in returns[leader].items():
                    target = date.fromordinal(day.toordinal() + lag)
                    if target in returns[lagger]:
                        xs.append(lead_return)
                        ys.append(returns[lagger][target])
                if len(xs) < 40:
                    continue
                candidates.append((f"{leader}→{lagger} +{lag}d", xs, ys))
    if not candidates:
        return [_data_required("H112", "lead_lag_network_probe", "FX universe")]

    # The max of ~168 pair/lag correlations clears any fixed threshold by
    # chance; a Benjamini-Hochberg q-value across the whole family is required
    # before a pair may be called a candidate.
    corrs = [_corr(xs, ys) for _, xs, ys in candidates]
    t_stats = [
        _corr_t_stat(corr, len(xs)) for corr, (_, xs, _) in zip(corrs, candidates, strict=True)
    ]
    q_values = _bh_q_values([_two_sided_p(t) for t in t_stats])
    rows = [
        _row(
            "H112",
            "lead_lag_network_probe",
            "Currency-network lead/lag propagation",
            "candidate" if len(xs) >= 30 and q <= 0.10 else "weak",
            subject,
            "lead_lag_corr",
            "corr",
            count=len(xs),
            effect=corr,
            secondary=q,
            t_stat=t_stat,
            details=(
                "Effect is correlation between leader return at t and lagger return "
                f"at t+lag; secondary is the BH-FDR q-value across all "
                f"{len(candidates)} pair/lag tests; shared legs still induce "
                "mechanical correlation."
            ),
        )
        for (subject, xs, _), corr, t_stat, q in zip(
            candidates, corrs, t_stats, q_values, strict=True
        )
    ]
    return sorted(rows, key=lambda row: abs(row.stats.effect), reverse=True)[:12]


_DIVERGENCE_WINDOW = timedelta(minutes=10)
_DIVERGENCE_HORIZON_MINUTES = 60


def _sweep_divergence(
    candles_by_instrument: dict[str, list[ClosedCandle]],
    sweep_events_by_instrument: dict[str, list[SweepProbeEvent]],
) -> list[DirectionRow]:
    """H114: a sweep unconfirmed by any currency-linked sibling is an
    idiosyncratic stop-run (reversion candidate); a simultaneous sibling sweep
    marks common repricing (continuation candidate). Pooling both populations
    is one hypothesis for why generic sweeps averaged to nothing."""
    instruments = sorted(sweep_events_by_instrument)
    if len(instruments) < 2:
        return [_data_required("H114", "sweep_divergence_probe", "sweep-event universe")]
    rows: list[DirectionRow] = []
    for instrument in instruments:
        if instrument not in candles_by_instrument:
            continue
        candles = sorted(candles_by_instrument[instrument], key=lambda candle: candle.ts)
        by_ts = {candle.ts: candle for candle in candles}
        sibling_times = sorted(
            event.ts
            for sibling, events in sweep_events_by_instrument.items()
            if sibling != instrument and _shares_currency(instrument, sibling)
            for event in events
        )
        divergent: list[float] = []
        confirmed: list[float] = []
        for event in sweep_events_by_instrument[instrument]:
            entry = by_ts.get(event.ts)
            exit_candle = by_ts.get(event.ts + timedelta(minutes=_DIVERGENCE_HORIZON_MINUTES))
            if entry is None or exit_candle is None:
                continue
            signed = exit_candle.c - entry.c
            reversal = signed if event.bias == Bias.BULLISH else -signed
            reversal_pips = float(reversal / event.pip_size)
            has_sibling_sweep = any(
                abs(sibling_ts - event.ts) <= _DIVERGENCE_WINDOW for sibling_ts in sibling_times
            )
            if has_sibling_sweep:
                confirmed.append(reversal_pips)
            else:
                divergent.append(reversal_pips)
        if divergent:
            rows.append(
                _values_row(
                    "H114",
                    "sweep_divergence_probe",
                    "Cross-pair sweep divergence",
                    _status_from_values(divergent),
                    instrument,
                    "divergent_sweep_60m_reversal",
                    "pips",
                    divergent,
                    secondary=_mean(confirmed),
                    details=(
                        "Sweeps with no currency-linked sibling sweep within ±10m, "
                        "reversal-scored at 60m. Secondary is the confirmed-sweep "
                        "mean for contrast."
                    ),
                )
            )
        if confirmed:
            rows.append(
                _values_row(
                    "H114",
                    "sweep_divergence_probe",
                    "Cross-pair sweep divergence",
                    _status_from_values([-value for value in confirmed]),
                    instrument,
                    "confirmed_sweep_60m_continuation",
                    "pips",
                    [-value for value in confirmed],
                    secondary=_mean(divergent),
                    details=(
                        "Sweeps confirmed by a sibling sweep within ±10m, "
                        "continuation-scored at 60m (common repricing should keep "
                        "going). Secondary is the divergent-sweep reversal mean."
                    ),
                )
            )
    return rows or [_data_required("H114", "sweep_divergence_probe", "sweep-event universe")]


def _shares_currency(instrument: str, sibling: str) -> bool:
    return bool(set(instrument.split("_")) & set(sibling.split("_")))


_LONDON_ZONE = ZoneInfo("Europe/London")
_FIX_TOLERANCE = timedelta(minutes=10)


def _month_end_fix(candles_by_instrument: dict[str, list[ClosedCandle]]) -> list[DirectionRow]:
    """H106 without any external calendar feed: the 16:00 London (WMR) fix time
    and the last business day of the month are both computable from the clock.
    Measures the post-fix retracement of the pre-fix drift."""
    rows: list[DirectionRow] = []
    for instrument in sorted(FX_MAJORS & candles_by_instrument.keys()):
        candles = sorted(candles_by_instrument[instrument], key=lambda candle: candle.ts)
        if not candles:
            continue
        times = [candle.ts for candle in candles]
        closes = [float(candle.c) for candle in candles]
        month_end_values: list[float] = []
        normal_values: list[float] = []
        for day in sorted({candle.ts.astimezone(_LONDON_ZONE).date() for candle in candles}):
            if day.weekday() >= 5:
                continue
            pre_fix = _close_near(times, closes, _london_at(day, 15, 40))
            at_fix = _close_near(times, closes, _london_at(day, 16, 0))
            post_fix = _close_near(times, closes, _london_at(day, 16, 30))
            if pre_fix is None or at_fix is None or post_fix is None:
                continue
            drift = log(at_fix / pre_fix)
            if drift == 0:
                continue
            retrace = log(post_fix / at_fix)
            reversal_bps = (-retrace if drift > 0 else retrace) * 10_000
            if _is_last_business_day(day):
                month_end_values.append(reversal_bps)
            else:
                normal_values.append(reversal_bps)
        for subject, values, contrast in (
            (f"{instrument} month-end", month_end_values, normal_values),
            (f"{instrument} normal", normal_values, month_end_values),
        ):
            if not values:
                continue
            rows.append(
                _values_row(
                    "H106",
                    "month_end_fix_probe",
                    "Month-end London fix reversal",
                    _status_from_values(values),
                    subject,
                    "post_fix_reversal_16to1630_london",
                    "bps",
                    values,
                    secondary=_mean(contrast),
                    details=(
                        "Effect is the 16:00→16:30 London retracement scored against "
                        "the 15:40→16:00 pre-fix drift direction. Secondary is the "
                        "same measure for the contrast day set."
                    ),
                )
            )
    return rows or [_data_required("H106", "month_end_fix_probe", "M1 candle universe")]


def _london_at(day: date, hour: int, minute: int) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=_LONDON_ZONE)


def _close_near(times: list[datetime], closes: list[float], target: datetime) -> float | None:
    """Close of the last candle at or before ``target`` within the tolerance."""
    position = bisect_right(times, target) - 1
    if position < 0 or target - times[position] > _FIX_TOLERANCE:
        return None
    value = closes[position]
    return value if value > 0 else None


def _is_last_business_day(day: date) -> bool:
    following = day + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return following.month != day.month


def _tercile_rows(records: list[tuple[float, float]]) -> list[DirectionRow]:
    if len(records) < 60:
        return [_data_required("H109", "regime_resurrection_probe", "FX universe")]
    ordered = sorted(records, key=lambda item: item[0])
    terciles = (
        ("low-vol", ordered[: len(ordered) // 3]),
        ("mid-vol", ordered[len(ordered) // 3 : 2 * len(ordered) // 3]),
        ("high-vol", ordered[2 * len(ordered) // 3 :]),
    )
    return [
        _values_row(
            "H109",
            "regime_resurrection_probe",
            "Regime-conditioned dead-signal resurrection",
            _status_from_values([value for _, value in bucket]),
            subject,
            "inverse_momentum_return_by_vol_tercile",
            "bps",
            [value for _, value in bucket],
            secondary=float(len(bucket)),
            details=(
                "Effect is 5d cross-sectional reversal bps after sorting by previous "
                "daily basket-vol tercile."
            ),
        )
        for subject, bucket in terciles
        if bucket
    ]


def _data_required(hypothesis_id: str, algorithm_id: str, subject: str) -> DirectionRow:
    labels = {
        "H109": "Regime-conditioned dead-signal resurrection",
        "H112": "Currency-network lead/lag propagation",
        "H114": "Cross-pair sweep divergence",
        "H106": "Month-end London fix reversal",
    }
    return _row(
        hypothesis_id,
        algorithm_id,
        labels.get(hypothesis_id, algorithm_id),
        "data_required",
        subject,
        "minimum_history",
        "count",
        count=0,
        effect=0,
        secondary=0,
        t_stat=0,
        details="Insufficient aligned data for this probe.",
    )


def _corr_row(
    hypothesis_id: str,
    algorithm_id: str,
    label: str,
    subject: str,
    metric: str,
    xs: list[float],
    ys: list[float],
    *,
    threshold: float,
    secondary: float | None = None,
    details: str,
) -> DirectionRow:
    corr = _corr(xs, ys)
    return _row(
        hypothesis_id,
        algorithm_id,
        label,
        _status_from_corr(corr, len(xs), threshold=threshold),
        subject,
        metric,
        "corr",
        count=len(xs),
        effect=corr,
        secondary=_r2(xs, ys) if secondary is None else secondary,
        t_stat=_corr_t_stat(corr, len(xs)),
        details=details,
    )


def _values_row(
    hypothesis_id: str,
    algorithm_id: str,
    label: str,
    status: str,
    subject: str,
    metric: str,
    unit: str,
    values: list[float],
    *,
    secondary: float,
    details: str,
) -> DirectionRow:
    return _row(
        hypothesis_id,
        algorithm_id,
        label,
        status,
        subject,
        metric,
        unit,
        count=len(values),
        effect=_mean(values),
        secondary=secondary,
        t_stat=_t_stat(values),
        details=details,
    )


def _row(
    hypothesis_id: str,
    algorithm_id: str,
    label: str,
    status: str,
    subject: str,
    metric: str,
    unit: str,
    *,
    count: int,
    effect: float,
    secondary: float,
    t_stat: float,
    details: str,
) -> DirectionRow:
    return DirectionRow(
        hypothesis_id=hypothesis_id,
        algorithm_id=algorithm_id,
        label=label,
        status=status,
        subject=subject,
        metric=metric,
        unit=unit,
        stats=DirectionStats(count=count, effect=effect, secondary=secondary, t_stat=t_stat),
        details=details,
    )


def _status_from_values(values: list[float]) -> str:
    t_stat = _t_stat(values)
    if len(values) >= 30 and t_stat >= 2:
        return "candidate"
    return "weak" if values else "data_required"


def _status_from_corr(corr: float, count: int, *, threshold: float) -> str:
    if count < 30:
        return "data_required"
    return "candidate" if abs(corr) >= threshold else "weak"


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def _t_stat(values: list[float]) -> float:
    sigma = _stddev(values)
    if len(values) < 2 or sigma == 0:
        return 0.0
    return _mean(values) / (sigma / sqrt(len(values)))


def _corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        return 0.0
    xbar, ybar = _mean(xs), _mean(ys)
    xdev = [x - xbar for x in xs]
    ydev = [y - ybar for y in ys]
    denom = sqrt(sum(x * x for x in xdev) * sum(y * y for y in ydev))
    if denom == 0:
        return 0.0
    return sum(x * y for x, y in zip(xdev, ydev, strict=True)) / denom


def _corr_t_stat(corr: float, count: int) -> float:
    if count < 3 or abs(corr) >= 1:
        return 0.0
    return corr * sqrt((count - 2) / (1 - corr * corr))


def _two_sided_p(t_stat: float) -> float:
    return erfc(abs(t_stat) / sqrt(2.0))


def _bh_q_values(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg step-up q-values in the input order."""
    count = len(p_values)
    order = sorted(range(count), key=lambda idx: p_values[idx])
    q_values = [0.0] * count
    running = 1.0
    for reverse_rank, idx in enumerate(reversed(order)):
        rank = count - reverse_rank
        running = min(running, p_values[idx] * count / rank)
        q_values[idx] = running
    return q_values


def _r2(xs: list[float], ys: list[float]) -> float:
    corr = _corr(xs, ys)
    return corr * corr


def _top_tercile_hit(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 9:
        return 0.0
    x_cut = _quantile(xs, 2 / 3)
    y_cut = _quantile(ys, 2 / 3)
    predicted = [idx for idx, value in enumerate(xs) if value >= x_cut]
    if not predicted:
        return 0.0
    hits = sum(1 for idx in predicted if ys[idx] >= y_cut)
    return hits / len(predicted)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
    return ordered[idx]
