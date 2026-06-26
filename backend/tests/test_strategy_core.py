from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.core import RiskContext, evaluate_closed_candle
from harbor_bot.strategy.models import (
    Bias,
    DayState,
    InstrumentRules,
    LevelName,
    SessionLevels,
    SweepState,
    strategy_config_from_defaults,
)


def test_core_detects_clean_sweep_then_market_entry_setup() -> None:
    state = DayState(trading_date=date(2026, 1, 15))
    sweep_result = evaluate_closed_candle(
        state,
        _candle("2026-01-15T14:30:00+00:00", low="1.07980", close="1.08020"),
        candle_history=[],
        candle_index=10,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(),
    )

    assert sweep_result.decisions[0].kind == "sweep"
    assert sweep_result.state.active_sweep is not None

    history = [
        _candle("2026-01-15T14:31:00+00:00", high="1.0810", low="1.0800"),
        _candle("2026-01-15T14:32:00+00:00", high="1.0815", low="1.0805"),
        _candle("2026-01-15T14:33:00+00:00", high="1.0830", low="1.0820"),
    ]
    entry_result = evaluate_closed_candle(
        sweep_result.state,
        history[-1],
        candle_history=history,
        candle_index=13,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(entry_price=Decimal("1.0830")),
    )

    assert entry_result.decisions[0].kind == "market_entry"
    setup = entry_result.decisions[0].payload["setup"]
    assert setup.side == "long"
    assert setup.level_name == LevelName.ASIA_LOW
    assert entry_result.state.active_sweep is None
    assert entry_result.state.trades_taken == 1
    assert entry_result.state.taken_levels == frozenset({LevelName.ASIA_LOW})


def test_core_rejects_sweep_without_rejection_close() -> None:
    result = evaluate_closed_candle(
        DayState(trading_date=date(2026, 1, 15)),
        _candle("2026-01-15T14:30:00+00:00", high="1.10020", close="1.10005"),
        candle_history=[],
        candle_index=10,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(),
    )

    assert result.decisions == []
    assert result.state.active_sweep is None


def test_core_ignores_sweeps_outside_ny_trade_window() -> None:
    result = evaluate_closed_candle(
        DayState(trading_date=date(2026, 1, 15)),
        _candle("2026-01-15T17:00:00+00:00", low="1.07980", close="1.08020"),
        candle_history=[],
        candle_index=10,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(),
    )

    assert result.decisions == []
    assert result.state.active_sweep is None


def test_core_keeps_waiting_on_wrong_direction_fvg() -> None:
    state = DayState(
        trading_date=date(2026, 1, 15),
        active_sweep=_sweep(Bias.BULLISH),
    )
    history = [
        _candle("2026-01-15T14:31:00+00:00", high="1.1000", low="1.0990"),
        _candle("2026-01-15T14:32:00+00:00", high="1.0995", low="1.0985"),
        _candle("2026-01-15T14:33:00+00:00", high="1.0980", low="1.0970"),
    ]

    result = evaluate_closed_candle(
        state,
        history[-1],
        candle_history=history,
        candle_index=13,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(),
    )

    assert result.decisions == []
    assert result.state.active_sweep == state.active_sweep


def test_core_expires_sweep_after_fvg_deadline() -> None:
    state = DayState(
        trading_date=date(2026, 1, 15),
        active_sweep=_sweep(Bias.BULLISH),
    )

    result = evaluate_closed_candle(
        state,
        _candle("2026-01-15T14:40:00+00:00"),
        candle_history=[],
        candle_index=19,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(),
    )

    assert result.decisions[0].kind == "sweep_expired"
    assert result.state.active_sweep is None


def test_core_emits_ny_close_flatten() -> None:
    result = evaluate_closed_candle(
        DayState(trading_date=date(2026, 1, 15), has_open_position=True),
        _candle("2026-01-15T16:30:00+00:00"),
        candle_history=[],
        candle_index=100,
        session_levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        risk_context=_risk(),
    )

    assert result.decisions[0].kind == "flatten"
    assert result.decisions[0].payload["reason"] == "ny_close"
    assert result.state.has_open_position is False


def test_core_rejects_incomplete_candles() -> None:
    with pytest.raises(ValueError, match="closed candles only"):
        evaluate_closed_candle(
            DayState(trading_date=date(2026, 1, 15)),
            _candle("2026-01-15T14:30:00+00:00", complete=False),
            candle_history=[],
            candle_index=10,
            session_levels=_levels(),
            config=_config(),
            instrument_rules=_rules(),
            risk_context=_risk(),
        )


def _config():
    return strategy_config_from_defaults(load_default_config())


def _risk(entry_price: Decimal = Decimal("1.0900")) -> RiskContext:
    return RiskContext(
        nav=Decimal("10000"),
        day_start_nav=Decimal("10000"),
        spread_pips=Decimal("0.5"),
        entry_price=entry_price,
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


def _levels() -> SessionLevels:
    return SessionLevels(
        trading_date=date(2026, 1, 15),
        instrument="EUR_USD",
        asia_high=Decimal("1.1000"),
        asia_low=Decimal("1.0800"),
        london_high=Decimal("1.1050"),
        london_low=Decimal("1.0750"),
    )


def _sweep(bias: Bias) -> SweepState:
    return SweepState(
        level_name=LevelName.ASIA_LOW if bias == Bias.BULLISH else LevelName.ASIA_HIGH,
        level_price=Decimal("1.0800") if bias == Bias.BULLISH else Decimal("1.1000"),
        bias=bias,
        sweep_extreme=Decimal("1.0798") if bias == Bias.BULLISH else Decimal("1.1002"),
        swept_ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        candle_index=10,
        fvg_deadline_index=18,
    )


def _candle(
    ts: str,
    *,
    high: str = "1.0810",
    low: str = "1.0800",
    close: str = "1.0805",
    complete: bool = True,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.0805"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=100,
        complete=complete,
    )
