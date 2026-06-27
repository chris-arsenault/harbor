from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.edge import (
    MIN_SAMPLES,
    EdgeStudyResult,
    _Observation,
    has_edge,
    run_edge_scan,
    run_edge_study,
    summarize,
    summarize_observations,
)
from harbor_bot.strategy.models import (
    Bias,
    InstrumentRules,
    LevelName,
    strategy_config_from_defaults,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


def test_summarize_reports_count_mean_and_hit_rate() -> None:
    summary = summarize([Decimal("2"), Decimal("-1"), Decimal("3")])

    assert summary.count == 3
    assert summary.mean_pips == Decimal("4") / Decimal("3")
    assert summary.hit_rate == Decimal("2") / Decimal("3")


def test_has_edge_requires_significant_positive_reversal() -> None:
    strong = summarize([Decimal("2")] * MIN_SAMPLES + [Decimal("1")] * 10)
    thin = summarize([Decimal("2")] * 5)
    coin_flip = summarize(([Decimal("1")] * 20) + ([Decimal("-1")] * 20))
    # Positive mean but huge variance: many samples, yet not significant vs chance.
    noisy = summarize(([Decimal("10")] * 16) + ([Decimal("-10")] * 15))

    assert has_edge(strong) is True
    assert has_edge(thin) is False  # too few samples
    assert has_edge(coin_flip) is False  # zero mean
    assert noisy.count >= MIN_SAMPLES
    assert noisy.mean_pips > 0
    assert noisy.t_stat < Decimal("2")
    assert has_edge(noisy) is False  # positive but not statistically significant


def test_cluster_correction_blocks_single_day_overlap_from_passing_edge_gate() -> None:
    observations = [
        _obs(index=index, trading_date="2026-01-15", value=Decimal("2"))
        for index in range(MIN_SAMPLES)
    ]

    summary = summarize_observations(observations)

    assert summary.count == MIN_SAMPLES
    assert summary.mean_pips > 0
    assert summary.naive_t_stat >= Decimal("0")
    assert summary.effective_sample_size == 1
    assert summary.correction == "cluster_by_trading_day"
    assert has_edge(summary) is False


def test_summary_reports_bonferroni_observability_fields() -> None:
    summary = summarize([Decimal("2"), Decimal("-1"), Decimal("3")])
    data = summary.to_jsonable()

    assert data["naive_t_stat"] == data["t_stat"]
    assert data["effective_sample_size"] == 3
    assert data["p_value"] == data["bonferroni_p_value"]
    assert data["correction"] == "iid"


def test_clean_signal_day_records_one_sweep_with_positive_reversal() -> None:
    result = _run("clean_signal_day.json", horizon=3)

    assert isinstance(result, EdgeStudyResult)
    assert result.total_sweeps == 2
    assert result.overall.count == 1  # only one sweep has a full forward window in the fixture
    assert result.overall.mean_pips > 0
    assert result.overall.hit_rate == Decimal("1")
    assert result.has_edge is False  # one observation is far under MIN_SAMPLES
    assert result.overall.correction == "cluster_by_trading_day"
    assert result.statistical_notes["conditional_multiple_test_method"] == "bonferroni"
    assert any(edge.value == "asia_low" for edge in result.by_level)


def test_no_trade_day_records_no_sweeps() -> None:
    result = _run("no_trade_day.json", horizon=3)

    assert result.total_sweeps == 0
    assert result.overall.count == 0
    assert result.has_edge is False


def test_edge_scan_runs_multiple_hypothesis_algorithms() -> None:
    rows = run_edge_scan(
        list(load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")),
        instrument="EUR_USD",
        config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        horizons=(3,),
        algorithm_ids=("generic_sweep_reversal", "clean_level_sweep_reversal"),
    )

    assert {row.algorithm_id for row in rows} == {
        "generic_sweep_reversal",
        "clean_level_sweep_reversal",
    }
    assert {row.hypothesis_id for row in rows} == {"H001", "H005"}
    assert all(row.horizon == 3 for row in rows)


def test_non_news_proxy_algorithm_excludes_1000_et_sweep() -> None:
    rows = _scan_algorithm_fixture(
        _algorithm_fixture_candles(
            [
                _sweep_spec(day=0, local_hour=9, local_minute=59),
                _sweep_spec(day=1, local_hour=10, local_minute=20),
            ]
        ),
        algorithms=("generic_sweep_reversal", "non_news_proxy_sweep_reversal"),
    )

    assert _sweeps(rows, "generic_sweep_reversal") == 2
    assert _sweeps(rows, "non_news_proxy_sweep_reversal") == 1


def test_early_ny_algorithm_keeps_opening_window_sweep_only() -> None:
    rows = _scan_algorithm_fixture(
        _algorithm_fixture_candles(
            [
                _sweep_spec(day=0, local_hour=9, local_minute=45),
                _sweep_spec(day=1, local_hour=10, local_minute=45),
            ]
        ),
        algorithms=("generic_sweep_reversal", "early_ny_sweep_reversal"),
    )

    assert _sweeps(rows, "generic_sweep_reversal") == 2
    assert _sweeps(rows, "early_ny_sweep_reversal") == 1


def test_clean_level_algorithm_excludes_pre_tapped_level() -> None:
    rows = _scan_algorithm_fixture(
        _algorithm_fixture_candles(
            [
                _sweep_spec(day=0, pre_tap=True),
                _sweep_spec(day=1, pre_tap=False),
            ]
        ),
        algorithms=("generic_sweep_reversal", "clean_level_sweep_reversal"),
    )

    assert _sweeps(rows, "generic_sweep_reversal") == 2
    assert _sweeps(rows, "clean_level_sweep_reversal") == 1


def test_compressed_range_algorithm_keeps_below_median_session_ranges() -> None:
    rows = _scan_algorithm_fixture(
        _algorithm_fixture_candles(
            [
                _sweep_spec(day=0, asia_high="1.1000", london_high="1.1050"),
                _sweep_spec(day=1, asia_high="1.1300", london_high="1.1350"),
            ]
        ),
        algorithms=("generic_sweep_reversal", "compressed_range_sweep_reversal"),
    )

    assert _sweeps(rows, "generic_sweep_reversal") == 2
    assert _sweeps(rows, "compressed_range_sweep_reversal") == 1


def test_mss_confirmed_algorithm_uses_confirmed_structure_break_event() -> None:
    rows = _scan_algorithm_fixture(
        _algorithm_fixture_candles(
            [
                _sweep_spec(day=0, mss_break=True),
                _sweep_spec(day=1, mss_break=False),
            ]
        ),
        algorithms=("generic_sweep_reversal", "mss_confirmed_sweep_reversal"),
    )

    assert _sweeps(rows, "generic_sweep_reversal") == 2
    assert _sweeps(rows, "mss_confirmed_sweep_reversal") == 1


def _run(name: str, *, horizon: int) -> EdgeStudyResult:
    return run_edge_study(
        load_candle_fixture(FIXTURE_DIR / name),
        instrument="EUR_USD",
        config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        horizon=horizon,
    )


def _scan_algorithm_fixture(candles, *, algorithms: tuple[str, ...]):
    return run_edge_scan(
        candles,
        instrument="EUR_USD",
        config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        horizons=(1,),
        algorithm_ids=algorithms,
    )


def _sweeps(rows, algorithm_id: str) -> int:
    return next(row.total_sweeps for row in rows if row.algorithm_id == algorithm_id)


def _sweep_spec(
    *,
    day: int,
    local_hour: int = 9,
    local_minute: int = 45,
    pre_tap: bool = False,
    asia_high: str = "1.1000",
    london_high: str = "1.1050",
    mss_break: bool = False,
) -> dict[str, object]:
    return {
        "day": day,
        "local_hour": local_hour,
        "local_minute": local_minute,
        "pre_tap": pre_tap,
        "asia_high": asia_high,
        "london_high": london_high,
        "mss_break": mss_break,
    }


def _algorithm_fixture_candles(specs: list[dict[str, object]]) -> list:
    candles = []
    for spec in specs:
        candles.extend(_day_candles(**spec))
    return candles


def _day_candles(
    *,
    day: int,
    local_hour: int,
    local_minute: int,
    pre_tap: bool,
    asia_high: str,
    london_high: str,
    mss_break: bool,
) -> list:
    base = date(2026, 1, 15) + timedelta(days=day)
    # london_low sits far below asia_low so the only sweepable level is asia_low.
    candles = [
        _candle(_utc(base, 20, 0, previous=True), high=asia_high, low="1.0800", close="1.0900"),
        _candle(_utc(base, 23, 59, previous=True), high=asia_high, low="1.0800", close="1.0900"),
        _candle(_utc(base, 2, 0), high=london_high, low="1.0700", close="1.0850"),
        _candle(_utc(base, 4, 59), high=london_high, low="1.0700", close="1.0850"),
        _candle(_utc(base, 9, 29), high="1.0920", low="1.0860", close="1.0900"),
        _candle(_utc(base, 9, 30), high="1.0915", low="1.0865", close="1.0890"),
    ]
    if pre_tap:
        # Touches asia_low (1.0800) without sweeping it (low is not below the buffer).
        candles.append(
            _candle(_utc(base, 9, 40), high="1.0820", low="1.0800", close="1.0810"),
        )
    if mss_break:
        # Build a confirmed swing-high pivot at 09:36 before the sweep.
        candles.extend(
            [
                _candle(_utc(base, 9, 35), high="1.0900", low="1.0830", close="1.0880"),
                _candle(_utc(base, 9, 36), high="1.0950", low="1.0830", close="1.0900"),
                _candle(_utc(base, 9, 37), high="1.0900", low="1.0830", close="1.0880"),
                _candle(_utc(base, 9, 38), high="1.0895", low="1.0830", close="1.0880"),
            ]
        )
    sweep_dt = _utc(base, local_hour, local_minute)
    candles.append(_candle(sweep_dt, high="1.0885", low="1.0790", close="1.0810"))
    if mss_break:
        # Post-sweep close breaks above the prior swing high → MSS confirmed.
        candles.append(
            _candle(sweep_dt + timedelta(minutes=1), high="1.0970", low="1.0830", close="1.0960"),
        )
    candles.append(
        _candle(sweep_dt + timedelta(minutes=2), high="1.0905", low="1.0830", close="1.0900"),
    )
    candles.append(
        _candle(sweep_dt + timedelta(minutes=3), high="1.0905", low="1.0830", close="1.0900"),
    )
    return sorted(candles, key=lambda candle: candle.ts)


_NY = ZoneInfo("America/New_York")


def _utc(value_date: date, hour: int, minute: int, *, previous: bool = False) -> datetime:
    local_date = value_date - timedelta(days=1) if previous else value_date
    local = datetime.combine(local_date, time(hour=hour, minute=minute), tzinfo=_NY)
    return local.astimezone(UTC)


def _candle(ts: datetime, *, high: str, low: str, close: str):
    return ClosedCandle(
        instrument="EUR_USD",
        ts=ts,
        o=Decimal(close),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=100,
    )


def _obs(*, index: int, trading_date: str, value: Decimal) -> _Observation:
    return _Observation(
        index=index,
        trading_date=date.fromisoformat(trading_date),
        level_name=LevelName.ASIA_LOW,
        bias=Bias.BULLISH,
        reversal_pips=value,
        atr_pips=Decimal("1"),
    )


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
