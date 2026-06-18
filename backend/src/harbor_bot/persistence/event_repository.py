from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.persistence.schema import events


async def append_event(
    connection: AsyncConnection,
    *,
    ts: datetime,
    level: str,
    module: str,
    event_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> int:
    result = await connection.execute(
        events.insert()
        .values(
            ts=ts,
            level=level,
            module=module,
            type=event_type,
            message=message,
            data_json=data or {},
        )
        .returning(events.c.id)
    )
    return result.scalar_one()


async def append_daily_summary_event(
    connection: AsyncConnection,
    *,
    ts: datetime,
    summary: dict[str, Any],
) -> int:
    return await append_event(
        connection,
        ts=ts,
        level="info",
        module="daily",
        event_type="daily_summary",
        message="daily summary",
        data=summary,
    )


async def list_events(
    connection: AsyncConnection,
    *,
    level: str | None = None,
    module: str | None = None,
    event_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
    descending: bool = False,
) -> list[dict[str, Any]]:
    order = (desc(events.c.ts), desc(events.c.id)) if descending else (events.c.ts, events.c.id)
    statement = select(events).order_by(*order)
    if level is not None:
        statement = statement.where(events.c.level == level)
    if module is not None:
        statement = statement.where(events.c.module == module)
    if event_type is not None:
        statement = statement.where(events.c.type == event_type)
    if start is not None:
        statement = statement.where(events.c.ts >= start)
    if end is not None:
        statement = statement.where(events.c.ts < end)
    if limit is not None:
        statement = statement.limit(limit)

    result = await connection.execute(statement)
    return [dict(row) for row in result.mappings()]
