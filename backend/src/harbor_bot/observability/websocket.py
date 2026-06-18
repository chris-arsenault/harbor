from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.observability.models import WebSocketEnvelope


class WebSocketHub:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._connections: set[Any] = set()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: Any) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: Any) -> None:
        self._connections.discard(websocket)

    def envelope(self, event_type: str, payload: Any) -> WebSocketEnvelope:
        return WebSocketEnvelope(
            type=event_type,
            sent_at=self._clock().astimezone(UTC),
            payload=_jsonable(payload),
        )

    async def send(self, websocket: Any, envelope: WebSocketEnvelope) -> None:
        await websocket.send_json(envelope.to_jsonable())

    async def broadcast(self, envelope: WebSocketEnvelope) -> None:
        disconnected: list[Any] = []
        for websocket in tuple(self._connections):
            try:
                await self.send(websocket, envelope)
            except RuntimeError:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_jsonable"):
        return value.to_jsonable()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    return value
