from datetime import UTC, datetime

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.observability.models import EventLogItem


def test_events_route_forwards_full_filter_set_and_returns_structured_events() -> None:
    service = FakeEventsService()
    client = TestClient(create_app(observability_service=service))

    response = client.get(
        "/api/events?"
        "level=info&module=daily&type=daily_summary&"
        "from=2026-01-15T00:00:00Z&to=2026-01-16T00:00:00Z&limit=50"
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 21,
            "ts": "2026-01-15T23:59:00Z",
            "level": "info",
            "module": "daily",
            "type": "daily_summary",
            "message": "daily summary",
            "data": {"trades_today": 2, "day_pnl": "42.00000000"},
        }
    ]
    assert service.requests == [
        {
            "level": "info",
            "module": "daily",
            "event_type": "daily_summary",
            "start": datetime(2026, 1, 15, tzinfo=UTC),
            "end": datetime(2026, 1, 16, tzinfo=UTC),
            "limit": 50,
        }
    ]


class FakeEventsService:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def get_events(
        self,
        *,
        level: str | None,
        module: str | None,
        event_type: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[EventLogItem, ...]:
        self.requests.append(
            {
                "level": level,
                "module": module,
                "event_type": event_type,
                "start": start,
                "end": end,
                "limit": limit,
            }
        )
        return (
            EventLogItem(
                id=21,
                ts=datetime(2026, 1, 15, 23, 59, tzinfo=UTC),
                level="info",
                module="daily",
                type="daily_summary",
                message="daily summary",
                data={"trades_today": 2, "day_pnl": "42.00000000"},
            ),
        )
