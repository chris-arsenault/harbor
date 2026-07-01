"""Creative next-wave research probes for H108-H112 (pure).

These probes intentionally change the statistical object away from the archived
single-pair price-pattern family. They are exploratory gates: compact,
pre-registered diagnostics that say whether a research direction deserves a
larger build-out.
"""

from dataclasses import dataclass
from datetime import date
from math import log, sqrt
from typing import Any

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.cross_instrument import DailyClose, daily_closes

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
            "description": "Predict next daily realized range from prior range persistence.",
        },
        {
            "algorithm_id": "book_conditioner_readiness",
            "hypothesis_id": "H111",
            "label": "Book-conditioned sweep readiness",
            "description": (
                "Check whether H103 order/position-book coverage is ready for conditioning."
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
) -> list[DirectionRow]:
    requested = set(algorithm_ids or default_direction_algorithm_ids())
    closes = {
        instrument: daily_closes(candles)
        for instrument, candles in candles_by_instrument.items()
        if candles
    }
    rows: list[DirectionRow] = []
    if "weekend_risk_gap_probe" in requested:
        rows.extend(_weekend_gap(closes))
    if "regime_resurrection_probe" in requested:
        rows.extend(_regime_resurrection(closes))
    if "range_forecast_probe" in requested:
        rows.extend(_range_forecast(closes))
    if "book_conditioner_readiness" in requested:
        rows.extend(_book_readiness(book_coverage or []))
    if "lead_lag_network_probe" in requested:
        rows.extend(_lead_lag(closes))
    return _rank_rows(rows)


def _rank_rows(rows: list[DirectionRow]) -> list[DirectionRow]:
    def key(row: DirectionRow) -> tuple[int, float, int]:
        status_rank = {"candidate": 0, "ready": 1, "weak": 2, "collecting": 3, "data_required": 4}
        return (status_rank.get(row.status, 9), -abs(row.stats.t_stat), -row.stats.count)

    return sorted(rows, key=key)


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
                [],
                effect=0,
                secondary=0,
                details=(
                    "No 24/7 risk proxy candles found; add crypto/index data before "
                    "testing weekend information gaps."
                ),
            )
        ]

    maps = _daily_maps(closes)
    proxy_days = sorted(maps[proxy])
    proxy_by_day = maps[proxy]
    rows: list[DirectionRow] = []
    for instrument in sorted(FX_MAJORS & closes.keys()):
        fx_days = sorted(set(maps[instrument]) & set(proxy_days))
        xs: list[float] = []
        ys: list[float] = []
        fx = maps[instrument]
        for day in fx_days:
            if day.weekday() != 0:  # Monday UTC proxy for post-weekend FX session.
                continue
            friday = day.toordinal() - 3
            sunday = day.toordinal() - 1
            monday_prev = day.toordinal() - 1
            fday = date.fromordinal(friday)
            sday = date.fromordinal(sunday)
            pday = date.fromordinal(monday_prev)
            if fday not in proxy_by_day or sday not in proxy_by_day or pday not in fx:
                continue
            xs.append(log(proxy_by_day[sday] / proxy_by_day[fday]))
            ys.append(log(fx[day] / fx[pday]))
        corr = _corr(xs, ys)
        rows.append(
            _row(
                "H108",
                "weekend_risk_gap_probe",
                "Weekend risk-asset gap lead",
                _status_from_corr(corr, len(xs)),
                instrument,
                "corr(weekend_proxy,monday_fx)",
                "corr",
                ys,
                effect=corr,
                secondary=_r2(xs, ys),
                details=(
                    f"Proxy={proxy}; secondary=R²; Monday daily return approximates "
                    "reopen/early-week FX repricing."
                ),
            )
        )
    return rows or [
        _row(
            "H108",
            "weekend_risk_gap_probe",
            "Weekend risk-asset gap lead",
            "data_required",
            proxy,
            "weekend_overlap",
            "count",
            [],
            effect=0,
            secondary=0,
            details="Risk proxy exists but no Friday→Sunday proxy / Monday FX overlap was found.",
        )
    ]


def _regime_resurrection(closes: dict[str, list[DailyClose]]) -> list[DirectionRow]:
    maps = _daily_maps({k: v for k, v in closes.items() if k in FX_MAJORS})
    instruments = sorted(maps)
    days = _common_days(maps, instruments)
    if len(instruments) < 4 or len(days) < 80:
        return [
            _row(
                "H109",
                "regime_resurrection_probe",
                "Regime-conditioned dead-signal resurrection",
                "data_required",
                "FX universe",
                "minimum_daily_history",
                "count",
                [],
                effect=0,
                secondary=0,
                details="Need at least four aligned FX instruments and ~80 daily closes.",
            )
        ]
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
        momentum = _basket_forward(maps, days, idx, horizon, longs=longs, shorts=shorts)
        regime_score = sum(abs_returns) / len(abs_returns)
        records.append((regime_score, -momentum * 10_000))  # inverse momentum / reversal bps.
    return _tercile_rows(
        records,
        hypothesis_id="H109",
        algorithm_id="regime_resurrection_probe",
        label="Regime-conditioned dead-signal resurrection",
        unit="bps",
        metric="inverse_momentum_return_by_vol_tercile",
        details=(
            "Effect is 5d cross-sectional reversal bps after sorting by previous "
            "daily basket-vol tercile."
        ),
    )


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


