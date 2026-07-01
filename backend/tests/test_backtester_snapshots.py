from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestInput
from harbor_bot.backtester.stats import result_snapshot
from harbor_bot.config.defaults import load_default_config
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


def test_clean_signal_day_snapshot_pins_trade_list_and_stats_json() -> None:
    snapshot = result_snapshot(_run_fixture("clean_signal_day.json"))

    assert snapshot == {
        "stats": {
            "trade_count": 1,
            "win_rate": "1",
            "net_pnl": "96.150000",
            "expectancy": "96.150000",
            "average_r": "1.785714285714285714285714286",
            "max_drawdown": "0",
            "ending_nav": "10096.150000",
            "lookahead_sanity_passed": True,
        },
        "trades": [
            {
                "instrument": "EUR_USD",
                "side": "long",
                "units": "15384",
                "entry_price": "1.09105",
                "entry_ts": "2026-01-15T14:34:00+00:00",
                "stop": "1.08755",
                "target": "1.097300",
                "exit_price": "1.097300",
                "exit_ts": "2026-01-15T14:40:00+00:00",
                "pnl": "96.150000",
                "r_multiple": "1.785714285714285714285714286",
                "exit_reason": "take_profit",
                "source_signal_ts": "2026-01-15T14:33:00+00:00",
                "level_name": "asia_low",
            }
        ],
    }


def test_no_trade_day_snapshot_pins_empty_trade_list_and_stats_json() -> None:
    snapshot = result_snapshot(_run_fixture("no_trade_day.json"))

    assert snapshot == {
        "stats": {
            "trade_count": 0,
            "win_rate": "0",
            "net_pnl": "0",
            "expectancy": "0",
            "average_r": "0",
            "max_drawdown": "0",
            "ending_nav": "10000",
            "lookahead_sanity_passed": True,
        },
        "trades": [],
    }


def _run_fixture(name: str):
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
