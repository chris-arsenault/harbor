import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.feed.historical import ingest_historical_candles
from harbor_bot.oanda.types import HistoricalCandle
from harbor_bot.persistence.database import create_engine
from harbor_bot.persistence.market_repository import list_candles
from harbor_bot.settings import Settings


def test_historical_ingestion_persists_only_complete_m1_candles(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_historical_ingestion(postgres_url))


async def _assert_historical_ingestion(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    client = _FakeHistoricalClient()
    from_time = datetime(2026, 1, 15, 14, 29, tzinfo=UTC)
    try:
        persisted = await ingest_historical_candles(
            client=client,
            engine=engine,
            instrument="EUR_USD",
            from_time=from_time,
            count=3,
            page_size=2,
            include_first=False,
        )

        async with engine.connect() as connection:
            candles = await list_candles(connection, instrument="EUR_USD")

        assert persisted == 3
        assert client.calls == [
            {
                "instrument": "EUR_USD",
                "from_time": from_time,
                "count": 2,
                "include_first": False,
            },
            {
                "instrument": "EUR_USD",
                "from_time": datetime(2026, 1, 15, 14, 31, tzinfo=UTC),
                "count": 1,
                "include_first": False,
            },
        ]
        assert candles == [
            {
                "instrument": "EUR_USD",
                "ts": datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
                "o": Decimal("1.09000000"),
                "h": Decimal("1.09100000"),
                "l": Decimal("1.08950000"),
                "c": Decimal("1.09050000"),
                "volume": 128,
                "complete": True,
            },
            {
                "instrument": "EUR_USD",
                "ts": datetime(2026, 1, 15, 14, 31, tzinfo=UTC),
                "o": Decimal("1.09050000"),
                "h": Decimal("1.09150000"),
                "l": Decimal("1.09000000"),
                "c": Decimal("1.09100000"),
                "volume": 130,
                "complete": True,
            },
            {
                "instrument": "EUR_USD",
                "ts": datetime(2026, 1, 15, 14, 32, tzinfo=UTC),
                "o": Decimal("1.09100000"),
                "h": Decimal("1.09200000"),
                "l": Decimal("1.09050000"),
                "c": Decimal("1.09150000"),
                "volume": 132,
                "complete": True,
            },
        ]
    finally:
        await engine.dispose()


class _FakeHistoricalClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def get_historical_candles(
        self,
        *,
        instrument: str,
        from_time: datetime | None,
        count: int,
        include_first: bool,
    ) -> list[HistoricalCandle]:
        self.calls.append(
            {
                "instrument": instrument,
                "from_time": from_time,
                "count": count,
                "include_first": include_first,
            }
        )
        candles = [
            HistoricalCandle(
                instrument=instrument,
                time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
                o=Decimal("1.09000"),
                h=Decimal("1.09100"),
                low=Decimal("1.08950"),
                c=Decimal("1.09050"),
                volume=128,
                complete=True,
            ),
            HistoricalCandle(
                instrument=instrument,
                time=datetime(2026, 1, 15, 14, 31, tzinfo=UTC),
                o=Decimal("1.09050"),
                h=Decimal("1.09150"),
                low=Decimal("1.09000"),
                c=Decimal("1.09100"),
                volume=130,
                complete=True,
            ),
            HistoricalCandle(
                instrument=instrument,
                time=datetime(2026, 1, 15, 14, 32, tzinfo=UTC),
                o=Decimal("1.09100"),
                h=Decimal("1.09200"),
                low=Decimal("1.09050"),
                c=Decimal("1.09150"),
                volume=132,
                complete=True,
            ),
            HistoricalCandle(
                instrument=instrument,
                time=datetime(2026, 1, 15, 14, 33, tzinfo=UTC),
                o=Decimal("1.09150"),
                h=Decimal("1.09180"),
                low=Decimal("1.09140"),
                c=Decimal("1.09170"),
                volume=13,
                complete=False,
            ),
        ]
        if from_time is None:
            return candles[:count]
        return [candle for candle in candles if candle.time > from_time][:count]


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
