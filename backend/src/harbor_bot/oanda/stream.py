import json
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from harbor_bot.oanda.types import (
    PricingFrame,
    PricingHeartbeat,
    TransactionHeartbeat,
    TransactionStreamFrame,
    parse_pricing_frame,
    parse_transaction_frame,
)


class OandaStreamParseError(ValueError):
    pass


@dataclass
class HeartbeatMonitor:
    timeout_seconds: float
    last_heartbeat: datetime | None = None

    def record(self, frame: PricingFrame | TransactionStreamFrame) -> None:
        if isinstance(frame, PricingHeartbeat | TransactionHeartbeat):
            self.last_heartbeat = frame.time

    def is_stale(self, now: datetime) -> bool:
        if self.last_heartbeat is None:
            return True
        return now - self.last_heartbeat > timedelta(seconds=self.timeout_seconds)


async def parse_pricing_stream_lines(
    lines: AsyncIterable[str | bytes],
) -> AsyncIterator[PricingFrame]:
    async for payload in _parse_json_lines(lines):
        yield parse_pricing_frame(payload)


async def parse_transaction_stream_lines(
    lines: AsyncIterable[str | bytes],
) -> AsyncIterator[TransactionStreamFrame]:
    async for payload in _parse_json_lines(lines):
        yield parse_transaction_frame(payload)


async def reconnecting_frames[T](
    connect: Callable[[], AsyncIterable[T]],
    *,
    initial_delay_seconds: float,
    max_delay_seconds: float,
    sleep: Callable[[float], Awaitable[None]],
    retry_exceptions: tuple[type[Exception], ...] = (OSError,),
) -> AsyncIterator[T]:
    delay = initial_delay_seconds
    while True:
        try:
            async for frame in connect():
                yield frame
            return
        except retry_exceptions:
            await sleep(delay)
            delay = min(delay * 2, max_delay_seconds)


async def _parse_json_lines(lines: AsyncIterable[str | bytes]) -> AsyncIterator[dict]:
    async for raw_line in lines:
        line = _decode_line(raw_line).strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            msg = "malformed OANDA stream JSON"
            raise OandaStreamParseError(msg) from exc
        if not isinstance(payload, dict):
            msg = "OANDA stream JSON line must be an object"
            raise OandaStreamParseError(msg)
        yield payload


def _decode_line(raw_line: str | bytes) -> str:
    if isinstance(raw_line, bytes):
        return raw_line.decode()
    return raw_line
