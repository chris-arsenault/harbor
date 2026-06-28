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

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, time, timedelta
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
BASELINE_ALGORITHM_ID = "generic_sweep_reversal"


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
    algorithm_id: str
    hypothesis_id: str
    algorithm_label: str
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
            "algorithm_id": self.algorithm_id,
            "hypothesis_id": self.hypothesis_id,
            "algorithm_label": self.algorithm_label,
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


@dataclass(frozen=True)
class EdgeEvent:
    index: int
    trading_date: date
    level_name: LevelName
    bias: Bias
    atr_pips: Decimal
    pip_size: Decimal


@dataclass(frozen=True)
class EdgeAlgorithm:
    algorithm_id: str
    hypothesis_id: str
    label: str
    description: str
    event_builder: Callable[..., list[EdgeEvent]]

    def to_jsonable(self) -> dict[str, str]:
        return {
            "algorithm_id": self.algorithm_id,
            "hypothesis_id": self.hypothesis_id,
            "label": self.label,
            "description": self.description,
        }


@dataclass(frozen=True)
class _SweepCandidate:
    index: int
    trading_date: date
    day_index: int
    day_start_index: int
    day_candles: tuple[ClosedCandle, ...]
    session_levels: Any
    sweep: Any


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
    algorithm_id: str
    hypothesis_id: str
    algorithm_label: str
    instrument: str
    horizon: int
    total_sweeps: int
    overall: ForwardSummary
    has_edge: bool
    best_conditional: ConditionalEdge | None
    statistical_notes: dict[str, Any]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "hypothesis_id": self.hypothesis_id,
            "algorithm_label": self.algorithm_label,
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
    algorithm_id: str = BASELINE_ALGORITHM_ID,
) -> EdgeStudyResult:
    _validate_horizons((horizon,))
    algorithm = get_edge_algorithm(algorithm_id)
    ordered = tuple(
        sorted((require_closed_candle(candle) for candle in candles), key=lambda c: c.ts)
    )
    events = algorithm.event_builder(
        ordered,
        instrument=instrument,
        config=config,
        instrument_rules=instrument_rules,
        atr_window=atr_window,
    )
    observations = _observations_with_forward(
        events,
        candles=ordered,
        horizon=horizon,
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
        algorithm_id=algorithm.algorithm_id,
        hypothesis_id=algorithm.hypothesis_id,
        algorithm_label=algorithm.label,
        instrument=instrument,
        horizon=horizon,
        total_candles=len(ordered),
        total_sweeps=len(events),
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
    algorithm_ids: tuple[str, ...] = (BASELINE_ALGORITHM_ID,),
) -> list[EdgeScanRow]:
    """Run the edge study at multiple horizons and hypothesis algorithms."""
    _validate_horizons(horizons)
    ordered = tuple(
        sorted((require_closed_candle(candle) for candle in candles), key=lambda c: c.ts)
    )
    rows: list[EdgeScanRow] = []
    for algorithm_id in algorithm_ids:
        algorithm = get_edge_algorithm(algorithm_id)
        events = algorithm.event_builder(
            ordered,
            instrument=instrument,
            config=config,
            instrument_rules=instrument_rules,
            atr_window=atr_window,
        )
        for horizon in horizons:
            observations = _observations_with_forward(
                events,
                candles=ordered,
                horizon=horizon,
            )
            overall = summarize_observations(observations)
            conditionals = _adjust_conditionals_for_family(_all_conditionals(observations))
            rows.append(
                EdgeScanRow(
                    algorithm_id=algorithm.algorithm_id,
                    hypothesis_id=algorithm.hypothesis_id,
                    algorithm_label=algorithm.label,
                    instrument=instrument,
                    horizon=horizon,
                    total_sweeps=len(events),
                    overall=overall,
                    has_edge=has_edge(overall),
                    best_conditional=_best_conditional(conditionals),
                    statistical_notes=_statistical_notes(
                        conditional_test_count=len(conditionals),
                        overall_test_count=len(horizons) * len(algorithm_ids),
                    ),
                )
            )
    return _adjust_scan_rows_for_family(rows)


def adjust_edge_scan_rows_for_universe(rows: list[EdgeScanRow]) -> list[EdgeScanRow]:
    """Apply a final overall-test correction across all scanned instruments/horizons."""
    return _adjust_scan_rows_for_family(rows)


