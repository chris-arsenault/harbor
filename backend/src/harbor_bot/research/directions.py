"""Creative next-wave research probes for H108-H112 (pure)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import log, sqrt
from typing import Any

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.cross_instrument import DailyClose, daily_closes
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
        rows.extend(_weekend_gap(closes))
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
    return _rank_rows(rows)


def daily_bars(candles: list[ClosedCandle]) -> list[DailyBar]:
    grouped: dict[date, list[ClosedCandle]] = {}
    for candle in sorted(candles, key=lambda item: item.ts):
        require_closed_candle(candle)
        grouped.setdefault(candle.ts.date(), []).append(candle)
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


def _weekend_gap(closes: dict[str, list[DailyClose]]) -> list[DirectionRow]:
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
        fx_days = sorted(set(maps[instrument]) & set(proxy_by_day))
        xs: list[float] = []
        ys: list[float] = []
        fx = maps[instrument]
        for day in fx_days:
            if day.weekday() != 0:
                continue
            fday = date.fromordinal(day.toordinal() - 3)
            sday = date.fromordinal(day.toordinal() - 1)
            pday = date.fromordinal(day.toordinal() - 1)
            if fday not in proxy_by_day or sday not in proxy_by_day or pday not in fx:
                continue
            xs.append(log(proxy_by_day[sday] / proxy_by_day[fday]))
            ys.append(log(fx[day] / fx[pday]))
        rows.append(
            _corr_row(
                "H108",
                "weekend_risk_gap_probe",
                "Weekend risk-asset gap lead",
                instrument,
                "corr(weekend_proxy,monday_fx)",
                xs,
                ys,
                threshold=0.15,
                details=(
                    f"Proxy={proxy}; secondary=R²; Monday daily return approximates "
                    "reopen/early-week FX repricing."
                ),
            )
        )
    return rows


def _regime_resurrection(closes: dict[str, list[DailyClose]]) -> list[DirectionRow]:
    maps = _daily_maps({k: v for k, v in closes.items() if k in FX_MAJORS})
    instruments = sorted(maps)
    days = _common_days(maps, instruments)
    if len(instruments) < 4 or len(days) < 80:
        return [_data_required("H109", "regime_resurrection_probe", "FX universe")]
    lookback, horizon = 20, 5
    records: list[tuple[float, float]] = []
    for idx in range(lookback, len(days) - horizon):
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


def _range_forecast(bars_by_instrument: dict[str, list[DailyBar]]) -> list[DirectionRow]:
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
        xs = ranges[:-1]
        ys = ranges[1:]
        top_hit = _top_tercile_hit(xs, ys)
        rows.append(
            _corr_row(
                "H110",
                "range_forecast_probe",
                "Next-session range forecast",
                instrument,
                "corr(prev_daily_range,next_daily_range)",
                xs,
                ys,
                threshold=0.15,
                secondary=top_hit,
                details=(
                    "Effect is correlation of prior daily high-low range vs next daily range. "
                    "Secondary is top-tercile range hit-rate among predicted high-range days."
                ),
            )
        )
    return sorted(rows, key=lambda row: float(row.stats.secondary), reverse=True)[:8]


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
            if state is None or abs(state.net_long_pct) < 10:
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
    return rows


def _position_states(book_snapshots: list[dict[str, Any]]) -> dict[str, list[BookState]]:
    by_instrument: dict[str, list[BookState]] = {}
    for row in book_snapshots:
        if row.get("book_type") != "position":
            continue
        buckets = row.get("buckets_json") or []
        net = 0.0
        for bucket in buckets:
            net += float(bucket.get("long_pct") or 0) - float(bucket.get("short_pct") or 0)
        by_instrument.setdefault(str(row["instrument"]), []).append(
            BookState(
                book_type="position",
                instrument=str(row["instrument"]),
                snapshot_time=row["snapshot_time"],
                net_long_pct=net * 100 if abs(net) <= 1.5 else net,
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
    rows: list[DirectionRow] = []
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
                corr = _corr(xs, ys)
                rows.append(
                    _corr_row(
                        "H112",
                        "lead_lag_network_probe",
                        "Currency-network lead/lag propagation",
                        f"{leader}→{lagger} +{lag}d",
                        "lead_lag_corr",
                        xs,
                        ys,
                        threshold=0.12,
                        secondary=abs(corr),
                        details=(
                            "Effect is correlation between leader return at t and lagger return "
                            "at t+lag; t-stat is correlation significance, not return t."
                        ),
                    )
                )
    return sorted(rows, key=lambda row: abs(row.stats.effect), reverse=True)[:12] or [
        _data_required("H112", "lead_lag_network_probe", "FX universe")
    ]


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
