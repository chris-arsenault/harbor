"""Cross-instrument FX research (pure).

Daily cross-sectional and relative-value tests over aligned instrument closes.
Returns are reported in basis points of basket/log-return, not pips.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import log, sqrt
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import require_closed_candle

_NY_ZONE = ZoneInfo("America/New_York")
_NY_ROLLOVER = time(17, 0)


def ny_trading_day(ts: datetime) -> date:
    """FX trading-day label under the New York 17:00 rollover convention.

    Grouping candles by raw UTC calendar date creates bogus Sunday part-days
    (FX reopens ~17:00 ET Sunday); those hours belong to Monday's trading day.
    """
    local = ts.astimezone(_NY_ZONE)
    if local.timetz().replace(tzinfo=None) >= _NY_ROLLOVER:
        return local.date() + timedelta(days=1)
    return local.date()


@dataclass(frozen=True)
class DailyClose:
    day: date
    close: float


@dataclass(frozen=True)
class CrossObservation:
    day: date
    return_bps: float


@dataclass(frozen=True)
class CrossStats:
    count: int
    hit_rate: float
    mean_return_bps: float
    median_return_bps: float
    total_return_bps: float
    t_stat: float

    def to_jsonable(self) -> dict[str, int | str]:
        return {
            "count": self.count,
            "hit_rate": f"{self.hit_rate:.8f}",
            "mean_return_bps": f"{self.mean_return_bps:.8f}",
            "median_return_bps": f"{self.median_return_bps:.8f}",
            "total_return_bps": f"{self.total_return_bps:.8f}",
            "t_stat": f"{self.t_stat:.8f}",
        }


@dataclass(frozen=True)
class CrossAlgorithm:
    algorithm_id: str
    hypothesis_id: str
    label: str
    description: str
    evaluator: Callable[..., list[CrossObservation]]
    lifecycle: str = "active"

    def to_jsonable(self) -> dict[str, str]:
        return {
            "algorithm_id": self.algorithm_id,
            "hypothesis_id": self.hypothesis_id,
            "label": self.label,
            "description": self.description,
            "lifecycle": self.lifecycle,
        }


@dataclass(frozen=True)
class CrossScanRow:
    algorithm_id: str
    hypothesis_id: str
    algorithm_label: str
    instruments: tuple[str, ...]
    observation_count: int
    stats: CrossStats

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "hypothesis_id": self.hypothesis_id,
            "algorithm_label": self.algorithm_label,
            "instruments": list(self.instruments),
            "observation_count": self.observation_count,
            "stats": self.stats.to_jsonable(),
        }


def available_cross_algorithms() -> tuple[CrossAlgorithm, ...]:
    return (
        CrossAlgorithm(
            algorithm_id="cs_momentum_20d_5d",
            hypothesis_id="H100",
            label="Cross-sectional momentum 20d→5d",
            description=(
                "Archived rejected hypothesis: long top recent 20-day performers, "
                "short bottom performers, hold 5 trading days."
            ),
            evaluator=_cs_momentum,
            lifecycle="archived",
        ),
        CrossAlgorithm(
            algorithm_id="cs_value_60d_5d",
            hypothesis_id="H100",
            label="Cross-sectional value/reversion 60d→5d",
            description=(
                "Archived weak hypothesis: long 60-day underperformers, short "
                "outperformers, hold 5 trading days."
            ),
            evaluator=_cs_value,
            lifecycle="archived",
        ),
        CrossAlgorithm(
            algorithm_id="cs_reversal_20d_5d_tranched",
            hypothesis_id="H113",
            label="Cross-sectional reversal 20d→5d, vol-scaled, 5 tranches",
            description=(
                "Long recent 20-day losers, short winners (the inverse of the "
                "significantly negative H100 momentum), inverse-vol weighted legs, "
                "risk split across 5 staggered daily tranches so observations are "
                "non-overlapping daily portfolio returns."
            ),
            evaluator=_cs_reversal_tranched,
            lifecycle="active",
        ),
        CrossAlgorithm(
            algorithm_id="tri_eur_gbp_residual_5d",
            hypothesis_id="H101",
            label="EUR/GBP triangular residual convergence",
            description=(
                "Archived paused hypothesis: trade convergence of EUR_GBP vs "
                "EUR_USD / GBP_USD residual."
            ),
            evaluator=_tri_eur_gbp,
            lifecycle="archived",
        ),
        CrossAlgorithm(
            algorithm_id="usd_dispersion_reversion_5d",
            hypothesis_id="H102",
            label="USD-factor dispersion reversion",
            description=(
                "Archived rejected hypothesis: long underperforming pairs and short "
                "outperforming pairs versus basket residual."
            ),
            evaluator=_usd_dispersion,
            lifecycle="archived",
        ),
    )


def default_cross_algorithm_ids() -> tuple[str, ...]:
    return tuple(
        algorithm.algorithm_id
        for algorithm in available_cross_algorithms()
        if algorithm.lifecycle == "active"
    )


def get_cross_algorithm(algorithm_id: str) -> CrossAlgorithm:
    by_id = {algorithm.algorithm_id: algorithm for algorithm in available_cross_algorithms()}
    try:
        return by_id[algorithm_id]
    except KeyError as exc:
        msg = f"unknown cross algorithm {algorithm_id!r}"
        raise ValueError(msg) from exc


def run_cross_scan(
    candles_by_instrument: dict[str, list[ClosedCandle]],
    *,
    algorithm_ids: tuple[str, ...] | None = None,
) -> list[CrossScanRow]:
    closes = {
        instrument: daily_closes(candles)
        for instrument, candles in candles_by_instrument.items()
        if candles
    }
    rows: list[CrossScanRow] = []
    for algorithm_id in algorithm_ids or default_cross_algorithm_ids():
        algorithm = get_cross_algorithm(algorithm_id)
        observations = algorithm.evaluator(closes)
        rows.append(
            CrossScanRow(
                algorithm_id=algorithm.algorithm_id,
                hypothesis_id=algorithm.hypothesis_id,
                algorithm_label=algorithm.label,
                instruments=tuple(sorted(closes)),
                observation_count=len(observations),
                stats=_stats([obs.return_bps for obs in observations]),
            )
        )
    return sorted(rows, key=lambda row: row.stats.t_stat, reverse=True)


def daily_closes(candles: list[ClosedCandle]) -> list[DailyClose]:
    by_day: dict[date, ClosedCandle] = {}
    for candle in sorted(candles, key=lambda item: item.ts):
        require_closed_candle(candle)
        by_day[ny_trading_day(candle.ts)] = candle
    return [DailyClose(day=day, close=float(candle.c)) for day, candle in sorted(by_day.items())]


def _aligned_maps(closes: dict[str, list[DailyClose]]) -> dict[str, dict[date, float]]:
    return {
        instrument: {item.day: item.close for item in rows} for instrument, rows in closes.items()
    }


def _common_days(maps: dict[str, dict[date, float]], instruments: list[str]) -> list[date]:
    if not instruments:
        return []
    if any(instrument not in maps for instrument in instruments):
        return []
    days = set(maps[instruments[0]])
    for instrument in instruments[1:]:
        days &= set(maps.get(instrument, {}))
    return sorted(days)


def _cs_momentum(closes: dict[str, list[DailyClose]]) -> list[CrossObservation]:
    return _cross_section_rank(closes, lookback=20, horizon=5, reverse=False)


def _cs_value(closes: dict[str, list[DailyClose]]) -> list[CrossObservation]:
    return _cross_section_rank(closes, lookback=60, horizon=5, reverse=True)


def _cs_reversal_tranched(closes: dict[str, list[DailyClose]]) -> list[CrossObservation]:
    """H113: cross-sectional reversal as a daily tranched portfolio.

    H100 measured 20d cross-sectional momentum at t=-2.14 — a reversal signal.
    This promotes the inverse with three structural upgrades: inverse-vol
    weighted legs (equal risk, so JPY crosses do not dominate), long losers /
    short winners, and one-fifth of risk rebalanced each day on a 5-day hold.
    Observations are non-overlapping one-day portfolio returns, so the t-stat
    needs no overlap correction. Weights at day t use data through t only; the
    return is measured t→t+1.
    """
    lookback, horizon, vol_window = 20, 5, 20
    maps = _aligned_maps(closes)
    instruments = sorted(maps)
    days = _common_days(maps, instruments)
    start = lookback + vol_window
    if len(instruments) < 4 or len(days) <= start + 1:
        return []
    leg_count = max(1, len(instruments) // 4)
    daily_returns: dict[str, dict[date, float]] = {instrument: {} for instrument in instruments}
    for idx in range(1, len(days)):
        for instrument in instruments:
            daily_returns[instrument][days[idx]] = log(
                maps[instrument][days[idx]] / maps[instrument][days[idx - 1]]
            )

    def rebalance_weights(idx: int) -> dict[str, float]:
        scores: list[tuple[str, float]] = []
        inverse_vol: dict[str, float] = {}
        for instrument in instruments:
            momentum = log(maps[instrument][days[idx]] / maps[instrument][days[idx - lookback]])
            recent = [
                daily_returns[instrument][days[position]]
                for position in range(idx - vol_window + 1, idx + 1)
            ]
            sigma = max(_stddev(recent), 1e-6)
            scores.append((instrument, momentum))
            inverse_vol[instrument] = 1.0 / sigma
        ranked = sorted(scores, key=lambda item: item[1], reverse=True)
        winners = [instrument for instrument, _ in ranked[:leg_count]]
        losers = [instrument for instrument, _ in ranked[-leg_count:]]
        long_mass = sum(inverse_vol[instrument] for instrument in losers)
        short_mass = sum(inverse_vol[instrument] for instrument in winners)
        weights = {instrument: inverse_vol[instrument] / long_mass for instrument in losers}
        weights.update(
            {instrument: -inverse_vol[instrument] / short_mass for instrument in winners}
        )
        return weights

    tranches: dict[int, dict[str, float]] = {}
    observations: list[CrossObservation] = []
    for idx in range(start, len(days) - 1):
        tranches[(idx - start) % horizon] = rebalance_weights(idx)
        tranche_returns = [
            sum(
                weight * daily_returns[instrument][days[idx + 1]]
                for instrument, weight in weights.items()
            )
            for weights in tranches.values()
        ]
        portfolio_return = sum(tranche_returns) / len(tranche_returns)
        observations.append(
            CrossObservation(day=days[idx + 1], return_bps=portfolio_return * 10_000)
        )
    return observations


def _cross_section_rank(
    closes: dict[str, list[DailyClose]], *, lookback: int, horizon: int, reverse: bool
) -> list[CrossObservation]:
    maps = _aligned_maps(closes)
    instruments = sorted(maps)
    days = _common_days(maps, instruments)
    observations: list[CrossObservation] = []
    if len(instruments) < 4:
        return observations
    leg_count = max(1, len(instruments) // 4)
    for idx in range(lookback, len(days) - horizon):
        day = days[idx]
        scores = []
        for instrument in instruments:
            prior = maps[instrument][days[idx - lookback]]
            current = maps[instrument][day]
            scores.append((instrument, log(current / prior)))
        ranked = sorted(scores, key=lambda item: item[1], reverse=not reverse)
        longs = [instrument for instrument, _ in ranked[:leg_count]]
        shorts = [instrument for instrument, _ in ranked[-leg_count:]]
        forward = _basket_forward(maps, days, idx, horizon, longs=longs, shorts=shorts)
        observations.append(CrossObservation(day=day, return_bps=forward * 10_000))
    return observations


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


def _tri_eur_gbp(closes: dict[str, list[DailyClose]]) -> list[CrossObservation]:
    required = ["EUR_USD", "GBP_USD", "EUR_GBP"]
    maps = _aligned_maps(closes)
    days = _common_days(maps, required)
    residuals = [
        log(maps["EUR_GBP"][day]) - (log(maps["EUR_USD"][day]) - log(maps["GBP_USD"][day]))
        for day in days
    ]
    observations: list[CrossObservation] = []
    lookback, horizon, threshold = 60, 5, 1.5
    for idx in range(lookback, len(days) - horizon):
        window = residuals[idx - lookback : idx]
        sigma = _stddev(window)
        if sigma <= 0:
            continue
        z = (residuals[idx] - sum(window) / len(window)) / sigma
        if abs(z) < threshold:
            continue
        convergence = -(1 if z > 0 else -1) * (residuals[idx + horizon] - residuals[idx])
        observations.append(CrossObservation(day=days[idx], return_bps=convergence * 10_000))
    return observations


def _usd_dispersion(closes: dict[str, list[DailyClose]]) -> list[CrossObservation]:
    maps = _aligned_maps(closes)
    instruments = sorted(instrument for instrument in maps if _usd_orientation(instrument) != 0)
    days = _common_days(maps, instruments)
    observations: list[CrossObservation] = []
    if len(instruments) < 4:
        return observations
    lookback, horizon = 5, 5
    leg_count = max(1, len(instruments) // 4)
    for idx in range(lookback, len(days) - horizon):
        recent = {
            instrument: _usd_oriented_return(maps, instrument, days[idx - lookback], days[idx])
            for instrument in instruments
        }
        mean = sum(recent.values()) / len(recent)
        residuals = sorted(
            ((instrument, value - mean) for instrument, value in recent.items()),
            key=lambda item: item[1],
        )
        if residuals[-1][1] - residuals[0][1] <= 1e-8:
            continue
        longs = [instrument for instrument, _ in residuals[:leg_count]]
        shorts = [instrument for instrument, _ in residuals[-leg_count:]]
        forward = _usd_oriented_basket_forward(maps, days, idx, horizon, longs=longs, shorts=shorts)
        observations.append(CrossObservation(day=days[idx], return_bps=forward * 10_000))
    return observations


def _usd_orientation(instrument: str) -> int:
    if instrument.endswith("_USD"):
        return 1
    if instrument.startswith("USD_"):
        return -1
    return 0


def _usd_oriented_return(
    maps: dict[str, dict[date, float]], instrument: str, start: date, end: date
) -> float:
    return _usd_orientation(instrument) * log(maps[instrument][end] / maps[instrument][start])


def _usd_oriented_basket_forward(
    maps: dict[str, dict[date, float]],
    days: list[date],
    idx: int,
    horizon: int,
    *,
    longs: list[str],
    shorts: list[str],
) -> float:
    start, end = days[idx], days[idx + horizon]
    long_return = sum(_usd_oriented_return(maps, instrument, start, end) for instrument in longs)
    short_return = sum(_usd_oriented_return(maps, instrument, start, end) for instrument in shorts)
    return (long_return / len(longs)) - (short_return / len(shorts))


def _stats(values: list[float]) -> CrossStats:
    if not values:
        return CrossStats(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    count = len(values)
    mean = sum(values) / count
    sigma = _stddev(values)
    t_stat = 0.0 if count < 2 or sigma <= 0 else mean / (sigma / sqrt(count))
    return CrossStats(
        count=count,
        hit_rate=sum(1 for value in values if value > 0) / count,
        mean_return_bps=mean,
        median_return_bps=float(median(values)),
        total_return_bps=sum(values),
        t_stat=t_stat,
    )


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance)
