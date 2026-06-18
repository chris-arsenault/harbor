import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.observability.models import StatusSnapshot
from harbor_bot.observability.websocket import WebSocketHub


def test_websocket_endpoint_sends_initial_status_envelope() -> None:
    hub = WebSocketHub(clock=lambda: datetime(2026, 1, 15, 14, 32, tzinfo=UTC))
    client = TestClient(
        create_app(
            observability_service=FakeObservabilityService(),
            websocket_hub=hub,
        )
    )

    with client.websocket_connect("/ws") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "status"
    assert message["sent_at"] == "2026-01-15T14:32:00Z"
    assert message["payload"]["bot_state"] == "WAIT_SWEEP"
    assert message["payload"]["day_pnl"] == "60.00000000"
    assert hub.connection_count == 0


def test_websocket_hub_broadcasts_validated_json_envelopes_to_connections() -> None:
    hub = WebSocketHub(clock=lambda: datetime(2026, 1, 15, 14, 33, tzinfo=UTC))
    first = FakeWebSocket()
    second = FakeWebSocket()

    asyncio.run(_assert_broadcast(hub, first, second))


async def _assert_broadcast(
    hub: WebSocketHub,
    first: "FakeWebSocket",
    second: "FakeWebSocket",
) -> None:
    await hub.connect(first)
    await hub.connect(second)

    await hub.broadcast(hub.envelope("log", {"level": "info", "value": Decimal("1.25")}))
    hub.disconnect(first)
    await hub.broadcast(hub.envelope("status", {"bot_state": "IDLE"}))

    assert first.accepted is True
    assert second.accepted is True
    assert first.sent == [
        {
            "type": "log",
            "sent_at": "2026-01-15T14:33:00Z",
            "payload": {"level": "info", "value": "1.25"},
        }
    ]
    assert second.sent == [
        {
            "type": "log",
            "sent_at": "2026-01-15T14:33:00Z",
            "payload": {"level": "info", "value": "1.25"},
        },
        {
            "type": "status",
            "sent_at": "2026-01-15T14:33:00Z",
            "payload": {"bot_state": "IDLE"},
        },
    ]
    assert hub.connection_count == 1


class FakeObservabilityService:
    async def get_status(self) -> StatusSnapshot:
        return StatusSnapshot(
            bot_state="WAIT_SWEEP",
            session_phase="ny_trade",
            connection_health="unknown",
            mode="practice",
            trading_enabled=False,
            trading_controls_available=False,
            kill_switch_state="armed",
            day_pnl=Decimal("60.00000000"),
            trades_today=1,
            max_trades_per_day=2,
            account_nav=Decimal("10060.00000000"),
            open_positions=0,
            unrealized_pnl=Decimal("0E-8"),
            last_heartbeat=datetime(2026, 1, 15, 14, 31, tzinfo=UTC),
        )


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)
