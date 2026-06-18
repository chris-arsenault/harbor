from datetime import UTC, datetime
from decimal import Decimal

from harbor_bot.backtester.models import BacktestStats, BacktestTrade, EquityPoint
from harbor_bot.backtester.stats import calculate_backtest_stats, lookahead_sanity_passed


def test_calculate_backtest_stats_summarizes_trades_and_equity() -> None:
    stats = calculate_backtest_stats(
        [
            _trade(pnl=Decimal("20"), r_multiple=Decimal("1")),
            _trade(pnl=Decimal("-10"), r_multiple=Decimal("-0.5")),
        ],
        [
            _equity("2026-01-15T14:30:00+00:00", "10000"),
            _equity("2026-01-15T14:40:00+00:00", "10020"),
            _equity("2026-01-15T14:50:00+00:00", "10010"),
        ],
        initial_nav=Decimal("10000"),
    )

    assert stats.trade_count == 2
    assert stats.win_rate == Decimal("0.5")
    assert stats.net_pnl == Decimal("10")
    assert stats.expectancy == Decimal("5")
    assert stats.average_r == Decimal("0.25")
    assert stats.max_drawdown == Decimal("10")
    assert stats.ending_nav == Decimal("10010")
    assert stats.lookahead_sanity_passed is True


def test_calculate_backtest_stats_handles_no_trades() -> None:
    stats = calculate_backtest_stats([], [], initial_nav=Decimal("10000"))

    assert stats.to_jsonable() == {
        "trade_count": 0,
        "win_rate": "0",
        "net_pnl": "0",
        "expectancy": "0",
        "average_r": "0",
        "max_drawdown": "0",
        "ending_nav": "10000",
        "lookahead_sanity_passed": True,
    }


def test_lookahead_sanity_flags_implausibly_perfect_large_samples() -> None:
    assert (
        lookahead_sanity_passed(
            BacktestStats(
                trade_count=25,
                win_rate=Decimal("0.96"),
                net_pnl=Decimal("1000"),
                expectancy=Decimal("40"),
                average_r=Decimal("2.5"),
                max_drawdown=Decimal("0"),
                ending_nav=Decimal("11000"),
                lookahead_sanity_passed=True,
            )
        )
        is False
    )


def _trade(*, pnl: Decimal, r_multiple: Decimal) -> BacktestTrade:
    return BacktestTrade(
        instrument="EUR_USD",
        side="long",
        units=Decimal("10000"),
        entry_price=Decimal("1.1000"),
        entry_ts=datetime(2026, 1, 15, 14, 34, tzinfo=UTC),
        stop=Decimal("1.0980"),
        target=Decimal("1.1040"),
        exit_price=Decimal("1.1040") if pnl > 0 else Decimal("1.0990"),
        exit_ts=datetime(2026, 1, 15, 14, 40, tzinfo=UTC),
        pnl=pnl,
        r_multiple=r_multiple,
        exit_reason="take_profit" if pnl > 0 else "stop_loss",
    )


def _equity(ts: str, nav: str) -> EquityPoint:
    return EquityPoint(ts=datetime.fromisoformat(ts), nav=Decimal(nav))
