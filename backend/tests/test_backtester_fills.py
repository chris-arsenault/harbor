from datetime import UTC, datetime
from decimal import Decimal

from harbor_bot.backtester.fills import (
    force_close_position,
    market_entry_price,
    simulate_bracket_exit,
    simulate_market_entry,
)
from harbor_bot.backtester.models import BacktestConfig, FillPolicy
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import InstrumentRules, LevelName, MarketEntrySetup


def test_market_entry_fills_next_candle_open_with_spread_and_slippage() -> None:
    config = BacktestConfig(spread_pips=Decimal("2.0"), slippage_pips=Decimal("0.5"))
    rules = _rules()

    assert market_entry_price(
        side="long",
        midpoint_open=Decimal("1.10000"),
        config=config,
        instrument_rules=rules,
    ) == Decimal("1.10015")
    assert market_entry_price(
        side="short",
        midpoint_open=Decimal("1.10000"),
        config=config,
        instrument_rules=rules,
    ) == Decimal("1.09985")


def test_simulate_market_entry_uses_next_closed_candle_open() -> None:
    position = simulate_market_entry(
        _setup(),
        entry_candle=_candle("2026-01-15T14:34:00+00:00", open_="1.10000"),
        config=BacktestConfig(spread_pips=Decimal("2.0"), slippage_pips=Decimal("0.5")),
        instrument_rules=_rules(),
    )

    assert position.entry_ts == datetime(2026, 1, 15, 14, 34, tzinfo=UTC)
    assert position.entry_price == Decimal("1.10015")


def test_bracket_exit_hits_target_and_computes_pnl_and_r_multiple() -> None:
    trade = simulate_bracket_exit(
        _position(),
        candle=_candle("2026-01-15T14:40:00+00:00", high="1.1041", low="1.1005"),
        config=BacktestConfig(spread_pips=Decimal("0"), slippage_pips=Decimal("0")),
        instrument_rules=_rules(),
    )

    assert trade is not None
    assert trade.exit_reason == "take_profit"
    assert trade.exit_price == Decimal("1.1040")
    assert trade.pnl == Decimal("40.0000")
    assert trade.r_multiple == Decimal("2")


def test_bracket_exit_subtracts_round_trip_commission() -> None:
    trade = simulate_bracket_exit(
        _position(),
        candle=_candle("2026-01-15T14:40:00+00:00", high="1.1041", low="1.1005"),
        config=BacktestConfig(
            spread_pips=Decimal("0"),
            slippage_pips=Decimal("0"),
            commission_per_unit=Decimal("0.0001"),
        ),
        instrument_rules=_rules(),
    )

    assert trade is not None
    assert trade.pnl == Decimal("38.0000")


def test_bracket_exit_hits_stop_loss() -> None:
    trade = simulate_bracket_exit(
        _position(),
        candle=_candle("2026-01-15T14:40:00+00:00", high="1.1005", low="1.0979"),
        config=BacktestConfig(spread_pips=Decimal("0"), slippage_pips=Decimal("0")),
        instrument_rules=_rules(),
    )

    assert trade is not None
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == Decimal("1.0980")
    assert trade.pnl == Decimal("-20.0000")
    assert trade.r_multiple == Decimal("-1")


def test_ambiguous_bracket_touch_uses_configured_fill_policy() -> None:
    pessimistic = simulate_bracket_exit(
        _position(),
        candle=_candle("2026-01-15T14:40:00+00:00", high="1.1041", low="1.0979"),
        config=BacktestConfig(
            spread_pips=Decimal("0"),
            slippage_pips=Decimal("0"),
            ambiguous_fill_policy=FillPolicy.PESSIMISTIC,
        ),
        instrument_rules=_rules(),
    )
    optimistic = simulate_bracket_exit(
        _position(),
        candle=_candle("2026-01-15T14:40:00+00:00", high="1.1041", low="1.0979"),
        config=BacktestConfig(
            spread_pips=Decimal("0"),
            slippage_pips=Decimal("0"),
            ambiguous_fill_policy=FillPolicy.OPTIMISTIC,
        ),
        instrument_rules=_rules(),
    )

    assert pessimistic is not None
    assert optimistic is not None
    assert pessimistic.exit_reason == "stop_loss"
    assert optimistic.exit_reason == "take_profit"


def test_forced_ny_close_exits_at_close_with_slippage() -> None:
    trade = force_close_position(
        _position(),
        candle=_candle("2026-01-15T16:30:00+00:00", close="1.1010"),
        config=BacktestConfig(spread_pips=Decimal("0"), slippage_pips=Decimal("0.5")),
        instrument_rules=_rules(),
    )

    assert trade.exit_reason == "ny_close"
    assert trade.exit_price == Decimal("1.10095")
    assert trade.pnl == Decimal("9.50000")


def _position():
    return simulate_market_entry(
        _setup(),
        entry_candle=_candle("2026-01-15T14:34:00+00:00", open_="1.1000"),
        config=BacktestConfig(spread_pips=Decimal("0"), slippage_pips=Decimal("0")),
        instrument_rules=_rules(),
    )


def _setup() -> MarketEntrySetup:
    return MarketEntrySetup(
        ts=datetime(2026, 1, 15, 14, 33, tzinfo=UTC),
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.1000"),
        stop=Decimal("1.0980"),
        target=Decimal("1.1040"),
        risk=Decimal("0.0020"),
        units=Decimal("10000"),
    )


def _candle(
    ts: str,
    *,
    open_: str = "1.1000",
    high: str = "1.1010",
    low: str = "1.0990",
    close: str = "1.1005",
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal(open_),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=100,
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
