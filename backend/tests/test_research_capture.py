from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.config.defaults import load_default_config
from harbor_bot.research.capture import run_capture_scan
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


def test_capture_scan_reports_cost_aware_fixed_horizon_rows() -> None:
    rows = run_capture_scan(
        list(load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")),
        instrument="EUR_USD",
        config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        algorithm_ids=("generic_sweep_continuation",),
        horizons=(3,),
        spread_pips=Decimal("0.8"),
        slippage_pips=Decimal("0.1"),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.algorithm_id == "generic_sweep_continuation"
    assert row.hypothesis_id == "H007"
    assert row.horizon == 3
    assert row.event_count == 2
    assert row.stats.count == 1
    assert row.stats.average_mfe_pips >= 0
    assert row.stats.average_mae_pips >= 0


def test_capture_costs_reduce_net_pips_against_zero_cost_capture() -> None:
    candles = list(load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json"))
    kwargs = {
        "instrument": "EUR_USD",
        "config": strategy_config_from_defaults(load_default_config()),
        "instrument_rules": _rules(),
        "algorithm_ids": ("generic_sweep_continuation",),
        "horizons": (3,),
    }

    zero_cost = run_capture_scan(
        candles, **kwargs, spread_pips=Decimal("0"), slippage_pips=Decimal("0")
    )[0]
    with_cost = run_capture_scan(
        candles, **kwargs, spread_pips=Decimal("0.8"), slippage_pips=Decimal("0.1")
    )[0]

    assert with_cost.stats.mean_net_pips == zero_cost.stats.mean_net_pips - Decimal("1.0")


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
