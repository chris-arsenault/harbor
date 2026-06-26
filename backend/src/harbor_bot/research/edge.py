"""Base-rate conditional-edge study (pure).

Reuses the strategy's sweep detection to ask the prior question behind ADR 0005:
after a session level is swept, is the next ``horizon`` minutes' move in the
reversal direction skewed better than chance? Returns forward-return summaries
conditioned by level type, session, and volatility, against an unconditional
baseline. No I/O — candles are passed in by the caller.

Edge verdict: a conditioned group carries an edge only when it has enough
observations, enough independent NY trading-day clusters, a positive mean
reversal, a cluster-robust t-statistic against the chance null (mean = 0), and
a multiple-test-adjusted p-value below the configured alpha. Hit-rate, naive
t-stat, corrected t-stat, and the unconditional baseline move are reported for
context.
"""

from dataclasses import dataclass
from datetime import UTC, date
from decimal import Decimal
from math import erfc, sqrt
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
MIN_EFFECTIVE_SAMPLES = 20
# One-sided t against the chance null (mean reversal = 0). ~2.0 ≈ 97.5% for
# moderate samples; a conditioned slice must beat noise, not merely lean positive.
T_THRESHOLD = Decimal("2.0")
ALPHA = Decimal("0.025")
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
    naive_t_stat: Decimal = Decimal("0")
    standard_error_pips: Decimal = Decimal("0")
    effective_sample_size: int = 0
    p_value: Decimal = Decimal("1")
    bonferroni_p_value: Decimal = Decimal("1")
    correction: str = "iid"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "mean_pips": str(self.mean_pips),
            "median_pips": str(self.median_pips),
            "hit_rate": str(self.hit_rate),
            "stddev_pips": str(self.stddev_pips),
            "t_stat": str(self.t_stat),
            "naive_t_stat": str(self.naive_t_stat),
            "standard_error_pips": str(self.standard_error_pips),
            "effective_sample_size": self.effective_sample_size,
            "p_value": str(self.p_value),
            "bonferroni_p_value": str(self.bonferroni_p_value),
            "correction": self.correction,
        }


@dataclass(frozen=True)
class ConditionalEdge:
    dimension: str
    value: str
    summary: ForwardSummary
    has_edge: bool
    family_test_count: int = 1

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "summary": self.summary.to_jsonable(),
            "has_edge": self.has_edge,
            "family_test_count": self.family_test_count,
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
    statistical_notes: dict[str, Any]

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
            "statistical_notes": self.statistical_notes,
        }


@dataclass(frozen=True)
class _Observation:
    index: int
    trading_date: date
    level_name: LevelName
    bias: Bias
    reversal_pips: Decimal
    atr_pips: Decimal


def summarize(values: list[Decimal]) -> ForwardSummary:
    if not values:
        return _empty_summary()
    count = len(values)
    mean = sum(values, Decimal("0")) / Decimal(count)
    wins = sum(1 for value in values if value > 0)
    stddev = _stddev(values, mean)
    naive_t = _t_stat(mean, stddev, count)
    p_value = _one_sided_p_value(naive_t)
    return ForwardSummary(
        count=count,
        mean_pips=mean,
        median_pips=_median(values),
        hit_rate=Decimal(wins) / Decimal(count),
        stddev_pips=stddev,
        t_stat=naive_t,
        naive_t_stat=naive_t,
        standard_error_pips=_standard_error(stddev, count),
        effective_sample_size=count,
        p_value=p_value,
        bonferroni_p_value=p_value,
    )


def has_edge(summary: ForwardSummary) -> bool:
    """An edge requires a statistically significant positive reversal, not just
    a favourable hit-rate: enough samples, a positive mean, and a t-statistic
    against the chance null (mean = 0) past ``T_THRESHOLD``."""
    return (
        summary.count >= MIN_SAMPLES
        and summary.effective_sample_size >= MIN_EFFECTIVE_SAMPLES
        and summary.mean_pips > 0
        and summary.t_stat >= T_THRESHOLD
        and summary.bonferroni_p_value <= ALPHA
    )


def _stddev(values: list[Decimal], mean: Decimal) -> Decimal:
    if len(values) < 2:
        return Decimal("0")
    variance = sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(
        len(values) - 1
    )
    return variance.sqrt()


def _standard_error(stddev: Decimal, count: int) -> Decimal:
    if count < 2 or stddev <= 0:
        return Decimal("0")
    return stddev / Decimal(count).sqrt()


def _t_stat(mean: Decimal, stddev: Decimal, count: int) -> Decimal:
    if count < 2 or stddev <= 0:
        return Decimal("0")
    standard_error = stddev / Decimal(count).sqrt()
    return mean / standard_error


def _t_stat_from_standard_error(mean: Decimal, standard_error: Decimal) -> Decimal:
    if standard_error <= 0:
        return Decimal("0")
    return mean / standard_error


