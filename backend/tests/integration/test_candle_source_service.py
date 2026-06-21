import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.feed.source_service import CandleSourceService
from harbor_bot.oanda.types import HistoricalCandle
from harbor_bot.persistence.database import create_engine
from harbor_bot.settings import Settings


def test_candle_source_service_reports_coverage_and_imports_historical_candles(
    postgres_url: str,
) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_candle_source_service(postgres_url))


async def _assert_candle_source_service(postgres_url: str) -> None:
    settings = Settings(
        DATABASE_URL=postgres_url,
        OANDA_API_TOKEN="token",
        OANDA_ACCOUNT_ID="account",
    )
    engine = create_engine(settings)
    service = CandleSourceService(
        engine=engine,
        settings=settings,
        client_factory=lambda _: _FakeHistoricalClient(),
    )
    try:
        empty = await service.get_status(instrument="EUR_USD")
        imported = await service.import_historical({"instrument": "EUR_USD", "count": 2})
        status = await service.get_status(instrument="EUR_USD")

        assert empty["coverage"]["candle_count"] == 0
        assert imported["imported_count"] == 2
        assert imported["coverage"]["candle_count"] == 2
        assert imported["from"] is None
        assert status["coverage"]["from"] == "2026-01-15T14:30:00+00:00"
        assert status["coverage"]["to"] == "2026-01-15T14:31:00+00:00"
        assert status["historical_import"] == {
            "page_size": 5000,
            "default_count": 259200,
            "request_interval_seconds": 0.1,
            "upsert_key": "instrument+timestamp",
            "replaces_existing": False,
        }
        assert status["oanda_historical_import_configured"] is True
    finally:
        await engine.dispose()

    resume_engine = create_engine(settings)
    resume_client = _FakeHistoricalClient()
    resume_service = CandleSourceService(
        engine=resume_engine,
        settings=settings,
        client_factory=lambda _: resume_client,
    )
    try:
        await resume_service.import_historical(
            {
                "instrument": "EUR_USD",
                "count": 2,
                "from": "2026-01-15T14:30:00+00:00",
            }
        )
        assert resume_client.include_first_values == [False]
    finally:
        await resume_engine.dispose()


class _FakeHistoricalClient:
    def __init__(self) -> None:
        self.include_first_values: list[bool] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def get_historical_candles(
        self,
        *,
        instrument: str,
        from_time: datetime | None,
        count: int,
        include_first: bool,
    ) -> list[HistoricalCandle]:
        assert instrument == "EUR_USD"
        assert count == 2
        self.include_first_values.append(include_first)
        if from_time is None:
            assert include_first is True
        else:
            assert from_time == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
            assert include_first is False
        return [
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
        ]


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
