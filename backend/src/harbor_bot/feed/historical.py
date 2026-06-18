from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.market_repository import upsert_candle


async def ingest_historical_candles(
    *,
    client: Any,
    engine: AsyncEngine,
    instrument: str,
    from_time: datetime | None = None,
    count: int | None = None,
    page_size: int = 5000,
    include_first: bool = True,
) -> int:
    remaining = page_size if count is None else count
    cursor = from_time
    next_include_first = include_first
    persisted = 0
    while remaining > 0:
        request_count = min(remaining, page_size)
        candles = await client.get_historical_candles(
            instrument=instrument,
            from_time=cursor,
            count=request_count,
            include_first=next_include_first,
        )
        if not candles:
            break

        async with transaction(engine) as connection:
            for candle in candles:
                if not candle.complete:
                    continue
                await upsert_candle(
                    connection,
                    instrument=candle.instrument,
                    ts=candle.time,
                    o=candle.o,
                    h=candle.h,
                    low=candle.low,
                    c=candle.c,
                    volume=candle.volume,
                    complete=True,
                )
                persisted += 1

        remaining -= len(candles)
        newest = max(candle.time for candle in candles)
        if cursor is not None and newest <= cursor:
            break
        cursor = newest
        next_include_first = False
    return persisted