def _one_sided_p_value(t_stat: Decimal) -> Decimal:
    if t_stat <= 0:
        return Decimal("1")
    value = 0.5 * erfc(float(t_stat) / sqrt(2.0))
    return Decimal(str(value))


def _bonferroni(p_value: Decimal, test_count: int) -> Decimal:
    if test_count <= 1:
        return p_value
    return min(Decimal("1"), p_value * Decimal(test_count))


def _empty_summary() -> ForwardSummary:
    return ForwardSummary(
        count=0,
        mean_pips=Decimal("0"),
        median_pips=Decimal("0"),
        hit_rate=Decimal("0"),
        stddev_pips=Decimal("0"),
        t_stat=Decimal("0"),
        naive_t_stat=Decimal("0"),
        standard_error_pips=Decimal("0"),
        effective_sample_size=0,
        p_value=Decimal("1"),
        bonferroni_p_value=Decimal("1"),
    )


def summarize_observations(observations: list["_Observation"]) -> ForwardSummary:
    """Summarize sweep forward returns with day-cluster-robust standard errors.

    Sweep forward windows can overlap within a trading day. Treating every
    observation as independent can inflate the t-stat. The corrected standard
    error clusters residuals by NY trading date, then uses the larger of the
    iid and clustered standard errors so the reported t-stat is never more
    optimistic than the naive one.
    """
    values = [obs.reversal_pips for obs in observations]
    base = summarize(values)
    if not observations:
        return base

    clusters: dict[date, list[Decimal]] = {}
    for obs in observations:
        clusters.setdefault(obs.trading_date, []).append(obs.reversal_pips - base.mean_pips)
    cluster_count = len(clusters)
    if cluster_count < 2:
        corrected_se = Decimal("0")
    else:
        cluster_sum_sq = sum(
            (sum(residuals, Decimal("0")) ** 2 for residuals in clusters.values()),
            Decimal("0"),
        )
        variance = (
            Decimal(cluster_count)
            / Decimal(cluster_count - 1)
            * cluster_sum_sq
            / (Decimal(base.count) ** 2)
        )
        corrected_se = variance.sqrt()

    iid_se = base.standard_error_pips
    standard_error = max(iid_se, corrected_se)
    corrected_t = _t_stat_from_standard_error(base.mean_pips, standard_error)
    p_value = _one_sided_p_value(corrected_t)
    return ForwardSummary(
        count=base.count,
        mean_pips=base.mean_pips,
        median_pips=base.median_pips,
        hit_rate=base.hit_rate,
        stddev_pips=base.stddev_pips,
        t_stat=corrected_t,
        naive_t_stat=base.naive_t_stat,
        standard_error_pips=standard_error,
        effective_sample_size=cluster_count,
        p_value=p_value,
        bonferroni_p_value=p_value,
        correction="cluster_by_trading_day",
    )


@dataclass(frozen=True)
class EdgeScanRow:
    instrument: str
    horizon: int
    total_sweeps: int
    overall: ForwardSummary
    has_edge: bool
    best_conditional: ConditionalEdge | None
    statistical_notes: dict[str, Any]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "horizon": self.horizon,
            "total_sweeps": self.total_sweeps,
            "overall": self.overall.to_jsonable(),
            "has_edge": self.has_edge,
            "best_conditional": (
                self.best_conditional.to_jsonable() if self.best_conditional else None
            ),
            "statistical_notes": self.statistical_notes,
        }


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
        config=config,
    )
    overall = summarize_observations(observations)
    conditionals = _adjust_conditionals_for_family(
        [
            *_conditional("level", observations, lambda obs: obs.level_name.value),
            *_conditional("session", observations, lambda obs: _session_for(obs.level_name)),
            *_conditional("volatility", observations, _volatility_bucket(observations)),
        ]
    )
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
        by_level=tuple(edge for edge in conditionals if edge.dimension == "level"),
        by_session=tuple(edge for edge in conditionals if edge.dimension == "session"),
        by_volatility=tuple(edge for edge in conditionals if edge.dimension == "volatility"),
        statistical_notes=_statistical_notes(
            conditional_test_count=len(conditionals),
            overall_test_count=1,
        ),
    )


def run_edge_scan(
    candles: list[ClosedCandle],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    horizons: tuple[int, ...] = (15, 30, 60),
    atr_window: int = DEFAULT_ATR_WINDOW,
) -> list[EdgeScanRow]:
    """Run the edge study at multiple horizons, reusing sweep detection."""
    ordered = tuple(
        sorted((require_closed_candle(candle) for candle in candles), key=lambda c: c.ts)
    )
    sweeps = _collect_sweeps(
        ordered, instrument=instrument, config=config, instrument_rules=instrument_rules
    )
    rows: list[EdgeScanRow] = []
    for horizon in horizons:
        observations = _observations_with_forward(
            sweeps,
            candles=ordered,
            horizon=horizon,
            atr_window=atr_window,
            instrument_rules=instrument_rules,
            config=config,
        )
        overall = summarize_observations(observations)
        conditionals = _adjust_conditionals_for_family(_all_conditionals(observations))
        rows.append(
            EdgeScanRow(
                instrument=instrument,
                horizon=horizon,
                total_sweeps=len(sweeps),
                overall=overall,
                has_edge=has_edge(overall),
                best_conditional=_best_conditional(conditionals),
                statistical_notes=_statistical_notes(
                    conditional_test_count=len(conditionals),
                    overall_test_count=len(horizons),
                ),
            )
        )
    return _adjust_scan_rows_for_family(rows)


