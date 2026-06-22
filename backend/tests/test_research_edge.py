from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.config.defaults import load_default_config
from harbor_bot.research.edge import (
    MIN_SAMPLES,
    EdgeStudyResult,
    has_edge,
    run_edge_study,
    summarize,
)
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults

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


def test_clean_signal_day_records_one_sweep_with_positive_reversal() -> None:
    result = _run("clean_signal_day.json", horizon=3)

    assert isinstance(result, EdgeStudyResult)
    assert result.total_sweeps == 2
    assert result.overall.count == 1  # only one sweep has a full forward window in the fixture
    assert result.overall.mean_pips > 0
    assert result.overall.hit_rate == Decimal("1")
    assert result.has_edge is False  # one observation is far under MIN_SAMPLES
    assert any(edge.value == "asia_low" for edge in result.by_level)


def test_no_trade_day_records_no_sweeps() -> None:
    result = _run("no_trade_day.json", horizon=3)

    assert result.total_sweeps == 0
    assert result.overall.count == 0
    assert result.has_edge is False


def _run(name: str, *, horizon: int) -> EdgeStudyResult:
    return run_edge_study(
        load_candle_fixture(FIXTURE_DIR / name),
        instrument="EUR_USD",
        config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        horizon=horizon,
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
