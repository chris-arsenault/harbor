from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.persistence.schema import config


async def seed_default_config(
    connection: AsyncConnection,
    defaults: dict[str, dict[str, Any]],
) -> int:
    if not defaults:
        return 0

    rows = [{"key": key, "value_json": value} for key, value in defaults.items()]
    statement = insert(config).values(rows).on_conflict_do_nothing(index_elements=[config.c.key])
    result = await connection.execute(statement)
    return result.rowcount or 0


async def get_config_value(connection: AsyncConnection, key: str) -> dict[str, Any] | None:
    result = await connection.execute(select(config.c.value_json).where(config.c.key == key))
    value = result.scalar_one_or_none()
    if value is None:
        return None
    return dict(value)


async def upsert_config_value(
    connection: AsyncConnection,
    *,
    key: str,
    value: dict[str, Any],
) -> None:
    statement = (
        insert(config)
        .values(key=key, value_json=value)
        .on_conflict_do_update(
            index_elements=[config.c.key],
            set_={"value_json": value},
        )
    )
    await connection.execute(statement)


async def list_config_values(connection: AsyncConnection) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(config.c.key, config.c.value_json, config.c.updated_ts).order_by(config.c.key)
    )
    return [
        {
            "key": row["key"],
            "value": dict(row["value_json"]),
            "updated_ts": row["updated_ts"],
        }
        for row in result.mappings()
    ]
