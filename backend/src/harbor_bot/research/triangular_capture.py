"""Cost-aware triangular residual capture (pure) for H101.

Tests whether the EUR_GBP triangular residual convergence survives execution
costs, across a grid of z-thresholds and holding horizons, in two construction
modes:

- ``direct_eur_gbp``: trade only EUR_GBP, fading the residual (1 leg).
- ``synthetic_triangle``: trade the EUR_GBP vs EUR_USD/GBP_USD residual (3 legs).

Returns are reported in basis points (1 bp = 0.01%) of the captured move, net of
a configurable per-leg cost. No I/O — candles are passed in by the caller.
"""

from dataclasses import dataclass
from math import log, sqrt
from statistics import median
from typing import Any

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.cross_instrument import daily_closes

REQUIRED_INSTRUMENTS = ("EUR_USD", "GBP_USD", "EUR_GBP")
DEFAULT_THRESHOLDS = (1.0, 1.5, 2.0)
DEFAULT_HORIZONS = (1, 3, 5, 10)
DEFAULT_LOOKBACK = 60
DEFAULT_COST_BPS_PER_LEG = 1.5
_LEG_COUNT = {"direct_eur_gbp": 1, "synthetic_triangle": 3}


@dataclass(frozen=True)
class TriangularStats:
    count: int
    hit_rate: float
    mean_gross_bps: float
    mean_net_bps: float
    median_net_bps: float
    total_net_bps: float
    t_stat: float
    first_half_mean_net_bps: float
    second_half_mean_net_bps: float

    def to_jsonable(self) -> dict[str, int | str]:
        return {
            "count": self.count,
            "hit_rate": f"{self.hit_rate:.8f}",
            "mean_gross_bps": f"{self.mean_gross_bps:.8f}",
            "mean_net_bps": f"{self.mean_net_bps:.8f}",
            "median_net_bps": f"{self.median_net_bps:.8f}",
            "total_net_bps": f"{self.total_net_bps:.8f}",
            "t_stat": f"{self.t_stat:.8f}",
            "first_half_mean_net_bps": f"{self.first_half_mean_net_bps:.8f}",
            "second_half_mean_net_bps": f"{self.second_half_mean_net_bps:.8f}",
        }


@dataclass(frozen=True)
class TriangularCaptureRow:
    hypothesis_id: str
    construction: str
    threshold: float
    horizon: int
    leg_count: int
    cost_bps_per_leg: float
    stats: TriangularStats

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "construction": self.construction,
            "threshold": f"{self.threshold:.4f}",
            "horizon": self.horizon,
            "leg_count": self.leg_count,
            "cost_bps_per_leg": f"{self.cost_bps_per_leg:.4f}",
            "stats": self.stats.to_jsonable(),
        }


def run_triangular_capture(
    candles_by_instrument: dict[str, list[ClosedCandle]],
    *,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    constructions: tuple[str, ...] = ("direct_eur_gbp", "synthetic_triangle"),
    lookback: int = DEFAULT_LOOKBACK,
    cost_bps_per_leg: float = DEFAULT_COST_BPS_PER_LEG,
) -> list[TriangularCaptureRow]:
    _validate_params(
        thresholds=thresholds,
        horizons=horizons,
        constructions=constructions,
        lookback=lookback,
        cost_bps_per_leg=cost_bps_per_leg,
    )
    series = _aligned_series(candles_by_instrument)
    rows: list[TriangularCaptureRow] = []
    if series is None:
        return rows
    days, eur_gbp_log, residual = series
    for construction in constructions:
        leg_count = _LEG_COUNT[construction]
        cost = leg_count * cost_bps_per_leg
        for threshold in thresholds:
            for horizon in horizons:
                gross = _capture_returns(
                    days=days,
                    eur_gbp_log=eur_gbp_log,
                    residual=residual,
                    construction=construction,
                    threshold=threshold,
                    horizon=horizon,
                    lookback=lookback,
                )
                net = [value - cost for value in gross]
                rows.append(
                    TriangularCaptureRow(
                        hypothesis_id="H101",
                        construction=construction,
                        threshold=threshold,
                        horizon=horizon,
                        leg_count=leg_count,
                        cost_bps_per_leg=cost_bps_per_leg,
                        stats=_stats(gross=gross, net=net),
                    )
                )
    rows.sort(key=lambda row: row.stats.mean_net_bps, reverse=True)
    return rows


