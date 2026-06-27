import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.market_repository import upsert_candle

Sleeper = Callable[[float], Awaitable[None]]


async def ingest_historical_candles(
    *,
    client: Any,
    engine: AsyncEngine,
    instrument: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    count: int | None = None,
    page_size: int = 5000,
    include_first: bool = True,
    request_interval_seconds: float = 0.1,
    sleeper: Sleeper = asyncio.sleep,
    replace_existing: bool = True,
) -> int:
    if request_interval_seconds < 0:
        msg = "request_interval_seconds must be non-negative"
        raise ValueError(msg)
    if to_time is not None:
        if from_time is None:
            msg = "from_time is required when to_time is provided"
            raise ValueError(msg)
        return await _ingest_bounded_historical_candles(
            client=client,
            engine=engine,
            instrument=instrument,
            from_time=from_time,
            to_time=to_time,
            page_size=page_size,
            include_first=include_first,
            request_interval_seconds=request_interval_seconds,
            sleeper=sleeper,
            replace_existing=replace_existing,
        )
    remaining = page_size if count is None else count
    cursor = from_time
    next_include_first = include_first
    persisted = 0
    page_index = 0
    while remaining > 0:
        if page_index > 0 and request_interval_seconds > 0:
            await sleeper(request_interval_seconds)
        request_count = min(remaining, page_size)
        candles = await client.get_historical_candles(
            instrument=instrument,
            from_time=cursor,
            count=request_count,
            include_first=next_include_first,
        )
        page_index += 1
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
                    bid_h=candle.bid_h,
                    bid_l=candle.bid_low,
                    ask_h=candle.ask_h,
                    ask_l=candle.ask_low,
                    replace_existing=replace_existing,
                )
                persisted += 1

        remaining -= len(candles)
        newest = max(candle.time for candle in candles)
        if cursor is not None and newest <= cursor:
            break
        cursor = newest
        next_include_first = False
    return persisted


async def _ingest_bounded_historical_candles(
    *,
    client: Any,
    engine: AsyncEngine,
    instrument: str,
    from_time: datetime,
    to_time: datetime,
    page_size: int,
    include_first: bool,
    request_interval_seconds: float,
    sleeper: Sleeper,
    replace_existing: bool,
) -> int:
    if to_time <= from_time:
        return 0
    cursor = from_time
    next_include_first = include_first
    persisted = 0
    page_index = 0
    while cursor < to_time:
        if page_index > 0 and request_interval_seconds > 0:
            await sleeper(request_interval_seconds)
        page_to = min(cursor + timedelta(minutes=page_size), to_time)
        candles = await client.get_historical_candles(
            instrument=instrument,
            from_time=cursor,
            to_time=page_to,
            include_first=next_include_first,
        )
        page_index += 1

        async with transaction(engine) as connection:
            for candle in candles:
                if not candle.complete or candle.time >= to_time:
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
                    bid_h=candle.bid_h,
                    bid_l=candle.bid_low,
                    ask_h=candle.ask_h,
                    ask_l=candle.ask_low,
                    replace_existing=replace_existing,
                )
                persisted += 1

        cursor = page_to
        next_include_first = False
    return persisted
