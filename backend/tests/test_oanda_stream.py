import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harbor_bot.oanda.stream import (
    HeartbeatMonitor,
    OandaStreamParseError,
    parse_pricing_stream_lines,
    parse_transaction_stream_lines,
    reconnecting_frames,
)
from harbor_bot.oanda.types import PriceFrame, PricingHeartbeat, TransactionFrame

FIXTURES = Path(__file__).parent / "fixtures" / "oanda"


@pytest.mark.asyncio
async def test_pricing_stream_parser_skips_blank_lines_and_decodes_bytes() -> None:
    lines = [
        b"",
        _fixture_line("pricing_heartbeat.json").encode(),
        "   ",
        _fixture_line("pricing_price.json"),
    ]

    frames = [frame async for frame in parse_pricing_stream_lines(_aiter(lines))]

    assert isinstance(frames[0], PricingHeartbeat)
    assert isinstance(frames[1], PriceFrame)
    assert frames[1].instrument == "EUR_USD"


@pytest.mark.asyncio
async def test_transaction_stream_parser_preserves_transaction_frames() -> None:
    lines = [
        _fixture_line("transaction_heartbeat.json"),
        _fixture_line("transaction_order_fill.json"),
    ]

    frames = [frame async for frame in parse_transaction_stream_lines(_aiter(lines))]

    assert frames[0].last_transaction_id == "9011"
    assert isinstance(frames[1], TransactionFrame)
    assert frames[1].raw["type"] == "ORDER_FILL"


@pytest.mark.asyncio
async def test_stream_parser_surfaces_malformed_json() -> None:
    with pytest.raises(OandaStreamParseError, match="malformed OANDA stream JSON"):
        _ = [frame async for frame in parse_pricing_stream_lines(_aiter(["{not-json}"]))]


def test_heartbeat_monitor_tracks_freshness() -> None:
    monitor = HeartbeatMonitor(timeout_seconds=20.0)
    heartbeat = PricingHeartbeat(time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC))

    assert monitor.last_heartbeat is None
    monitor.record(heartbeat)

    assert monitor.last_heartbeat == heartbeat.time
    assert monitor.is_stale(heartbeat.time + timedelta(seconds=19)) is False
    assert monitor.is_stale(heartbeat.time + timedelta(seconds=21)) is True


@pytest.mark.asyncio
async def test_reconnecting_frames_uses_injected_exponential_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    def connect() -> AsyncIterator[str]:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise OSError("stream dropped")
        return _aiter(["connected"])

    async def sleep(delay: float) -> None:
        delays.append(delay)

    frames = [
        frame
        async for frame in reconnecting_frames(
            connect,
            initial_delay_seconds=1.0,
            max_delay_seconds=2.0,
            sleep=sleep,
        )
    ]

    assert frames == ["connected"]
    assert delays == [1.0, 2.0, 2.0]


async def _aiter(values) -> AsyncIterator:
    for value in values:
        yield value


def _fixture_line(name: str) -> str:
    return json.dumps(json.loads((FIXTURES / name).read_text()))