def adjust_edge_scan_rows_for_universe(rows: list[EdgeScanRow]) -> list[EdgeScanRow]:
    """Apply a final overall-test correction across all scanned instruments/horizons."""
    return _adjust_scan_rows_for_family(rows)


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
    config: StrategyConfig,
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
                trading_date=trading_date_for_candle(candles[index], config),
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
    grouped: dict[str, list[_Observation]] = {}
    for obs in observations:
        grouped.setdefault(key(obs), []).append(obs)
    edges = []
    for value in sorted(grouped):
        summary = summarize_observations(grouped[value])
        edges.append(
            ConditionalEdge(
                dimension=dimension, value=value, summary=summary, has_edge=has_edge(summary)
            )
        )
    return tuple(edges)


def _all_conditionals(observations: list[_Observation]) -> list[ConditionalEdge]:
    edges: list[ConditionalEdge] = []
    edges.extend(_conditional("level", observations, lambda obs: obs.level_name.value))
    edges.extend(_conditional("session", observations, lambda obs: _session_for(obs.level_name)))
    edges.extend(_conditional("volatility", observations, _volatility_bucket(observations)))
    return edges


def _best_conditional(edges: list[ConditionalEdge]) -> ConditionalEdge | None:
    candidates = [e for e in edges if e.has_edge]
    if not candidates:
        candidates = [e for e in edges if e.summary.count >= MIN_SAMPLES]
    if not candidates:
        return None
    return max(candidates, key=lambda e: e.summary.t_stat)


def _adjust_conditionals_for_family(edges: list[ConditionalEdge]) -> tuple[ConditionalEdge, ...]:
    test_count = len(edges)
    adjusted: list[ConditionalEdge] = []
    for edge in edges:
        summary = _with_bonferroni(edge.summary, test_count)
        adjusted.append(
            ConditionalEdge(
                dimension=edge.dimension,
                value=edge.value,
                summary=summary,
                has_edge=has_edge(summary),
                family_test_count=test_count,
            )
        )
    return tuple(adjusted)


def _adjust_scan_rows_for_family(rows: list[EdgeScanRow]) -> list[EdgeScanRow]:
    test_count = len(rows)
    adjusted: list[EdgeScanRow] = []
    for row in rows:
        overall = _with_bonferroni(row.overall, test_count)
        notes = {
            **row.statistical_notes,
            "overall_test_count": test_count,
            "overall_multiple_test_method": "bonferroni",
        }
        adjusted.append(
            EdgeScanRow(
                instrument=row.instrument,
                horizon=row.horizon,
                total_sweeps=row.total_sweeps,
                overall=overall,
                has_edge=has_edge(overall),
                best_conditional=row.best_conditional,
                statistical_notes=notes,
            )
        )
    return adjusted


def _with_bonferroni(summary: ForwardSummary, test_count: int) -> ForwardSummary:
    return ForwardSummary(
        count=summary.count,
        mean_pips=summary.mean_pips,
        median_pips=summary.median_pips,
        hit_rate=summary.hit_rate,
        stddev_pips=summary.stddev_pips,
        t_stat=summary.t_stat,
        naive_t_stat=summary.naive_t_stat,
        standard_error_pips=summary.standard_error_pips,
        effective_sample_size=summary.effective_sample_size,
        p_value=summary.p_value,
        bonferroni_p_value=_bonferroni(summary.p_value, test_count),
        correction=summary.correction,
    )


def _statistical_notes(*, conditional_test_count: int, overall_test_count: int) -> dict[str, Any]:
    return {
        "mean_null_hypothesis": "mean reversal pips <= 0",
        "tail": "one_sided_positive_reversal",
        "alpha": str(ALPHA),
        "minimum_observations": MIN_SAMPLES,
        "minimum_effective_samples": MIN_EFFECTIVE_SAMPLES,
        "t_threshold": str(T_THRESHOLD),
        "standard_error_correction": "max(iid, cluster_by_trading_day)",
        "effective_sample_unit": "NY trading day",
        "conditional_test_count": conditional_test_count,
        "conditional_multiple_test_method": "bonferroni",
        "overall_test_count": overall_test_count,
        "overall_multiple_test_method": "bonferroni",
    }


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
