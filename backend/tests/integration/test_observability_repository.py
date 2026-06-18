import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.decision_repository import (
    append_equity_snapshot,
    append_fvg,
    append_signal,
    append_sweep,
    append_trade,
)
from harbor_bot.persistence.event_repository import append_event
from harbor_bot.persistence.market_repository import upsert_candle, upsert_session_levels
from harbor_bot.persistence.observability_repository import (
    get_day_trade_summary,
    get_latest_equity_snapshot,
    get_session_levels_for_date,
    list_candles_for_range,
    list_events_for_dashboard,
    list_fvgs_for_date,
    list_signals_for_date,
    list_sweeps_for_date,
    list_trades_for_date,
)
from harbor_bot.settings import Settings


def test_observability_queries_return_persisted_dashboard_facts(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_dashboard_fact_queries(postgres_url))


async def _assert_dashboard_fact_queries(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    trading_date = date(2026, 1, 15)
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    later = datetime(2026, 1, 15, 14, 31, tzinfo=UTC)
    next_day = datetime(2026, 1, 16, 14, 30, tzinfo=UTC)
    try:
        async with transaction(engine) as connection:
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=ts,
                o=Decimal("1.1000"),
                h=Decimal("1.1050"),
                low=Decimal("1.0990"),
                c=Decimal("1.1040"),
                volume=100,
                complete=True,
            )
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=later,
                o=Decimal("1.1040"),
                h=Decimal("1.1060"),
                low=Decimal("1.1030"),
                c=Decimal("1.1055"),
                volume=125,
                complete=True,
            )
            await upsert_candle(
                connection,
                instrument="GBP_USD",
                ts=ts,
                o=Decimal("1.2000"),
                h=Decimal("1.2050"),
                low=Decimal("1.1990"),
                c=Decimal("1.2040"),
                volume=100,
                complete=True,
            )
            await upsert_session_levels(
                connection,
                date=trading_date,
                instrument="EUR_USD",
                asia_high=Decimal("1.1100"),
                asia_low=Decimal("1.1000"),
                london_high=Decimal("1.1150"),
                london_low=Decimal("1.1050"),
            )
            sweep_id = await append_sweep(
                connection,
                ts=ts,
                instrument="EUR_USD",
                level_name="asia_low",
                level_price=Decimal("1.1000"),
                direction="bullish",
                sweep_extreme=Decimal("1.0990"),
            )
            await append_sweep(
                connection,
                ts=next_day,
                instrument="EUR_USD",
                level_name="london_low",
                level_price=Decimal("1.1050"),
                direction="bullish",
                sweep_extreme=Decimal("1.1040"),
            )
            fvg_id = await append_fvg(
                connection,
                ts=later,
                instrument="EUR_USD",
                fvg_type="bullish",
                top=Decimal("1.1060"),
                bottom=Decimal("1.1040"),
                midpoint=Decimal("1.1050"),
                sweep_id=sweep_id,
            )
            signal_id = await append_signal(
                connection,
                ts=later,
                instrument="EUR_USD",
                direction="long",
                entry=Decimal("1.1050"),
                stop=Decimal("1.1020"),
                target=Decimal("1.1110"),
                risk=Decimal("0.0030"),
                rr=Decimal("2.0000"),
                status="filled",
            )
            trade_id = await append_trade(
                connection,
                signal_id=signal_id,
                broker_trade_id="broker-1",
                side="long",
                units=Decimal("1000"),
                entry_price=Decimal("1.1050"),
                entry_ts=later,
                exit_price=Decimal("1.1110"),
                exit_ts=later,
                pnl=Decimal("60.00"),
                r_multiple=Decimal("2.0000"),
                exit_reason="target",
            )
            await append_equity_snapshot(
                connection,
                ts=ts,
                nav=Decimal("10000.00"),
                balance=Decimal("10000.00"),
                unrealized_pnl=Decimal("0.00"),
                open_positions=0,
            )
            equity_id = await append_equity_snapshot(
                connection,
                ts=later,
                nav=Decimal("10060.00"),
                balance=Decimal("10060.00"),
                unrealized_pnl=Decimal("0.00"),
                open_positions=0,
            )
            await append_event(
                connection,
                ts=ts,
                level="info",
                module="strategy",
                event_type="sweep",
                message="sweep detected",
                data={"sweep_id": sweep_id},
            )
            event_id = await append_event(
                connection,
                ts=later,
                level="warn",
                module="feed",
                event_type="heartbeat.stale",
                message="heartbeat stale",
                data={"seconds": 31},
            )

        async with engine.connect() as connection:
            candles = await list_candles_for_range(
                connection,
                instrument="EUR_USD",
                start=ts,
                end=next_day,
            )
            levels = await get_session_levels_for_date(
                connection,
                date=trading_date,
                instrument="EUR_USD",
            )
            sweeps = await list_sweeps_for_date(
                connection,
                date=trading_date,
                instrument="EUR_USD",
            )
            fvgs = await list_fvgs_for_date(connection, date=trading_date, instrument="EUR_USD")
            signals = await list_signals_for_date(
                connection,
                date=trading_date,
                instrument="EUR_USD",
            )
            trades = await list_trades_for_date(
                connection,
                date=trading_date,
                instrument="EUR_USD",
            )
            events = await list_events_for_dashboard(connection, level="warn", limit=5)
            latest_equity = await get_latest_equity_snapshot(connection)
            summary = await get_day_trade_summary(
                connection,
                date=trading_date,
                instrument="EUR_USD",
            )

        assert [row["ts"] for row in candles] == [ts, later]
        assert levels is not None
        assert levels["asia_low"] == Decimal("1.10000000")
        assert [row["id"] for row in sweeps] == [sweep_id]
        assert [row["id"] for row in fvgs] == [fvg_id]
        assert [row["id"] for row in signals] == [signal_id]
        assert [row["id"] for row in trades] == [trade_id]
        assert events == [
            {
                "id": event_id,
                "ts": later,
                "level": "warn",
                "module": "feed",
                "type": "heartbeat.stale",
                "message": "heartbeat stale",
                "data_json": {"seconds": 31},
            }
        ]
        assert latest_equity is not None
        assert latest_equity["id"] == equity_id
        assert latest_equity["nav"] == Decimal("10060.00000000")
        assert summary == {"realized_pnl": Decimal("60.00000000"), "trade_count": 1}
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
