import json
from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestInput, BacktestRunResult
from harbor_bot.config.defaults import load_default_config
from harbor_bot.research.baseline import baseline_from_results, expectancy_delta
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"
BASELINE_PATH = Path(__file__).resolve().parents[1] / "baselines" / "midpoint_fixtures.json"
FIXTURES = {
    "clean_signal_day": "clean_signal_day.json",
    "no_trade_day": "no_trade_day.json",
}


def test_committed_midpoint_baseline_matches_current_backtest() -> None:
    current = baseline_from_results(
        {name: _run_fixture(file_name) for name, file_name in FIXTURES.items()}
    )
    recorded = json.loads(BASELINE_PATH.read_text())

    assert current == recorded


def test_expectancy_delta_against_self_is_zero() -> None:
    recorded = json.loads(BASELINE_PATH.read_text())

    delta = expectancy_delta(recorded, recorded)

    assert delta["clean_signal_day"]["before"] == "95.996160"
    assert Decimal(delta["clean_signal_day"]["delta"]) == Decimal("0")


def _run_fixture(name: str) -> BacktestRunResult:
    return run_backtest(
        BacktestInput(
            instrument="EUR_USD",
            candles=load_candle_fixture(FIXTURE_DIR / name),
            strategy_config=strategy_config_from_defaults(load_default_config()),
            instrument_rules=_rules(),
        )
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
