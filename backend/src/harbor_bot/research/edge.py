"""Base-rate conditional-edge study (pure).

Reuses the strategy's sweep detection to ask the prior question behind ADR 0005:
after a session level is swept, is the next ``horizon`` minutes' move in the
reversal direction skewed better than chance? Returns forward-return summaries
conditioned by level type, session, and volatility, against an unconditional
baseline. No I/O — candles are passed in by the caller.

Edge verdict: a conditioned group carries an edge only when it has at least
``MIN_SAMPLES`` observations, a positive mean reversal, and a one-sample
t-statistic against the chance null (mean = 0) past ``T_THRESHOLD`` — a
significance test, not a bare hit-rate. Hit-rate and the unconditional baseline
move are reported for context. Caveat: forward windows from sweeps close in time
can overlap, which inflates the t-statistic; sweeps are limited to one per level
per day, and a block-bootstrap correction is tracked in the backlog.
"""

from dataclasses import dataclass
from datetime import UTC, date
from decimal import Decimal
from typing import Any

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    Bias,
    DayState,
    InstrumentRules,
    LevelName,
    StrategyConfig,
    require_closed_candle,
)
from harbor_bot.strategy.sessions import (
    compute_session_levels,
    is_in_ny_trade_window,
    session_windows_for_date,
    trading_date_for_candle,
)
from harbor_bot.strategy.sweeps import detect_sweep, mark_level_taken

MIN_SAMPLES = 30
# One-sided t against the chance null (mean reversal = 0). ~2.0 ≈ 97.5% for
# moderate samples; a conditioned slice must beat noise, not merely lean positive.
T_THRESHOLD = Decimal("2.0")
DEFAULT_HORIZON = 15
DEFAULT_ATR_WINDOW = 14


@dataclass(frozen=True)
class ForwardSummary:
    count: int
    mean_pips: Decimal
    median_pips: Decimal
    hit_rate: Decimal
    stddev_pips: Decimal
    t_stat: Decimal

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean_pips": str(self.mean_pips),
            "median_pips": str(self.median_pips),
            "hit_rate": str(self.hit_rate),
            "stddev_pips": str(self.stddev_pips),
            "t_stat": str(self.t_stat),
        }


@dataclass(frozen=True)
class ConditionalEdge:
    dimension: str
    value: str
    summary: ForwardSummary
    has_edge: bool

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "summary": self.summary.to_jsonable(),
            "has_edge": self.has_edge,
        }


@dataclass(frozen=True)
class EdgeStudyResult:
    instrument: str
    horizon: int
    total_candles: int
    total_sweeps: int
    overall: ForwardSummary
    has_edge: bool
    baseline_mean_abs_pips: Decimal
    by_level: tuple[ConditionalEdge, ...]
    by_session: tuple[ConditionalEdge, ...]
    by_volatility: tuple[ConditionalEdge, ...]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "horizon": self.horizon,
            "total_candles": self.total_candles,
            "total_sweeps": self.total_sweeps,
            "overall": self.overall.to_jsonable(),
            "has_edge": self.has_edge,
            "baseline_mean_abs_pips": str(self.baseline_mean_abs_pips),
            "by_level": [edge.to_jsonable() for edge in self.by_level],
            "by_session": [edge.to_jsonable() for edge in self.by_session],
            "by_volatility": [edge.to_jsonable() for edge in self.by_volatility],
        }


@dataclass(frozen=True)
class _Observation:
    index: int
    level_name: LevelName
    bias: Bias
    reversal_pips: Decimal
    atr_pips: Decimal


def summarize(values: list[Decimal]) -> ForwardSummary:
    if not values:
        return ForwardSummary(0, *([Decimal("0")] * 5))
    count = len(values)
    mean = sum(values, Decimal("0")) / Decimal(count)
    wins = sum(1 for value in values if value > 0)
    stddev = _stddev(values, mean)
    return ForwardSummary(
        count=count,
        mean_pips=mean,
        median_pips=_median(values),
        hit_rate=Decimal(wins) / Decimal(count),
        stddev_pips=stddev,
        t_stat=_t_stat(mean, stddev, count),
    )


def has_edge(summary: ForwardSummary) -> bool:
    """An edge requires a statistically significant positive reversal, not just
    a favourable hit-rate: enough samples, a positive mean, and a t-statistic
    against the chance null (mean = 0) past ``T_THRESHOLD``."""
    return summary.count >= MIN_SAMPLES and summary.mean_pips > 0 and summary.t_stat >= T_THRESHOLD


def _stddev(values: list[Decimal], mean: Decimal) -> Decimal:
    if len(values) < 2:
        return Decimal("0")
    variance = sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(
        len(values) - 1
    )
    return variance.sqrt()


def _t_stat(mean: Decimal, stddev: Decimal, count: int) -> Decimal:
    if count < 2 or stddev <= 0:
        return Decimal("0")
    standard_error = stddev / Decimal(count).sqrt()
    return mean / standard_error


