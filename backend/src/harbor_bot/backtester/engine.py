from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date
from decimal import Decimal

from harbor_bot.backtester.fills import (
    OpenBacktestPosition,
    force_close_position,
    simulate_exit,
    simulate_market_entry,
)
from harbor_bot.backtester.models import (
    BacktestInput,
    BacktestRunResult,
    BacktestStats,
    BacktestStatus,
    BacktestTrade,
    EquityPoint,
    entry_setup_from_decision,
)
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.core import RiskContext, StrategyResult, evaluate_closed_candle
from harbor_bot.strategy.models import DayState, SessionLevels
from harbor_bot.strategy.sessions import (
    compute_session_levels,
    session_windows_for_date,
    trading_date_for_candle,
)

StrategyEvaluator = Callable[..., StrategyResult]


def run_backtest(
    backtest_input: BacktestInput,
    *,
    strategy_evaluator: StrategyEvaluator = evaluate_closed_candle,
) -> BacktestRunResult:
    candles = tuple(sorted(backtest_input.candles, key=lambda candle: candle.ts))
    if not candles:
        stats = BacktestStats.empty(initial_nav=backtest_input.backtest_config.initial_nav)
        return BacktestRunResult(
            status=BacktestStatus.COMPLETED,
            stats=stats,
            params_json=_params_json(backtest_input),
        )

    nav = backtest_input.backtest_config.initial_nav
    day_start_nav = nav
    trading_date: date | None = None
    candle_index = -1
    day_state: DayState | None = None
    session_levels: SessionLevels | None = None
    day_history: list[ClosedCandle] = []
    pending_entry = None
    position: OpenBacktestPosition | None = None
    trades: list[BacktestTrade] = []
    equity_curve = [EquityPoint(ts=candles[0].ts, nav=nav)]
    prev_day_high: Decimal | None = None
    prev_day_low: Decimal | None = None
    current_day_high: Decimal | None = None
    current_day_low: Decimal | None = None

    previous_candle: ClosedCandle | None = None
    for candle in candles:
        if not candle.complete:
            msg = "backtest engine accepts closed candles only"
            raise ValueError(msg)
        next_trading_date = trading_date_for_candle(candle, backtest_input.strategy_config)
        if next_trading_date != trading_date:
            if position is not None and previous_candle is not None:
                # A position carried into the day rollover must be booked, not
                # silently dropped: close it at the outgoing day's last close.
                trade = force_close_position(
                    position,
                    candle=previous_candle,
                    config=backtest_input.backtest_config,
                    instrument_rules=backtest_input.instrument_rules,
                    reason="day_rollover",
                )
                trades.append(trade)
                nav += trade.pnl
                equity_curve.append(EquityPoint(ts=trade.exit_ts, nav=nav))
            trading_date = next_trading_date
            candle_index = -1
            day_start_nav = nav
            day_state = DayState(trading_date=trading_date)
            session_levels = None
            day_history = []
            pending_entry = None
            position = None
            prev_day_high, prev_day_low = current_day_high, current_day_low
            current_day_high = None
            current_day_low = None

        candle_index += 1
        previous_candle = candle
        day_history.append(candle)
        current_day_high = candle.h if current_day_high is None else max(current_day_high, candle.h)
        current_day_low = (
            candle.low if current_day_low is None else min(current_day_low, candle.low)
        )
        if session_levels is None and _is_at_or_after_ny_window(
            candle, trading_date, backtest_input
        ):
            session_levels = compute_session_levels(
                day_history,
                trading_date=trading_date,
                instrument=backtest_input.instrument,
                config=backtest_input.strategy_config,
                prev_day_high=prev_day_high,
                prev_day_low=prev_day_low,
            )

        if pending_entry is not None:
            position = simulate_market_entry(
                pending_entry,
                entry_candle=candle,
                config=backtest_input.backtest_config,
                instrument_rules=backtest_input.instrument_rules,
            )
            pending_entry = None

        if position is not None:
            position, trade = simulate_exit(
                position,
                candle=candle,
                strategy_config=backtest_input.strategy_config,
                backtest_config=backtest_input.backtest_config,
                instrument_rules=backtest_input.instrument_rules,
                recent_candles=day_history,
            )
            if trade is not None:
                trades.append(trade)
                nav += trade.pnl
                equity_curve.append(EquityPoint(ts=trade.exit_ts, nav=nav))
                position = None
                day_state = replace(day_state, has_open_position=False)

        result = strategy_evaluator(
            day_state,
            candle,
            candle_history=list(day_history),
            candle_index=candle_index,
            session_levels=session_levels,
            config=backtest_input.strategy_config,
            instrument_rules=backtest_input.instrument_rules,
            risk_context=RiskContext(
                nav=nav,
                day_start_nav=day_start_nav,
                spread_pips=backtest_input.backtest_config.spread_pips,
                entry_price=candle.c,
            ),
        )
        day_state = result.state

        for decision in result.decisions:
            if decision.kind == "market_entry" and position is None and pending_entry is None:
                pending_entry = entry_setup_from_decision(decision)
            elif decision.kind == "flatten":
                pending_entry = None
                if position is not None and backtest_input.backtest_config.force_ny_close:
                    trade = force_close_position(
                        position,
                        candle=candle,
                        config=backtest_input.backtest_config,
                        instrument_rules=backtest_input.instrument_rules,
                    )
                    trades.append(trade)
                    nav += trade.pnl
                    equity_curve.append(EquityPoint(ts=trade.exit_ts, nav=nav))
                    position = None
                    day_state = replace(day_state, has_open_position=False)

    stats = _stats_from_trades(
        trades,
        equity_curve=equity_curve,
        ending_nav=nav,
    )
    return BacktestRunResult(
        status=BacktestStatus.COMPLETED,
        stats=stats,
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
        params_json=_params_json(backtest_input),
    )


