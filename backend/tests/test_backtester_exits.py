from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from harbor_bot.backtester.fills import (
    OpenBacktestPosition,
    simulate_bracket_exit,
    simulate_exit,
)
from harbor_bot.backtester.models import BacktestConfig
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    strategy_config_from_defaults,
)

TS = datetime(2026, 1, 15, 14, 0, tzinfo=UTC)
CONFIG = BacktestConfig()


def _candle(minute: int, *, high: str, low: str, close: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=TS + timedelta(minutes=minute),
        o=Decimal(close),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=1,
    )


def test_time_stop_exits_at_close_after_duration() -> None:
    config = replace(_strategy(), exit_mode="time_stop", time_stop_minutes=120)
    position = _long(stop="1.09800", target="1.10400")
    # 130 minutes later, price has neither hit the stop nor the target.
    candle = _candle(130, high="1.10150", low="1.10050", close="1.10100")

    _, trade = simulate_exit(
        position,
        candle=candle,
        strategy_config=config,
        backtest_config=CONFIG,
        instrument_rules=_rules(),
        recent_candles=[candle],
    )

    assert trade is not None
    assert trade.exit_reason == "time_stop"


def test_time_stop_holds_before_duration() -> None:
    config = replace(_strategy(), exit_mode="time_stop", time_stop_minutes=120)
    position = _long(stop="1.09800", target="1.10400")
    candle = _candle(30, high="1.10150", low="1.10050", close="1.10100")

    _, trade = simulate_exit(
        position,
        candle=candle,
        strategy_config=config,
        backtest_config=CONFIG,
        instrument_rules=_rules(),
        recent_candles=[candle],
    )

    assert trade is None


def test_atr_trailing_stop_locks_in_profit_above_original_stop() -> None:
    config = replace(_strategy(), exit_mode="atr_trail", atr_trail_mult=Decimal("1.5"))
    position = _long(stop="1.09000", target="1.20000")
    rising = [
        _candle(0, high="1.10100", low="1.09950", close="1.10050"),
        _candle(1, high="1.10300", low="1.10100", close="1.10250"),
        _candle(2, high="1.10500", low="1.10300", close="1.10450"),
        _candle(3, high="1.10450", low="1.10000", close="1.10050"),
    ]

    trade = _run_sequence(position, rising, config)

    assert trade is not None
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price > Decimal("1.09000")  # trailed above the original stop
    assert trade.pnl > 0  # locked-in profit


def test_bracket_mode_matches_plain_bracket_exit() -> None:
    config = replace(_strategy(), exit_mode="bracket")
    position = _long(stop="1.09800", target="1.10400")
    target_hit = _candle(5, high="1.10450", low="1.10100", close="1.10420")

    _, dispatched = simulate_exit(
        position,
        candle=target_hit,
        strategy_config=config,
        backtest_config=CONFIG,
        instrument_rules=_rules(),
        recent_candles=[target_hit],
    )
    direct = simulate_bracket_exit(
        position, candle=target_hit, config=CONFIG, instrument_rules=_rules()
    )

    assert dispatched is not None
    assert direct is not None
    assert dispatched.exit_price == direct.exit_price
    assert dispatched.exit_reason == direct.exit_reason == "take_profit"


def _run_sequence(position: OpenBacktestPosition, candles: list[ClosedCandle], config):
    history: list[ClosedCandle] = []
    for candle in candles:
        history.append(candle)
        position, trade = simulate_exit(
            position,
            candle=candle,
            strategy_config=config,
            backtest_config=CONFIG,
            instrument_rules=_rules(),
            recent_candles=history,
        )
        if trade is not None:
            return trade
    return None


def _strategy():
    return strategy_config_from_defaults(load_default_config())


def _long(*, stop: str, target: str) -> OpenBacktestPosition:
    setup = MarketEntrySetup(
        ts=TS,
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.10000"),
        stop=Decimal(stop),
        target=Decimal(target),
        risk=Decimal("1.10000") - Decimal(stop),
        units=Decimal("10000"),
    )
    return OpenBacktestPosition(setup=setup, entry_price=Decimal("1.10000"), entry_ts=TS)


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
