import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.feed.live import ingest_pricing_stream
from harbor_bot.oanda.types import PriceBucket, PriceFrame, PricingHeartbeat
from harbor_bot.persistence.database import create_engine
from harbor_bot.persistence.event_repository import list_events
from harbor_bot.persistence.market_repository import list_candles
from harbor_bot.settings import Settings


def test_pricing_stream_ingestion_persists_only_closed_m1_candles(
    postgres_url: str,
) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_pricing_stream_ingestion(postgres_url))


async def _assert_pricing_stream_ingestion(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        persisted = await ingest_pricing_stream(
            engine=engine,
            instrument="EUR_USD",
            frames=_frames(),
            heartbeat_timeout_seconds=20.0,
            reconnect_attempts=[{"attempt": 1, "delay_seconds": 1.0}],
            event_ts=datetime(2026, 1, 15, 14, 29, 59, tzinfo=UTC),
        )

        async with engine.connect() as connection:
            candles = await list_candles(connection, instrument="EUR_USD")
            events = await list_events(connection)

        assert persisted == 1
        assert candles == [
            {
                "instrument": "EUR_USD",
                "ts": datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
                "o": Decimal("1.09015000"),
                "h": Decimal("1.09060000"),
                "l": Decimal("1.09015000"),
                "c": Decimal("1.09060000"),
                "volume": 2,
                "complete": True,
                "bid_h": None,
                "bid_l": None,
                "ask_h": None,
                "ask_l": None,
            }
        ]
        assert [event["type"] for event in events] == [
            "pricing_stream.connected",
            "pricing_stream.reconnect_attempt",
            "pricing_stream.heartbeat_timeout",
        ]
        assert events[0]["data_json"] == {"instruments": ["EUR_USD"]}
        assert events[1]["data_json"] == {
            "instruments": ["EUR_USD"],
            "attempt": 1,
            "delay_seconds": 1.0,
        }
        assert events[2]["data_json"] == {
            "instruments": ["EUR_USD"],
            "last_heartbeat": "2026-01-15T14:30:00+00:00",
        }
    finally:
        await engine.dispose()


async def _frames() -> AsyncIterator[PriceFrame | PricingHeartbeat]:
    yield PricingHeartbeat(time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC))
    yield _price("2026-01-15T14:30:05+00:00", "1.09010", "1.09020")
    yield _price("2026-01-15T14:30:45+00:00", "1.09050", "1.09070")
    yield _price("2026-01-15T14:31:00+00:00", "1.09030", "1.09040")


def _price(time: str, bid: str, ask: str) -> PriceFrame:
    return PriceFrame(
        time=datetime.fromisoformat(time),
        instrument="EUR_USD",
        bids=(PriceBucket(price=Decimal(bid), liquidity=1_000_000),),
        asks=(PriceBucket(price=Decimal(ask), liquidity=1_000_000),),
        closeout_bid=None,
        closeout_ask=None,
        tradeable=True,
        status="tradeable",
    )


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