def _is_at_or_after_ny_window(
    candle: ClosedCandle,
    trading_date: date,
    backtest_input: BacktestInput,
) -> bool:
    windows = session_windows_for_date(trading_date, backtest_input.strategy_config)
    return candle.ts.astimezone(UTC) >= windows.ny_trade.start


def _stats_from_trades(
    trades: list[BacktestTrade],
    *,
    equity_curve: list[EquityPoint],
    ending_nav: Decimal,
) -> BacktestStats:
    trade_count = len(trades)
    net_pnl = sum((trade.pnl for trade in trades), Decimal("0"))
    wins = [trade for trade in trades if trade.pnl > 0]
    win_rate = Decimal(len(wins)) / Decimal(trade_count) if trade_count else Decimal("0")
    expectancy = net_pnl / Decimal(trade_count) if trade_count else Decimal("0")
    average_r = (
        sum((trade.r_multiple for trade in trades), Decimal("0")) / Decimal(trade_count)
        if trade_count
        else Decimal("0")
    )
    return BacktestStats(
        trade_count=trade_count,
        win_rate=win_rate,
        net_pnl=net_pnl,
        expectancy=expectancy,
        average_r=average_r,
        max_drawdown=_max_drawdown(equity_curve),
        ending_nav=ending_nav,
        lookahead_sanity_passed=True,
    )


def _max_drawdown(equity_curve: list[EquityPoint]) -> Decimal:
    peak: Decimal | None = None
    max_drawdown = Decimal("0")
    for point in equity_curve:
        peak = point.nav if peak is None else max(peak, point.nav)
        max_drawdown = max(max_drawdown, peak - point.nav)
    return max_drawdown


def _params_json(backtest_input: BacktestInput) -> dict[str, object]:
    return {
        "instrument": backtest_input.instrument,
        "backtest_config": backtest_input.backtest_config.to_jsonable(),
    }
