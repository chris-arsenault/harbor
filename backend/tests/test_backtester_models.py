from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from harbor_bot.backtester.models import (
    BacktestConfig,
    BacktestInput,
    BacktestRunResult,
    BacktestStats,
    BacktestStatus,
    BacktestTrade,
    EquityPoint,
    FillPolicy,
    candle_to_record,
    entry_setup_from_decision,
)
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    StrategyDecision,
    strategy_config_from_defaults,
)


def test_backtest_config_defaults_are_conservative_and_jsonable() -> None:
    config = BacktestConfig()

    assert config.initial_nav == Decimal("10000")
    assert config.spread_pips == Decimal("0.8")
    assert config.slippage_pips == Decimal("0.1")
    assert config.commission_per_unit == Decimal("0")
    assert config.ambiguous_fill_policy == FillPolicy.PESSIMISTIC
    assert config.force_ny_close is True
    assert config.to_jsonable() == {
        "initial_nav": "10000",
        "spread_pips": "0.8",
        "slippage_pips": "0.1",
        "commission_per_unit": "0",
        "ambiguous_fill_policy": "pessimistic",
        "force_ny_close": True,
    }


def test_backtest_config_rejects_invalid_runtime_assumptions() -> None:
    with pytest.raises(ValueError, match="initial_nav"):
        BacktestConfig(initial_nav=Decimal("0"))
    with pytest.raises(ValueError, match="spread_pips"):
        BacktestConfig(spread_pips=Decimal("-0.1"))
    with pytest.raises(ValueError, match="slippage_pips"):
        BacktestConfig(slippage_pips=Decimal("-0.1"))
    with pytest.raises(ValueError, match="commission_per_unit"):
        BacktestConfig(commission_per_unit=Decimal("-0.1"))


def test_backtest_input_is_immutable_and_matches_instrument_boundaries() -> None:
    candle = _candle()
    backtest_input = BacktestInput(
        instrument="EUR_USD",
        candles=[candle],
        strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_instrument_rules(),
    )

    assert backtest_input.candles == (candle,)
    with pytest.raises(FrozenInstanceError):
        backtest_input.instrument = "GBP_USD"
    with pytest.raises(ValueError, match="instrument"):
        BacktestInput(
            instrument="GBP_USD",
            candles=[candle],
            strategy_config=strategy_config_from_defaults(load_default_config()),
            instrument_rules=_instrument_rules(),
        )


def test_strategy_market_entry_decision_converts_to_entry_setup() -> None:
    setup = _entry_setup()
    decision = StrategyDecision(kind="market_entry", ts=setup.ts, payload={"setup": setup})

    assert entry_setup_from_decision(decision) == setup

    with pytest.raises(ValueError, match="market entry"):
        entry_setup_from_decision(StrategyDecision(kind="sweep", ts=setup.ts))
    with pytest.raises(TypeError, match="MarketEntrySetup"):
        entry_setup_from_decision(
            StrategyDecision(kind="market_entry", ts=setup.ts, payload={"setup": object()})
        )


def test_backtest_trade_converts_from_entry_setup_and_to_persistence_row() -> None:
    setup = _entry_setup()
    trade = BacktestTrade.from_entry_setup(
        setup,
        entry_price=Decimal("1.1010"),
        entry_ts=datetime(2026, 1, 15, 14, 36, tzinfo=UTC),
        exit_price=Decimal("1.1070"),
        exit_ts=datetime(2026, 1, 15, 14, 42, tzinfo=UTC),
        pnl=Decimal("60"),
        r_multiple=Decimal("2"),
        exit_reason="target",
    )

    assert trade.instrument == "EUR_USD"
    assert trade.side == "long"
    assert trade.level_name == "asia_low"
    assert trade.source_signal_ts == setup.ts
    assert trade.to_persistence_row() == {
        "side": "long",
        "units": Decimal("10000"),
        "entry_price": Decimal("1.1010"),
        "entry_ts": datetime(2026, 1, 15, 14, 36, tzinfo=UTC),
        "exit_price": Decimal("1.1070"),
        "exit_ts": datetime(2026, 1, 15, 14, 42, tzinfo=UTC),
        "pnl": Decimal("60"),
        "r_multiple": Decimal("2"),
        "exit_reason": "target",
    }


def test_backtest_stats_equity_and_result_are_immutable_and_jsonable() -> None:
    stats = BacktestStats.empty(initial_nav=Decimal("10000"))
    point = EquityPoint(
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        nav=Decimal("10000"),
    )
    result = BacktestRunResult(
        status=BacktestStatus.COMPLETED,
        stats=stats,
        equity_curve=[point],
        params_json={"instrument": "EUR_USD"},
    )

    assert stats.to_jsonable()["ending_nav"] == "10000"
    assert point.to_jsonable()["nav"] == "10000"
    assert result.equity_curve == (point,)
    assert result.status == BacktestStatus.COMPLETED
    with pytest.raises(FrozenInstanceError):
        result.status = BacktestStatus.FAILED


def test_closed_candle_converts_to_jsonable_record() -> None:
    assert candle_to_record(_candle()) == {
        "instrument": "EUR_USD",
        "ts": "2026-01-15T14:30:00+00:00",
        "o": "1.1000",
        "h": "1.1010",
        "low": "1.0990",
        "c": "1.1005",
        "volume": 100,
        "complete": True,
    }


def _candle() -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        o=Decimal("1.1000"),
        h=Decimal("1.1010"),
        low=Decimal("1.0990"),
        c=Decimal("1.1005"),
        volume=100,
    )


def _entry_setup() -> MarketEntrySetup:
    return MarketEntrySetup(
        ts=datetime(2026, 1, 15, 14, 35, tzinfo=UTC),
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.1000"),
        stop=Decimal("1.0980"),
        target=Decimal("1.1060"),
        risk=Decimal("0.0020"),
        units=Decimal("10000"),
    )


def _instrument_rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
