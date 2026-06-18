import asyncio
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.event_repository import (
    append_daily_summary_event,
    append_event,
    list_events,
)
from harbor_bot.settings import Settings


def test_events_append_and_read_structured_payloads(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_event_append_and_read(postgres_url))


async def _assert_event_append_and_read(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    summary_ts = datetime(2026, 1, 15, 23, 59, tzinfo=UTC)
    try:
        async with transaction(engine) as connection:
            event_id = await append_event(
                connection,
                ts=ts,
                level="info",
                module="strategy",
                event_type="signal.created",
                message="created pending signal",
                data={"signal_id": 10, "instrument": "EUR_USD"},
            )
            summary_id = await append_daily_summary_event(
                connection,
                ts=summary_ts,
                summary={"trades_today": 1, "day_pnl": "18.00000000"},
            )

        async with engine.connect() as connection:
            events = await list_events(connection)
            assert events == [
                {
                    "id": event_id,
                    "ts": ts,
                    "level": "info",
                    "module": "strategy",
                    "type": "signal.created",
                    "message": "created pending signal",
                    "data_json": {"signal_id": 10, "instrument": "EUR_USD"},
                },
                {
                    "id": summary_id,
                    "ts": summary_ts,
                    "level": "info",
                    "module": "daily",
                    "type": "daily_summary",
                    "message": "daily summary",
                    "data_json": {"trades_today": 1, "day_pnl": "18.00000000"},
                },
            ]
            assert await list_events(
                connection,
                level="info",
                module="daily",
                event_type="daily_summary",
                start=datetime(2026, 1, 15, tzinfo=UTC),
                end=datetime(2026, 1, 16, tzinfo=UTC),
                limit=10,
            ) == [
                events[1],
            ]
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
