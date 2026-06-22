from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.feed.candles import CandleBuilder, ClosedCandle
from harbor_bot.oanda.stream import HeartbeatMonitor
from harbor_bot.oanda.types import PriceFrame, PricingFrame
from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.event_repository import append_event
from harbor_bot.persistence.market_repository import upsert_candle


async def ingest_pricing_stream(
    *,
    engine: AsyncEngine,
    frames: AsyncIterable[PricingFrame],
    heartbeat_timeout_seconds: float,
    instrument: str | None = None,
    instruments: Sequence[str] | None = None,
    reconnect_attempts: Sequence[Mapping[str, Any]] = (),
    event_ts: datetime | None = None,
    on_closed_candle: Callable[[ClosedCandle], Awaitable[None]] | None = None,
) -> int:
    tracked_instruments = _tracked_instruments(instrument=instrument, instruments=instruments)
    event_ts = event_ts or datetime.now(UTC)
    await _append_lifecycle_event(
        engine,
        ts=event_ts,
        level="info",
        event_type="pricing_stream.connected",
        message="pricing stream connected",
        data={"instruments": list(tracked_instruments)},
    )
    for attempt in reconnect_attempts:
        await _append_lifecycle_event(
            engine,
            ts=event_ts,
            level="warning",
            event_type="pricing_stream.reconnect_attempt",
            message="pricing stream reconnect attempt",
            data={"instruments": list(tracked_instruments), **dict(attempt)},
        )

    builder = CandleBuilder()
    monitor = HeartbeatMonitor(timeout_seconds=heartbeat_timeout_seconds)
    timeout_logged = False
    persisted = 0

    async for frame in frames:
        if (
            isinstance(frame, PriceFrame)
            and monitor.last_heartbeat is not None
            and monitor.is_stale(frame.time)
            and not timeout_logged
        ):
            timeout_logged = True
            await _append_lifecycle_event(
                engine,
                ts=frame.time,
                level="warning",
                event_type="pricing_stream.heartbeat_timeout",
                message="pricing stream heartbeat timeout",
                data={
                    "instruments": list(tracked_instruments),
                    "last_heartbeat": monitor.last_heartbeat.isoformat(),
                },
            )

        monitor.record(frame)
        if isinstance(frame, PriceFrame) and frame.instrument not in tracked_instruments:
            continue

        closed = builder.add(frame)
        if closed is None:
            continue
        await _persist_closed_candle(engine, closed)
        if on_closed_candle is not None:
            await on_closed_candle(closed)
        persisted += 1

    return persisted


def _tracked_instruments(
    *,
    instrument: str | None,
    instruments: Sequence[str] | None,
) -> tuple[str, ...]:
    if instruments is not None:
        tracked = tuple(str(value).strip().upper() for value in instruments if value)
        if tracked:
            return tracked
    if instrument is None:
        msg = "instrument or instruments is required"
        raise ValueError(msg)
    return (instrument.strip().upper(),)


async def _persist_closed_candle(engine: AsyncEngine, candle: ClosedCandle) -> None:
    async with transaction(engine) as connection:
        await upsert_candle(
            connection,
            instrument=candle.instrument,
            ts=candle.ts,
            o=candle.o,
            h=candle.h,
            low=candle.low,
            c=candle.c,
            volume=candle.volume,
            complete=candle.complete,
        )


async def _append_lifecycle_event(
    engine: AsyncEngine,
    *,
    ts: datetime,
    level: str,
    event_type: str,
    message: str,
    data: dict[str, Any],
) -> None:
    async with transaction(engine) as connection:
        await append_event(
            connection,
            ts=ts,
            level=level,
            module="feed.live",
            event_type=event_type,
            message=message,
            data=data,
        )
