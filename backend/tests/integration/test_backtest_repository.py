import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from harbor_bot.backtester.models import (
    BacktestRunResult,
    BacktestStats,
    BacktestStatus,
    BacktestTrade,
)
from harbor_bot.persistence.backtest_repository import append_backtest_result, get_backtest_run
from harbor_bot.persistence.database import create_engine
from harbor_bot.persistence.schema import backtest_runs, backtest_trades
from harbor_bot.settings import Settings


def test_backtest_runs_and_trades_are_persisted_in_one_transaction(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_backtest_round_trip(postgres_url))


def test_backtest_run_rolls_back_when_trade_insert_fails(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_backtest_rollback(postgres_url))


async def _assert_backtest_round_trip(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    result = _result()
    try:
        run_id = await append_backtest_result(engine, result)

        async with engine.connect() as connection:
            stored = await get_backtest_run(connection, run_id=run_id)

        assert stored is not None
        assert stored["id"] == run_id
        assert stored["params_json"] == {"instrument": "EUR_USD"}
        assert stored["stats_json"] == result.stats.to_jsonable()
        assert len(stored["trades"]) == 1
        assert stored["trades"][0]["side"] == "long"
        assert stored["trades"][0]["units"] == Decimal("10000.0000")
        assert stored["trades"][0]["entry_price"] == Decimal("1.10000000")
        assert stored["trades"][0]["pnl"] == Decimal("40.0000")
    finally:
        await engine.dispose()


async def _assert_backtest_rollback(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    result = _result()
    bad_trade = result.trades[0]
    object.__setattr__(bad_trade, "side", "invalid")
    bad_result = BacktestRunResult(
        status=BacktestStatus.COMPLETED,
        stats=result.stats,
        trades=(bad_trade,),
        params_json=result.params_json,
    )
    try:
        with pytest.raises(IntegrityError):
            await append_backtest_result(engine, bad_result)

        async with engine.connect() as connection:
            run_count = await connection.scalar(select(func.count()).select_from(backtest_runs))
            trade_count = await connection.scalar(select(func.count()).select_from(backtest_trades))

        assert run_count == 0
        assert trade_count == 0
    finally:
        await engine.dispose()


def _result() -> BacktestRunResult:
    return BacktestRunResult(
        status=BacktestStatus.COMPLETED,
        stats=BacktestStats(
            trade_count=1,
            win_rate=Decimal("1"),
            net_pnl=Decimal("40"),
            expectancy=Decimal("40"),
            average_r=Decimal("2"),
            max_drawdown=Decimal("0"),
            ending_nav=Decimal("10040"),
            lookahead_sanity_passed=True,
        ),
        trades=(
            BacktestTrade(
                instrument="EUR_USD",
                side="long",
                units=Decimal("10000"),
                entry_price=Decimal("1.1000"),
                entry_ts=datetime(2026, 1, 15, 14, 34, tzinfo=UTC),
                stop=Decimal("1.0980"),
                target=Decimal("1.1040"),
                exit_price=Decimal("1.1040"),
                exit_ts=datetime(2026, 1, 15, 14, 40, tzinfo=UTC),
                pnl=Decimal("40"),
                r_multiple=Decimal("2"),
                exit_reason="take_profit",
            ),
        ),
        params_json={"instrument": "EUR_USD"},
    )


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
