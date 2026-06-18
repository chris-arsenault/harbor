from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from harbor_bot.backtester.models import BacktestRunResult, BacktestTrade
from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.schema import backtest_runs, backtest_trades


async def append_backtest_result(engine: AsyncEngine, result: BacktestRunResult) -> int:
    return await append_backtest_run(
        engine,
        params_json=result.params_json,
        stats_json=result.stats.to_jsonable(),
        trades=result.trades,
    )


async def append_backtest_run(
    engine: AsyncEngine,
    *,
    params_json: Mapping[str, Any],
    stats_json: Mapping[str, Any],
    trades: Iterable[BacktestTrade],
) -> int:
    async with transaction(engine) as connection:
        run_result = await connection.execute(
            insert(backtest_runs)
            .values(params_json=dict(params_json), stats_json=dict(stats_json))
            .returning(backtest_runs.c.id)
        )
        run_id = int(run_result.scalar_one())
        for trade in trades:
            await connection.execute(
                insert(backtest_trades).values(run_id=run_id, **trade.to_persistence_row())
            )
        return run_id


async def get_backtest_run(
    connection: AsyncConnection,
    *,
    run_id: int,
) -> dict[str, Any] | None:
    run_result = await connection.execute(
        select(
            backtest_runs.c.id,
            backtest_runs.c.created_ts,
            backtest_runs.c.params_json,
            backtest_runs.c.stats_json,
        ).where(backtest_runs.c.id == run_id)
    )
    run = run_result.mappings().first()
    if run is None:
        return None

    trade_result = await connection.execute(
        select(
            backtest_trades.c.id,
            backtest_trades.c.run_id,
            backtest_trades.c.side,
            backtest_trades.c.units,
            backtest_trades.c.entry_price,
            backtest_trades.c.entry_ts,
            backtest_trades.c.exit_price,
            backtest_trades.c.exit_ts,
            backtest_trades.c.pnl,
            backtest_trades.c.r_multiple,
            backtest_trades.c.exit_reason,
        )
        .where(backtest_trades.c.run_id == run_id)
        .order_by(backtest_trades.c.id)
    )
    data = dict(run)
    data["trades"] = [dict(row) for row in trade_result.mappings()]
    return data


async def list_backtest_runs(
    connection: AsyncConnection,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            backtest_runs.c.id.label("run_id"),
            backtest_runs.c.created_ts,
            backtest_runs.c.params_json.label("params"),
            backtest_runs.c.stats_json.label("stats"),
            func.count(backtest_trades.c.id).label("trade_count"),
        )
        .select_from(
            backtest_runs.outerjoin(
                backtest_trades,
                backtest_trades.c.run_id == backtest_runs.c.id,
            )
        )
        .group_by(
            backtest_runs.c.id,
            backtest_runs.c.created_ts,
            backtest_runs.c.params_json,
            backtest_runs.c.stats_json,
        )
        .order_by(backtest_runs.c.created_ts.desc(), backtest_runs.c.id.desc())
        .limit(limit)
    )
    return [dict(row) for row in result.mappings()]
