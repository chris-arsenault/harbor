from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app


class FakeBookRecorderStatusService:
    async def get_status(self) -> dict[str, Any]:
        return {
            "recorder": {
                "running": True,
                "state": "running",
                "last_started_at": "2026-01-15T15:00:00+00:00",
                "last_error": None,
            },
            "coverage": [
                {
                    "book_type": "order",
                    "instrument": "EUR_USD",
                    "snapshot_count": 12,
                    "from": "2026-01-15T14:20:00+00:00",
                    "to": "2026-01-15T14:40:00+00:00",
                    "latest_mid_price": "1.09000",
                }
            ],
            "latest": {
                "EUR_USD": {
                    "order": {
                        "snapshot_time": "2026-01-15T14:40:00+00:00",
                        "bucket_count": 401,
                    },
                    "position": None,
                }
            },
        }


def test_book_status_routes_through_injected_service() -> None:
    client = TestClient(
        create_app(book_recorder_status_service=FakeBookRecorderStatusService())  # type: ignore[arg-type]
    )

    response = client.get("/api/research/books/status")

    assert response.status_code == 200
    assert response.json()["recorder"]["state"] == "running"
    assert response.json()["coverage"][0]["book_type"] == "order"
    assert response.json()["latest"]["EUR_USD"]["order"]["bucket_count"] == 401