def _aligned_series(
    candles_by_instrument: dict[str, list[ClosedCandle]],
) -> tuple[list[Any], list[float], list[float]] | None:
    maps: dict[str, dict[Any, float]] = {}
    for instrument in REQUIRED_INSTRUMENTS:
        candles = candles_by_instrument.get(instrument)
        if not candles:
            return None
        maps[instrument] = {item.day: item.close for item in daily_closes(candles)}
    days = sorted(set(maps["EUR_USD"]) & set(maps["GBP_USD"]) & set(maps["EUR_GBP"]))
    if not days:
        return None
    eur_gbp_log = [log(maps["EUR_GBP"][day]) for day in days]
    residual = [
        log(maps["EUR_GBP"][day]) - (log(maps["EUR_USD"][day]) - log(maps["GBP_USD"][day]))
        for day in days
    ]
    return days, eur_gbp_log, residual


def _capture_returns(
    *,
    days: list[Any],
    eur_gbp_log: list[float],
    residual: list[float],
    construction: str,
    threshold: float,
    horizon: int,
    lookback: int,
) -> list[float]:
    returns: list[float] = []
    for idx in range(lookback, len(days) - horizon):
        window = residual[idx - lookback : idx]
        sigma = _stddev(window)
        if sigma <= 0:
            continue
        z = (residual[idx] - sum(window) / len(window)) / sigma
        if abs(z) < threshold:
            continue
        direction = -1.0 if z > 0 else 1.0
        if construction == "synthetic_triangle":
            move = residual[idx + horizon] - residual[idx]
        else:
            move = eur_gbp_log[idx + horizon] - eur_gbp_log[idx]
        returns.append(direction * move * 10_000)
    return returns


def _stats(*, gross: list[float], net: list[float]) -> TriangularStats:
    if not net:
        return TriangularStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    count = len(net)
    mean_net = sum(net) / count
    sigma = _stddev(net)
    t_stat = 0.0 if count < 2 or sigma <= 0 else mean_net / (sigma / sqrt(count))
    mid = count // 2
    first = net[:mid]
    second = net[mid:]
    return TriangularStats(
        count=count,
        hit_rate=sum(1 for value in net if value > 0) / count,
        mean_gross_bps=sum(gross) / count,
        mean_net_bps=mean_net,
        median_net_bps=float(median(net)),
        total_net_bps=sum(net),
        t_stat=t_stat,
        first_half_mean_net_bps=(sum(first) / len(first)) if first else 0.0,
        second_half_mean_net_bps=(sum(second) / len(second)) if second else 0.0,
    )


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance)


def _validate_params(
    *,
    thresholds: tuple[float, ...],
    horizons: tuple[int, ...],
    constructions: tuple[str, ...],
    lookback: int,
    cost_bps_per_leg: float,
) -> None:
    if not thresholds or any(threshold <= 0 for threshold in thresholds):
        msg = "thresholds must be positive"
        raise ValueError(msg)
    if not horizons or any(horizon <= 0 for horizon in horizons):
        msg = "horizons must be positive"
        raise ValueError(msg)
    if lookback < 2:
        msg = "lookback must be at least 2"
        raise ValueError(msg)
    if cost_bps_per_leg < 0:
        msg = "cost_bps_per_leg cannot be negative"
        raise ValueError(msg)
    unknown = set(constructions) - set(_LEG_COUNT)
    if unknown:
        msg = f"unknown triangular construction(s): {sorted(unknown)}"
        raise ValueError(msg)
