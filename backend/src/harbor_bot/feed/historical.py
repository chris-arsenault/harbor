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
    request_count = page_size if count is None else min(count, page_size)
    candles = await client.get_historical_candles(
        instrument=instrument,
        from_time=from_time,
        count=request_count,
        include_first=include_first,
    )

    persisted = 0
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
    return persisted
