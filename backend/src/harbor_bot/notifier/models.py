from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

Jsonable = str | int | bool | None | list["Jsonable"] | dict[str, "Jsonable"]


@dataclass(frozen=True)
class NotificationConfig:
    ntfy_enabled: bool = False
    ntfy_base_url: str = "http://ntfy:80"
    ntfy_topic: str = "harbor"
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


@dataclass(frozen=True)
class NotificationEvent:
    event_type: str
    title: str
    message: str
    ts: datetime
    severity: str = "info"
    data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ts", _utc(self.ts))
        object.__setattr__(self, "data", dict(self.data or {}))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "data": _json_safe(self.data),
            "event_type": self.event_type,
            "message": self.message,
            "severity": self.severity,
            "title": self.title,
            "ts": self.ts.isoformat(),
        }


@dataclass(frozen=True)
class NotificationResult:
    sent: bool
    channels: tuple[str, ...]
    skipped_reason: str | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "notification datetimes must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _json_safe(value: Any) -> Jsonable:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | bool):
        return value
    return str(value)
