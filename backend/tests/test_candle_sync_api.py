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


def test_post_candles_sync_routes_through_service() -> None:
    service = FakeCandleSourceService()
    client = TestClient(create_app(candle_source_service=service))

    response = client.post("/api/candles/sync", json={"days": 90})

    assert response.status_code == 200
    assert response.json()["days"] == 90
    assert response.json()["reports"][0]["instrument"] == "EUR_USD"
    assert service.calls == [{"days": 90}]