def available_edge_algorithms() -> tuple[EdgeAlgorithm, ...]:
    return (
        EdgeAlgorithm(
            algorithm_id=BASELINE_ALGORITHM_ID,
            hypothesis_id="H001",
            label="Generic session sweep reversal",
            description="Any first Asia/London session-level sweep inside the NY window.",
            event_builder=_generic_sweep_events,
        ),
        EdgeAlgorithm(
            algorithm_id="non_news_proxy_sweep_reversal",
            hypothesis_id="H002",
            label="Non-news-proxy sweep reversal",
            description=(
                "Session sweeps excluding the 10:00 ET macro-release proxy window "
                "where genuine repricing is more likely than stop-run reversion."
            ),
            event_builder=_non_news_proxy_events,
        ),
        EdgeAlgorithm(
            algorithm_id="mss_confirmed_sweep_reversal",
            hypothesis_id="H003",
            label="MSS-confirmed sweep reversal",
            description=(
                "A sweep only becomes an event after a closed-candle market-structure "
                "shift in the reversal direction."
            ),
            event_builder=_mss_confirmed_events,
        ),
        EdgeAlgorithm(
            algorithm_id="compressed_range_sweep_reversal",
            hypothesis_id="H004",
            label="Compressed-range sweep reversal",
            description=(
                "Sweeps after below-median Asia/London range compression should reverse "
                "more cleanly than sweeps after expanded ranges."
            ),
            event_builder=_compressed_range_events,
        ),
        EdgeAlgorithm(
            algorithm_id="clean_level_sweep_reversal",
            hypothesis_id="H005",
            label="Clean-level first-touch sweep",
            description=(
                "Sweeps of levels not already tapped in the NY window are cleaner "
                "liquidity events than repeatedly traded levels."
            ),
            event_builder=_clean_level_events,
        ),
        EdgeAlgorithm(
            algorithm_id="early_ny_sweep_reversal",
            hypothesis_id="H006",
            label="Early-NY sweep reversal",
            description=(
                "Sweeps during the opening NY liquidity auction should behave "
                "differently from late-window sweeps."
            ),
            event_builder=_early_ny_events,
        ),
        EdgeAlgorithm(
            algorithm_id="generic_sweep_continuation",
            hypothesis_id="H007",
            label="Generic session sweep continuation",
            description=(
                "Any first Asia/London session-level sweep, scored in the continuation "
                "direction instead of the reversal direction."
            ),
            event_builder=_generic_sweep_continuation_events,
        ),
        EdgeAlgorithm(
            algorithm_id="mss_confirmed_sweep_continuation",
            hypothesis_id="H007",
            label="MSS-confirmed sweep continuation",
            description=("MSS-confirmed sweep events scored as continuation rather than reversal."),
            event_builder=_mss_confirmed_continuation_events,
        ),
        EdgeAlgorithm(
            algorithm_id="early_ny_sweep_continuation",
            hypothesis_id="H007",
            label="Early-NY sweep continuation",
            description=("Early-NY sweep events scored as continuation rather than reversal."),
            event_builder=_early_ny_continuation_events,
        ),
    )


def default_edge_algorithm_ids() -> tuple[str, ...]:
    return tuple(algorithm.algorithm_id for algorithm in available_edge_algorithms())


def get_edge_algorithm(algorithm_id: str) -> EdgeAlgorithm:
    algorithms = {algorithm.algorithm_id: algorithm for algorithm in available_edge_algorithms()}
    try:
        return algorithms[algorithm_id]
    except KeyError as exc:
        msg = f"unknown edge algorithm {algorithm_id!r}"
        raise ValueError(msg) from exc


