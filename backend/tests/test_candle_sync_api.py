from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app


class FakeCandleSourceService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            "status": "completed",
            "days": int(payload.get("days", 180)),
            "reports": [
                {
                    "instrument": "EUR_USD",
                    "imported": 3,
                    "candle_count": 3,
                    "from": None,
                    "to": None,
                }
            ],
        }

    async def get_backfill_status(self) -> dict[str, Any]:
        return {
            "status": "idle",
            "job_id": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "current_instrument": None,
            "imported_count": 0,
            "completed_ranges": 0,
            "total_ranges": 0,
            "historical": {
                "start": None,
                "end": None,
                "expected_days": 0,
                "loaded_days": 0,
                "missing_days": 0,
                "filled_days": 0,
                "pending_days": 0,
            },
            "recent": {"pending_ranges": 0, "completed_ranges": 0},
            "instruments": [],
        }

    async def start_backfill(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {
            **(await self.get_backfill_status()),
            "status": "running",
            "job_id": "job-1",
            "total_ranges": 3,
        }


def test_post_candles_sync_routes_through_service() -> None:
    service = FakeCandleSourceService()
    client = TestClient(create_app(candle_source_service=service))

    response = client.post("/api/candles/sync", json={"days": 90})

    assert response.status_code == 200
    assert response.json()["days"] == 90
    assert response.json()["reports"][0]["instrument"] == "EUR_USD"
    assert service.calls == [{"days": 90}]


def test_candles_backfill_routes_through_service() -> None:
    service = FakeCandleSourceService()
    client = TestClient(create_app(candle_source_service=service))

    status = client.get("/api/candles/backfill")
    started = client.post("/api/candles/backfill", json={})

    assert status.status_code == 200
    assert status.json()["status"] == "idle"
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert started.json()["job_id"] == "job-1"
    assert service.calls == [{}]
