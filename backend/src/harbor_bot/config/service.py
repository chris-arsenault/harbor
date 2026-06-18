from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.config.defaults import load_default_config
from harbor_bot.config.models import ConfigSnapshot, ConfigUpdateRequest, ConfigUpdateResult
from harbor_bot.persistence import config_repository, event_repository
from harbor_bot.persistence.database import transaction

DEFAULT_CONFIRMATION = "APPLY_CONFIG"


class ConfigService:
    def __init__(
        self,
        *,
        engine: AsyncEngine | None,
        defaults: Mapping[str, Mapping[str, Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
        confirmation: str = DEFAULT_CONFIRMATION,
    ) -> None:
        self._engine = engine
        self._defaults = {
            key: dict(value) for key, value in (defaults or load_default_config()).items()
        }
        self._clock = clock or (lambda: datetime.now(UTC))
        self._confirmation = confirmation

    async def get_snapshot(self) -> ConfigSnapshot:
        if self._engine is None:
            return self.snapshot_from_values([])
        async with self._engine.connect() as connection:
            values = await config_repository.list_config_values(connection)
        return self.snapshot_from_values(values)

    async def update_config(self, request: ConfigUpdateRequest) -> ConfigUpdateResult:
        if self._engine is None:
            msg = "config persistence is not configured"
            raise ValueError(msg)

        async with transaction(self._engine) as connection:
            current_values = await config_repository.list_config_values(connection)
            snapshot = self.snapshot_from_values(current_values)
            result = self.preview_update(snapshot, request, status="updated")
            for value in result.values:
                await config_repository.upsert_config_value(
                    connection,
                    key=str(value["key"]),
                    value=dict(value["value"]),
                )
            await event_repository.append_event(
                connection,
                ts=result.updated_ts,
                level="info",
                module="config",
                event_type="config.updated",
                message="configuration updated",
                data={"diff": [dict(item) for item in result.diff]},
            )
            return result

    def snapshot_from_values(self, values: list[Mapping[str, Any]]) -> ConfigSnapshot:
        stored = {str(item["key"]): dict(item["value"]) for item in values}
        merged = {}
        for key, default_value in sorted(self._defaults.items()):
            entry = dict(default_value)
            entry.update(stored.get(key, {}))
            merged[key] = entry
        for key, value in sorted(stored.items()):
            if key not in merged:
                merged[key] = value
        return ConfigSnapshot(
            values=tuple({"key": key, "value": value} for key, value in merged.items())
        )

    def preview_update(
        self,
        snapshot: ConfigSnapshot,
        request: ConfigUpdateRequest,
        *,
        status: str = "preview",
    ) -> ConfigUpdateResult:
        if request.confirmation != self._confirmation:
            msg = "config update confirmation is required"
            raise ValueError(msg)
        if not request.updates:
            msg = "config update must include at least one update"
            raise ValueError(msg)

        values_by_key = {str(item["key"]): dict(item["value"]) for item in snapshot.values}
        diff: list[dict[str, Any]] = []
        for key, update in request.updates.items():
            if key not in values_by_key:
                msg = f"unknown config key: {key}"
                raise ValueError(msg)
            before = values_by_key[key]
            after = _merge_config_entry(before, update)
            _validate_bounds(key, after)
            if after != before:
                diff.append({"key": key, "before": before, "after": after})
                values_by_key[key] = after

        values = tuple({"key": key, "value": values_by_key[key]} for key in sorted(values_by_key))
        return ConfigUpdateResult(
            status=status,
            updated_ts=self._clock(),
            values=values,
            diff=tuple(diff),
        )


def _merge_config_entry(
    before: Mapping[str, Any],
    update: Mapping[str, Any],
) -> dict[str, Any]:
    if "value" not in update:
        msg = "config update entries must include value"
        raise ValueError(msg)
    after = dict(before)
    after["value"] = update["value"]
    if "bounds" in update:
        after["bounds"] = dict(update["bounds"])
    return after


def _validate_bounds(key: str, entry: Mapping[str, Any]) -> None:
    bounds = entry.get("bounds")
    if not isinstance(bounds, Mapping):
        return
    value = entry.get("value")
    if isinstance(value, bool):
        return
    if not isinstance(value, int | float | Decimal):
        return
    lower = bounds.get("min")
    upper = bounds.get("max")
    if lower is None or upper is None:
        return
    decimal_value = Decimal(str(value))
    if decimal_value < Decimal(str(lower)) or decimal_value > Decimal(str(upper)):
        msg = f"{key} is outside configured bounds"
        raise ValueError(msg)
