import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.research.service import ResearchService

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


class FakeResearchService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def edge_study(self, *, instrument: str, horizon: int) -> dict[str, Any]:
        self.calls.append((instrument, horizon))
        return {"instrument": instrument, "horizon": horizon, "total_sweeps": 0, "has_edge": False}


def test_get_edge_study_routes_through_injected_service() -> None:
    service = FakeResearchService()
    client = TestClient(create_app(research_service=service))

    response = client.get("/api/research/edge", params={"instrument": "GBP_USD", "horizon": 5})

    assert response.status_code == 200
    assert response.json()["instrument"] == "GBP_USD"
    assert service.calls == [("GBP_USD", 5)]


def test_edge_study_runs_over_loaded_candles() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_fixed_window)

    result = asyncio.run(service.edge_study(instrument="EUR_USD", horizon=3))

    assert result["total_sweeps"] == 2
    assert result["overall"]["count"] == 1
    assert result["has_edge"] is False


def test_edge_study_with_no_window_returns_empty() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_no_window)

    result = asyncio.run(service.edge_study(instrument="EUR_USD"))

    assert result["total_candles"] == 0
    assert result["total_sweeps"] == 0


async def _fixture_records(
    engine: Any, *, instrument: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    return [
        {
            "instrument": instrument,
            "ts": candle.ts.isoformat(),
            "o": str(candle.o),
            "h": str(candle.h),
            "low": str(candle.low),
            "c": str(candle.c),
            "volume": candle.volume,
            "complete": candle.complete,
        }
        for candle in load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")
    ]


async def _fixed_window(engine: Any, *, instrument: str, required_days: int) -> dict[str, Any]:
    return {"from": datetime(2026, 1, 15, tzinfo=UTC), "to": datetime(2026, 1, 16, tzinfo=UTC)}


async def _no_window(engine: Any, *, instrument: str, required_days: int) -> None:
    return None
