from decimal import Decimal
from typing import Any

from harbor_bot.backtester.models import (
    BacktestRunResult,
    BacktestStats,
    BacktestTrade,
    EquityPoint,
)


def calculate_backtest_stats(
    trades: tuple[BacktestTrade, ...] | list[BacktestTrade],
    equity_curve: tuple[EquityPoint, ...] | list[EquityPoint],
    *,
    initial_nav: Decimal,
) -> BacktestStats:
    trade_count = len(trades)
    net_pnl = sum((trade.pnl for trade in trades), Decimal("0"))
    win_rate = _win_rate(trades)
    expectancy = net_pnl / Decimal(trade_count) if trade_count else Decimal("0")
    average_r = _average_r(trades)
    ending_nav = equity_curve[-1].nav if equity_curve else initial_nav + net_pnl
    stats = BacktestStats(
        trade_count=trade_count,
        win_rate=win_rate,
        net_pnl=net_pnl,
        expectancy=expectancy,
        average_r=average_r,
        max_drawdown=max_drawdown(equity_curve),
        ending_nav=ending_nav,
        lookahead_sanity_passed=True,
    )
    return BacktestStats(
        trade_count=stats.trade_count,
        win_rate=stats.win_rate,
        net_pnl=stats.net_pnl,
        expectancy=stats.expectancy,
        average_r=stats.average_r,
        max_drawdown=stats.max_drawdown,
        ending_nav=stats.ending_nav,
        lookahead_sanity_passed=lookahead_sanity_passed(stats),
    )


def max_drawdown(equity_curve: tuple[EquityPoint, ...] | list[EquityPoint]) -> Decimal:
    peak: Decimal | None = None
    value = Decimal("0")
    for point in equity_curve:
        peak = point.nav if peak is None else max(peak, point.nav)
        value = max(value, peak - point.nav)
    return value


def lookahead_sanity_passed(stats: BacktestStats) -> bool:
    if stats.trade_count < 20:
        return True
    return not (stats.win_rate >= Decimal("0.95") and stats.average_r >= Decimal("2"))


def result_snapshot(result: BacktestRunResult) -> dict[str, Any]:
    return {
        "stats": result.stats.to_jsonable(),
        "trades": [trade.to_jsonable() for trade in result.trades],
    }


def _win_rate(trades: tuple[BacktestTrade, ...] | list[BacktestTrade]) -> Decimal:
    if not trades:
        return Decimal("0")
    wins = [trade for trade in trades if trade.pnl > 0]
    return Decimal(len(wins)) / Decimal(len(trades))


def _average_r(trades: tuple[BacktestTrade, ...] | list[BacktestTrade]) -> Decimal:
    if not trades:
        return Decimal("0")
    return sum((trade.r_multiple for trade in trades), Decimal("0")) / Decimal(len(trades))
