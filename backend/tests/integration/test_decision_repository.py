import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.decision_repository import (
    append_equity_snapshot,
    append_fvg,
    append_signal,
    append_sweep,
    append_trade,
    list_equity_snapshots,
    list_fvgs,
    list_signals,
    list_sweeps,
    list_trades,
)
from harbor_bot.persistence.schema import fvgs, sweeps
from harbor_bot.settings import Settings


def test_decision_facts_append_and_read(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_append_and_read(postgres_url))


def test_decision_constraints_are_enforced(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_constraints(postgres_url))


def test_decision_transaction_rolls_back_related_facts(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_related_fact_rollback(postgres_url))


async def _assert_append_and_read(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    try:
        async with transaction(engine) as connection:
            sweep_id = await append_sweep(
                connection,
                ts=ts,
                instrument="EUR_USD",
                level_name="asia_high",
                level_price=Decimal("1.1050"),
                direction="bullish",
                sweep_extreme=Decimal("1.1065"),
            )
            fvg_id = await append_fvg(
                connection,
                ts=ts,
                instrument="EUR_USD",
                fvg_type="bullish",
                top=Decimal("1.1060"),
                bottom=Decimal("1.1040"),
                midpoint=Decimal("1.1050"),
                sweep_id=sweep_id,
            )
            signal_id = await append_signal(
                connection,
                ts=ts,
                instrument="EUR_USD",
                direction="long",
                entry=Decimal("1.1050"),
                stop=Decimal("1.1020"),
                target=Decimal("1.1110"),
                risk=Decimal("0.0030"),
                rr=Decimal("2.0000"),
                status="pending",
            )
            trade_id = await append_trade(
                connection,
                signal_id=signal_id,
                broker_trade_id="broker-1",
                side="long",
                units=Decimal("1000"),
                entry_price=Decimal("1.1050"),
                entry_ts=ts,
            )
            snapshot_id = await append_equity_snapshot(
                connection,
                ts=ts,
                nav=Decimal("10000.00"),
                balance=Decimal("10000.00"),
                unrealized_pnl=Decimal("0.00"),
                open_positions=1,
            )

        async with engine.connect() as connection:
            assert await list_sweeps(connection, instrument="EUR_USD") == [
                {
                    "id": sweep_id,
                    "ts": ts,
                    "instrument": "EUR_USD",
                    "level_name": "asia_high",
                    "level_price": Decimal("1.10500000"),
                    "direction": "bullish",
                    "sweep_extreme": Decimal("1.10650000"),
                }
            ]
            assert await list_fvgs(connection, instrument="EUR_USD") == [
                {
                    "id": fvg_id,
                    "ts": ts,
                    "instrument": "EUR_USD",
                    "type": "bullish",
                    "top": Decimal("1.10600000"),
                    "bottom": Decimal("1.10400000"),
                    "midpoint": Decimal("1.10500000"),
                    "sweep_id": sweep_id,
                }
            ]
            assert await list_signals(connection, instrument="EUR_USD") == [
                {
                    "id": signal_id,
                    "ts": ts,
                    "instrument": "EUR_USD",
                    "direction": "long",
                    "entry": Decimal("1.10500000"),
                    "stop": Decimal("1.10200000"),
                    "target": Decimal("1.11100000"),
                    "risk": Decimal("0.00300000"),
                    "rr": Decimal("2.0000"),
                    "status": "pending",
                }
            ]
            assert await list_trades(connection, signal_id=signal_id) == [
                {
                    "id": trade_id,
                    "signal_id": signal_id,
                    "broker_trade_id": "broker-1",
                    "side": "long",
                    "units": Decimal("1000.0000"),
                    "entry_price": Decimal("1.10500000"),
                    "entry_ts": ts,
                    "exit_price": None,
                    "exit_ts": None,
                    "pnl": None,
                    "r_multiple": None,
                    "exit_reason": None,
                }
            ]
            assert await list_equity_snapshots(connection) == [
                {
                    "id": snapshot_id,
                    "ts": ts,
                    "nav": Decimal("10000.00000000"),
                    "balance": Decimal("10000.00000000"),
                    "unrealized_pnl": Decimal("0E-8"),
                    "open_positions": 1,
                }
            ]
    finally:
        await engine.dispose()


async def _assert_constraints(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    try:
        with pytest.raises(IntegrityError):
            async with transaction(engine) as connection:
                await append_signal(
                    connection,
                    ts=ts,
                    instrument="EUR_USD",
                    direction="long",
                    entry=Decimal("1.1050"),
                    stop=Decimal("1.1020"),
                    target=Decimal("1.1110"),
                    risk=Decimal("0.0030"),
                    rr=Decimal("2.0000"),
                    status="invalid",
                )

        with pytest.raises(IntegrityError):
            async with transaction(engine) as connection:
                await append_fvg(
                    connection,
                    ts=ts,
                    instrument="EUR_USD",
                    fvg_type="bullish",
                    top=Decimal("1.1060"),
                    bottom=Decimal("1.1040"),
                    midpoint=Decimal("1.1050"),
                    sweep_id=999_999,
                )
    finally:
        await engine.dispose()


async def _assert_related_fact_rollback(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    try:
        with pytest.raises(IntegrityError):
            async with transaction(engine) as connection:
                sweep_id = await append_sweep(
                    connection,
                    ts=ts,
                    instrument="EUR_USD",
                    level_name="asia_high",
                    level_price=Decimal("1.1050"),
                    direction="bullish",
                    sweep_extreme=Decimal("1.1065"),
                )
                await append_fvg(
                    connection,
                    ts=ts,
                    instrument="EUR_USD",
                    fvg_type="bullish",
                    top=Decimal("1.1060"),
                    bottom=Decimal("1.1040"),
                    midpoint=Decimal("1.1050"),
                    sweep_id=sweep_id,
                )
                await append_signal(
                    connection,
                    ts=ts,
                    instrument="EUR_USD",
                    direction="long",
                    entry=Decimal("1.1050"),
                    stop=Decimal("1.1020"),
                    target=Decimal("1.1110"),
                    risk=Decimal("0.0030"),
                    rr=Decimal("2.0000"),
                    status="invalid",
                )

        async with engine.connect() as connection:
            assert await connection.scalar(select(func.count()).select_from(sweeps)) == 0
            assert await connection.scalar(select(func.count()).select_from(fvgs)) == 0
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