def run_edge_study(
    candles: list[ClosedCandle],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    horizon: int = DEFAULT_HORIZON,
    atr_window: int = DEFAULT_ATR_WINDOW,
) -> EdgeStudyResult:
    ordered = tuple(
        sorted((require_closed_candle(candle) for candle in candles), key=lambda c: c.ts)
    )
    sweeps = _collect_sweeps(
        ordered, instrument=instrument, config=config, instrument_rules=instrument_rules
    )
    observations = _observations_with_forward(
        sweeps,
        candles=ordered,
        horizon=horizon,
        atr_window=atr_window,
        instrument_rules=instrument_rules,
    )
    overall = summarize([obs.reversal_pips for obs in observations])
    return EdgeStudyResult(
        instrument=instrument,
        horizon=horizon,
        total_candles=len(ordered),
        total_sweeps=len(sweeps),
        overall=overall,
        has_edge=has_edge(overall),
        baseline_mean_abs_pips=_baseline_abs_pips(
            ordered, horizon=horizon, instrument_rules=instrument_rules
        ),
        by_level=_conditional("level", observations, lambda obs: obs.level_name.value),
        by_session=_conditional("session", observations, lambda obs: _session_for(obs.level_name)),
        by_volatility=_conditional("volatility", observations, _volatility_bucket(observations)),
    )


def _collect_sweeps(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> list[tuple[int, Any]]:
    sweeps: list[tuple[int, Any]] = []
    trading_date: date | None = None
    day_state: DayState | None = None
    session_levels = None
    day_history: list[ClosedCandle] = []
    for index, candle in enumerate(candles):
        next_date = trading_date_for_candle(candle, config)
        if next_date != trading_date:
            trading_date, day_state, session_levels, day_history = (
                next_date,
                DayState(trading_date=next_date),
                None,
                [],
            )
        day_history.append(candle)
        if session_levels is None and candle.ts.astimezone(UTC) >= _ny_start(next_date, config):
            session_levels = _try_levels(
                day_history, trading_date=next_date, instrument=instrument, config=config
            )
        if session_levels is None or not is_in_ny_trade_window(
            candle, trading_date=next_date, config=config
        ):
            continue
        sweep = detect_sweep(
            candle,
            levels=session_levels,
            config=config,
            instrument_rules=instrument_rules,
            day_state=day_state,
            candle_index=index,
        )
        if sweep is not None:
            sweeps.append((index, sweep))
            day_state = mark_level_taken(day_state, sweep.level_name)
    return sweeps


def _observations_with_forward(
    sweeps: list[tuple[int, Any]],
    *,
    candles: tuple[ClosedCandle, ...],
    horizon: int,
    atr_window: int,
    instrument_rules: InstrumentRules,
) -> list[_Observation]:
    pip = instrument_rules.pip_size
    observations: list[_Observation] = []
    for index, sweep in sweeps:
        forward_index = index + horizon
        if forward_index >= len(candles):
            continue
        signed = candles[forward_index].c - candles[index].c
        reversal = signed if sweep.bias == Bias.BULLISH else -signed
        observations.append(
            _Observation(
                index=index,
                level_name=sweep.level_name,
                bias=sweep.bias,
                reversal_pips=reversal / pip,
                atr_pips=_atr_pips(candles, index, atr_window, instrument_rules),
            )
        )
    return observations


def _conditional(
    dimension: str,
    observations: list[_Observation],
    key: Any,
) -> tuple[ConditionalEdge, ...]:
    grouped: dict[str, list[Decimal]] = {}
    for obs in observations:
        grouped.setdefault(key(obs), []).append(obs.reversal_pips)
    edges = []
    for value in sorted(grouped):
        summary = summarize(grouped[value])
        edges.append(
            ConditionalEdge(
                dimension=dimension, value=value, summary=summary, has_edge=has_edge(summary)
            )
        )
    return tuple(edges)


def _volatility_bucket(observations: list[_Observation]) -> Any:
    atrs = sorted(obs.atr_pips for obs in observations)
    median = _median(atrs) if atrs else Decimal("0")
    return lambda obs: "low" if obs.atr_pips < median else "high"


def _baseline_abs_pips(
    candles: tuple[ClosedCandle, ...], *, horizon: int, instrument_rules: InstrumentRules
) -> Decimal:
    pip = instrument_rules.pip_size
    moves = [
        abs(candles[index + horizon].c - candles[index].c) / pip
        for index in range(len(candles) - horizon)
    ]
    return summarize(moves).mean_pips


def _atr_pips(
    candles: tuple[ClosedCandle, ...], index: int, window: int, instrument_rules: InstrumentRules
) -> Decimal:
    start = max(1, index - window + 1)
    ranges: list[Decimal] = []
    for position in range(start, index + 1):
        current, previous = candles[position], candles[position - 1]
        true_range = max(
            current.h - current.low,
            abs(current.h - previous.c),
            abs(current.low - previous.c),
        )
        ranges.append(true_range)
    if not ranges:
        return Decimal("0")
    return (sum(ranges, Decimal("0")) / Decimal(len(ranges))) / instrument_rules.pip_size


def _try_levels(day_history: list[ClosedCandle], **kwargs: Any) -> Any:
    try:
        return compute_session_levels(day_history, **kwargs)
    except ValueError:
        return None


def _ny_start(trading_date: date, config: StrategyConfig) -> Any:
    return session_windows_for_date(trading_date, config).ny_trade.start


def _session_for(level_name: LevelName) -> str:
    return "asia" if level_name in (LevelName.ASIA_HIGH, LevelName.ASIA_LOW) else "london"


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        return Decimal("0")
    mid = size // 2
    if size % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")