def _collect_sweep_candidates(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> list[_SweepCandidate]:
    candidates: list[_SweepCandidate] = []
    for trading_date, day_start_index, day_candles in _day_groups(candles, config):
        candidates.extend(
            _collect_sweep_candidates_for_day(
                day_candles,
                trading_date=trading_date,
                day_start_index=day_start_index,
                instrument=instrument,
                config=config,
                instrument_rules=instrument_rules,
            )
        )
    return candidates


def _day_groups(
    candles: tuple[ClosedCandle, ...],
    config: StrategyConfig,
) -> list[tuple[date, int, tuple[ClosedCandle, ...]]]:
    groups: list[tuple[date, int, tuple[ClosedCandle, ...]]] = []
    trading_date: date | None = None
    start_index = 0
    current: list[ClosedCandle] = []
    for index, candle in enumerate(candles):
        next_date = trading_date_for_candle(candle, config)
        if trading_date is not None and next_date != trading_date:
            groups.append((trading_date, start_index, tuple(current)))
            current = []
            start_index = index
        trading_date = next_date
        current.append(candle)
    if trading_date is not None:
        groups.append((trading_date, start_index, tuple(current)))
    return groups


def _collect_sweep_candidates_for_day(
    day_candles: tuple[ClosedCandle, ...],
    *,
    trading_date: date,
    day_start_index: int,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> list[_SweepCandidate]:
    candidates: list[_SweepCandidate] = []
    day_state: DayState | None = None
    session_levels = None
    day_history: list[ClosedCandle] = []
    day_state = DayState(trading_date=trading_date)
    for day_index, candle in enumerate(day_candles):
        day_history.append(candle)
        if session_levels is None and candle.ts.astimezone(UTC) >= _ny_start(trading_date, config):
            session_levels = _try_levels(
                day_history, trading_date=trading_date, instrument=instrument, config=config
            )
        if session_levels is None or not is_in_ny_trade_window(
            candle, trading_date=trading_date, config=config
        ):
            continue
        sweep = detect_sweep(
            candle,
            levels=session_levels,
            config=config,
            instrument_rules=instrument_rules,
            day_state=day_state,
            candle_index=day_index,
        )
        if sweep is not None:
            candidates.append(
                _SweepCandidate(
                    index=day_start_index + day_index,
                    trading_date=trading_date,
                    day_index=day_index,
                    day_start_index=day_start_index,
                    day_candles=day_candles,
                    session_levels=session_levels,
                    sweep=sweep,
                )
            )
            day_state = mark_level_taken(day_state, sweep.level_name)
    return candidates


def _generic_sweep_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    return _events_from_candidates(
        _collect_sweep_candidates(
            candles, instrument=instrument, config=config, instrument_rules=instrument_rules
        ),
        candles=candles,
        atr_window=atr_window,
        instrument_rules=instrument_rules,
    )


def _non_news_proxy_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    candidates = [
        candidate
        for candidate in _collect_sweep_candidates(
            candles, instrument=instrument, config=config, instrument_rules=instrument_rules
        )
        if not _in_time_window(
            candles[candidate.index],
            config,
            start=time(9, 55),
            end=time(10, 10),
        )
    ]
    return _events_from_candidates(
        candidates, candles=candles, atr_window=atr_window, instrument_rules=instrument_rules
    )


def _mss_confirmed_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    from harbor_bot.strategy.structure import mss_confirmed

    events: list[EdgeEvent] = []
    candidates = _collect_sweep_candidates(
        candles, instrument=instrument, config=config, instrument_rules=instrument_rules
    )
    for candidate in candidates:
        deadline = min(candidate.day_index + config.fvg_window, len(candidate.day_candles) - 1)
        for current_day_index in range(candidate.day_index + 1, deadline + 1):
            current = candidate.day_candles[current_day_index]
            if not is_in_ny_trade_window(
                current, trading_date=candidate.trading_date, config=config
            ):
                continue
            if mss_confirmed(
                list(candidate.day_candles[: current_day_index + 1]),
                sweep=candidate.sweep,
                current_index=current_day_index,
                config=config,
            ):
                events.append(
                    _event_from_candidate(
                        candidate,
                        index=candidate.day_start_index + current_day_index,
                        candles=candles,
                        atr_window=atr_window,
                        instrument_rules=instrument_rules,
                    )
                )
                break
    return events


def _compressed_range_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    candidates = _collect_sweep_candidates(
        candles, instrument=instrument, config=config, instrument_rules=instrument_rules
    )
    filtered = []
    ranges_so_far: list[Decimal] = []
    for candidate in candidates:
        range_pips = _session_range_pips(candidate, instrument_rules)
        ranges_so_far.append(range_pips)
        if range_pips <= _median(ranges_so_far):
            filtered.append(candidate)
    return _events_from_candidates(
        filtered, candles=candles, atr_window=atr_window, instrument_rules=instrument_rules
    )


def _clean_level_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    candidates = [
        candidate
        for candidate in _collect_sweep_candidates(
            candles, instrument=instrument, config=config, instrument_rules=instrument_rules
        )
        if _level_clean_before_sweep(candidate, config=config, instrument_rules=instrument_rules)
    ]
    return _events_from_candidates(
        candidates, candles=candles, atr_window=atr_window, instrument_rules=instrument_rules
    )


def _early_ny_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    candidates = [
        candidate
        for candidate in _collect_sweep_candidates(
            candles, instrument=instrument, config=config, instrument_rules=instrument_rules
        )
        if _in_time_window(candles[candidate.index], config, start=time(9, 30), end=time(10, 15))
    ]
    return _events_from_candidates(
        candidates, candles=candles, atr_window=atr_window, instrument_rules=instrument_rules
    )


def _generic_sweep_continuation_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    return _continuation_events(
        _generic_sweep_events(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=instrument_rules,
            atr_window=atr_window,
        )
    )


def _mss_confirmed_continuation_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    return _continuation_events(
        _mss_confirmed_events(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=instrument_rules,
            atr_window=atr_window,
        )
    )


def _early_ny_continuation_events(
    candles: tuple[ClosedCandle, ...],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    atr_window: int,
) -> list[EdgeEvent]:
    return _continuation_events(
        _early_ny_events(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=instrument_rules,
            atr_window=atr_window,
        )
    )


def _continuation_events(events: list[EdgeEvent]) -> list[EdgeEvent]:
    return [
        EdgeEvent(
            index=event.index,
            trading_date=event.trading_date,
            level_name=event.level_name,
            bias=_opposite_bias(event.bias),
            atr_pips=event.atr_pips,
            pip_size=event.pip_size,
        )
        for event in events
    ]


def _opposite_bias(bias: Bias) -> Bias:
    return Bias.BEARISH if bias == Bias.BULLISH else Bias.BULLISH


def _events_from_candidates(
    candidates: list[_SweepCandidate],
    *,
    candles: tuple[ClosedCandle, ...],
    atr_window: int,
    instrument_rules: InstrumentRules,
) -> list[EdgeEvent]:
    return [
        _event_from_candidate(
            candidate,
            index=candidate.index,
            candles=candles,
            atr_window=atr_window,
            instrument_rules=instrument_rules,
        )
        for candidate in candidates
    ]


def _event_from_candidate(
    candidate: _SweepCandidate,
    *,
    index: int,
    candles: tuple[ClosedCandle, ...],
    atr_window: int,
    instrument_rules: InstrumentRules,
) -> EdgeEvent:
    return EdgeEvent(
        index=index,
        trading_date=candidate.trading_date,
        level_name=candidate.sweep.level_name,
        bias=candidate.sweep.bias,
        atr_pips=_atr_pips(candles, index, atr_window, instrument_rules),
        pip_size=instrument_rules.pip_size,
    )


def _in_time_window(
    candle: ClosedCandle,
    config: StrategyConfig,
    *,
    start: time,
    end: time,
) -> bool:
    local_time = candle.ts.astimezone(_zone(config)).time().replace(tzinfo=None)
    return start <= local_time < end


def _zone(config: StrategyConfig) -> Any:
    from zoneinfo import ZoneInfo

    return ZoneInfo(config.timezone)


def _session_range_pips(
    candidate: _SweepCandidate,
    instrument_rules: InstrumentRules,
) -> Decimal:
    levels = candidate.session_levels
    high = max(levels.asia_high, levels.london_high)
    low = min(levels.asia_low, levels.london_low)
    return (high - low) / instrument_rules.pip_size


def _level_clean_before_sweep(
    candidate: _SweepCandidate,
    *,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> bool:
    level_price = candidate.sweep.level_price
    buffer = instrument_rules.pips_to_price(config.sweep_buffer_pips)
    prior = list(candidate.day_candles[: candidate.day_index])
    for candle in prior:
        if not is_in_ny_trade_window(candle, trading_date=candidate.trading_date, config=config):
            continue
        if candle.low - buffer <= level_price <= candle.h + buffer:
            return False
    return True


def _observations_with_forward(
    events: list[EdgeEvent],
    *,
    candles: tuple[ClosedCandle, ...],
    horizon: int,
) -> list[_Observation]:
    observations: list[_Observation] = []
    by_ts = {candle.ts: index for index, candle in enumerate(candles)}
    for event in events:
        forward_index = by_ts.get(candles[event.index].ts + timedelta(minutes=horizon))
        if forward_index is None:
            continue
        signed = candles[forward_index].c - candles[event.index].c
        reversal = signed if event.bias == Bias.BULLISH else -signed
        observations.append(
            _Observation(
                index=event.index,
                trading_date=event.trading_date,
                level_name=event.level_name,
                bias=event.bias,
                reversal_pips=reversal / event.pip_size,
                atr_pips=event.atr_pips,
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
                algorithm_id=row.algorithm_id,
                hypothesis_id=row.hypothesis_id,
                algorithm_label=row.algorithm_label,
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
    _validate_horizons((horizon,))
    pip = instrument_rules.pip_size
    by_ts = {candle.ts: candle for candle in candles}
    moves = [
        abs(forward.c - candle.c) / pip
        for candle in candles
        if (forward := by_ts.get(candle.ts + timedelta(minutes=horizon))) is not None
    ]
    return summarize(moves).mean_pips


def _validate_horizons(horizons: tuple[int, ...]) -> None:
    if not horizons or any(horizon <= 0 for horizon in horizons):
        msg = "horizons must be positive"
        raise ValueError(msg)


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
