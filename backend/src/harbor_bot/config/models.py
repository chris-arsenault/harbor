from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class ConfigUpdateRequest:
    updates: Mapping[str, Mapping[str, Any]]
    confirmation: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "updates",
            {key: dict(value) for key, value in self.updates.items()},
        )


@dataclass(frozen=True)
class ConfigSnapshot:
    values: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(dict(value) for value in self.values))

    def to_jsonable(self) -> dict[str, JsonValue]:
        return {"values": [_json_safe(value) for value in self.values]}


@dataclass(frozen=True)
class ConfigUpdateResult:
    status: str
    updated_ts: datetime
    values: tuple[Mapping[str, Any], ...]
    diff: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(dict(value) for value in self.values))
        object.__setattr__(self, "diff", tuple(dict(value) for value in self.diff))

    def to_jsonable(self) -> dict[str, JsonValue]:
        return {
            "status": self.status,
            "updated_ts": self.updated_ts.isoformat(),
            "diff": [_json_safe(value) for value in self.diff],
            "values": [_json_safe(value) for value in self.values],
        }


def _json_safe(value: Any) -> JsonValue:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_safe(item) for item in value]
    return value
