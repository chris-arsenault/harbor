from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestConfig, BacktestInput, BacktestStatus
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.core import StrategyResult
from harbor_bot.strategy.models import (
    DayState,
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    StrategyDecision,
    strategy_config_from_defaults,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


def test_engine_replays_clean_fixture_through_strategy_core_and_fills_trade() -> None:
    result = run_backtest(_input("clean_signal_day.json"))

    assert result.status == BacktestStatus.COMPLETED
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "long"
    assert trade.entry_ts.isoformat() == "2026-01-15T14:34:00+00:00"
    assert trade.entry_price == Decimal("1.09105")
    assert trade.exit_reason == "take_profit"
    assert trade.pnl > 0
    assert result.equity_curve[-1].nav == BacktestConfig().initial_nav + trade.pnl
    assert result.stats.trade_count == 1


def test_engine_replays_no_trade_fixture_without_trades() -> None:
    result = run_backtest(_input("no_trade_day.json"))

    assert result.status == BacktestStatus.COMPLETED
    assert result.trades == ()
    assert result.stats.trade_count == 0
    assert result.equity_curve[-1].nav == BacktestConfig().initial_nav


def test_engine_only_passes_history_through_the_current_closed_candle_to_strategy() -> None:
    calls = []

    def evaluator(day_state: DayState, candle, *, candle_history, **kwargs) -> StrategyResult:
        assert candle_history[-1] == candle
        assert all(history_candle.ts <= candle.ts for history_candle in candle_history)
        calls.append((candle.ts, candle_history[-1].ts, len(candle_history)))
        return StrategyResult(state=day_state, decisions=[])

    run_backtest(_input("clean_signal_day.json"), strategy_evaluator=evaluator)

    assert calls
    assert all(current_ts == last_history_ts for current_ts, last_history_ts, _ in calls)


def test_engine_computes_session_levels_at_each_day_ny_boundary() -> None:
    candles = load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json") + load_candle_fixture(
        FIXTURE_DIR / "no_trade_day.json"
    )
    seen_boundaries = []

    def evaluator(day_state: DayState, candle, *, session_levels, **kwargs) -> StrategyResult:
        if candle.ts.hour == 14 and candle.ts.minute == 30:
            seen_boundaries.append((day_state.trading_date, session_levels))
        return StrategyResult(state=day_state, decisions=[])

    run_backtest(_input_from_candles(candles), strategy_evaluator=evaluator)

    assert [trading_date for trading_date, _ in seen_boundaries] == [
        date(2026, 1, 15),
        date(2026, 1, 16),
    ]
    assert all(levels is not None for _, levels in seen_boundaries)


def test_engine_books_open_position_at_day_rollover_instead_of_dropping_it() -> None:
    # A position still open when the trading date changes must be force-closed
    # at the outgoing day's last candle, never silently discarded.
    day_one = datetime(2026, 1, 15, 13, 30, tzinfo=UTC)
    day_two = datetime(2026, 1, 16, 13, 30, tzinfo=UTC)
    candles = (
        _flat_candle(day_one),
        _flat_candle(day_one + timedelta(minutes=1)),
        _flat_candle(day_two),
        _flat_candle(day_two + timedelta(minutes=1)),
    )
    entered = []

    def evaluator(day_state: DayState, candle, **kwargs) -> StrategyResult:
        if not entered:
            entered.append(candle.ts)
            return StrategyResult(
                state=day_state,
                decisions=[
                    StrategyDecision(
                        kind="market_entry",
                        ts=candle.ts,
                        payload={"setup": _far_bracket_setup(candle.ts)},
                    )
                ],
            )
        return StrategyResult(state=day_state, decisions=[])

    result = run_backtest(_input_from_candles(candles), strategy_evaluator=evaluator)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "day_rollover"
    assert trade.exit_ts == day_one + timedelta(minutes=1)
    assert result.equity_curve[-1].nav == BacktestConfig().initial_nav + trade.pnl


def _flat_candle(ts: datetime) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=ts,
        o=Decimal("1.1000"),
        h=Decimal("1.1002"),
        low=Decimal("1.0998"),
        c=Decimal("1.1000"),
        volume=50,
    )


def _far_bracket_setup(ts: datetime) -> MarketEntrySetup:
    return MarketEntrySetup(
        ts=ts,
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.1000"),
        stop=Decimal("1.0500"),
        target=Decimal("1.1500"),
        risk=Decimal("0.0500"),
        units=Decimal("10000"),
    )


def _input(name: str) -> BacktestInput:
    return _input_from_candles(load_candle_fixture(FIXTURE_DIR / name))


def _input_from_candles(candles) -> BacktestInput:
    return BacktestInput(
        instrument="EUR_USD",
        candles=candles,
        strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
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