def _range_forecast(closes: dict[str, list[DailyClose]]) -> list[DirectionRow]:
    rows: list[DirectionRow] = []
    for instrument, daily in sorted(closes.items()):
        if instrument not in FX_MAJORS:
            continue
        # DailyClose stores closes only, so this probe currently measures close-to-close absolute
        # range persistence. Service/API label calls it realized movement until OHLC aggregation is
        # expanded to expose true daily high/low.
        ordered = sorted(daily, key=lambda item: item.day)
        moves = [
            abs(log(ordered[idx].close / ordered[idx - 1].close)) * 10_000
            for idx in range(1, len(ordered))
        ]
        xs = moves[:-1]
        ys = moves[1:]
        corr = _corr(xs, ys)
        rows.append(
            _row(
                "H110",
                "range_forecast_probe",
                "Next-session movement forecast",
                _status_from_corr(corr, len(xs)),
                instrument,
                "corr(prev_abs_return,next_abs_return)",
                "corr",
                ys,
                effect=corr,
                secondary=_r2(xs, ys),
                details=(
                    "Secondary=R². Uses close-to-close absolute return as a first volatility proxy."
                ),
            )
        )
    return sorted(rows, key=lambda row: float(row.stats.secondary), reverse=True)[:8]


def _book_readiness(book_coverage: list[dict[str, Any]]) -> list[DirectionRow]:
    if not book_coverage:
        return [
            _row(
                "H111",
                "book_conditioner_readiness",
                "Book-conditioned sweep readiness",
                "collecting",
                "OANDA books",
                "snapshot_count",
                "snapshots",
                [],
                effect=0,
                secondary=0,
                details=(
                    "No book coverage rows yet; let H103 recorder accumulate order "
                    "and position snapshots."
                ),
            )
        ]
    by_instrument: dict[str, dict[str, int]] = {}
    for row in book_coverage:
        by_instrument.setdefault(str(row["instrument"]), {})[str(row["book_type"])] = int(
            row.get("snapshot_count") or 0
        )
    rows = []
    for instrument, counts in sorted(by_instrument.items()):
        order_count = counts.get("order", 0)
        position_count = counts.get("position", 0)
        ready_count = min(order_count, position_count)
        status = "ready" if ready_count >= 500 else "collecting"
        rows.append(
            _row(
                "H111",
                "book_conditioner_readiness",
                "Book-conditioned sweep readiness",
                status,
                instrument,
                "min(order,position)_snapshots",
                "snapshots",
                [],
                effect=float(ready_count),
                secondary=float(order_count + position_count),
                details=(
                    "Need roughly 500 paired snapshots before conditioning sweep "
                    "events on book/position state."
                ),
            )
        )
    return rows


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
                lagger_returns = returns[lagger]
                for day, lead_return in returns[leader].items():
                    target = date.fromordinal(day.toordinal() + lag)
                    if target in lagger_returns:
                        xs.append(lead_return)
                        ys.append(lagger_returns[target])
                corr = _corr(xs, ys)
                if len(xs) < 40:
                    continue
                rows.append(
                    _row(
                        "H112",
                        "lead_lag_network_probe",
                        "Currency-network lead/lag propagation",
                        _status_from_corr(corr, len(xs), threshold=0.12),
                        f"{leader}→{lagger} +{lag}d",
                        "lead_lag_corr",
                        "corr",
                        ys,
                        effect=corr,
                        secondary=abs(corr),
                        details=(
                            "Effect is daily return correlation between leader at t "
                            "and lagger at t+lag."
                        ),
                    )
                )
    return sorted(rows, key=lambda row: abs(row.stats.effect), reverse=True)[:12] or [
        _row(
            "H112",
            "lead_lag_network_probe",
            "Currency-network lead/lag propagation",
            "data_required",
            "FX universe",
            "minimum_overlap",
            "count",
            [],
            effect=0,
            secondary=0,
            details="Need at least 40 overlapping daily return observations per pair/lag.",
        )
    ]


def _tercile_rows(
    records: list[tuple[float, float]],
    *,
    hypothesis_id: str,
    algorithm_id: str,
    label: str,
    unit: str,
    metric: str,
    details: str,
) -> list[DirectionRow]:
    if len(records) < 60:
        return [
            _row(
                hypothesis_id,
                algorithm_id,
                label,
                "data_required",
                "FX universe",
                metric,
                unit,
                [],
                effect=0,
                secondary=0,
                details="Need at least 60 observations to split into volatility terciles.",
            )
        ]
    ordered = sorted(records, key=lambda item: item[0])
    terciles = (
        ("low-vol", ordered[: len(ordered) // 3]),
        ("mid-vol", ordered[len(ordered) // 3 : 2 * len(ordered) // 3]),
        ("high-vol", ordered[2 * len(ordered) // 3 :]),
    )
    return [
        _row(
            hypothesis_id,
            algorithm_id,
            label,
            _status_from_t([value for _, value in bucket]),
            subject,
            metric,
            unit,
            [value for _, value in bucket],
            effect=_mean([value for _, value in bucket]),
            secondary=float(len(bucket)),
            details=details,
        )
        for subject, bucket in terciles
        if bucket
    ]


def _row(
    hypothesis_id: str,
    algorithm_id: str,
    label: str,
    status: str,
    subject: str,
    metric: str,
    unit: str,
    values: list[float],
    *,
    effect: float | None = None,
    secondary: float = 0,
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
        stats=DirectionStats(
            count=len(values),
            effect=_mean(values) if effect is None else effect,
            secondary=secondary,
            t_stat=_t_stat(values),
        ),
        details=details,
    )


def _status_from_t(values: list[float]) -> str:
    t_stat = _t_stat(values)
    if len(values) >= 40 and t_stat >= 2:
        return "candidate"
    return "weak" if values else "data_required"


def _status_from_corr(corr: float, count: int, *, threshold: float = 0.15) -> str:
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


def _r2(xs: list[float], ys: list[float]) -> float:
    corr = _corr(xs, ys)
    return corr * corr
