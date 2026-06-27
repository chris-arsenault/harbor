from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from harbor_bot.feed.book_recorder import record_books_once
from harbor_bot.oanda.types import BookBucket, BookSnapshot

NOW = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_book_recorder_inserts_then_skips_duplicate_snapshots() -> None:
    seen: set[tuple[str, str, datetime]] = set()
    events: list[dict[str, Any]] = []

    async def writer(snapshot: BookSnapshot, recorded_ts: datetime) -> bool:
        key = (snapshot.book_type, snapshot.instrument, snapshot.time)
        inserted = key not in seen
        seen.add(key)
        assert recorded_ts == NOW
        return inserted

    client = FakeBookClient()

    first = await record_books_once(
        client=client,
        engine=object(),  # type: ignore[arg-type]
        instruments=("EUR_USD",),
        now=NOW,
        snapshot_writer=writer,
        event_writer=_event_writer(events),
    )
    second = await record_books_once(
        client=client,
        engine=object(),  # type: ignore[arg-type]
        instruments=("EUR_USD",),
        now=NOW,
        snapshot_writer=writer,
        event_writer=_event_writer(events),
    )

    assert first.inserted == 2
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 2
    assert events[-1]["event_type"] == "book_poll_completed"


@pytest.mark.asyncio
async def test_book_recorder_continues_after_one_instrument_failure() -> None:
    inserted: list[tuple[str, str]] = []
    events: list[dict[str, Any]] = []

    async def writer(snapshot: BookSnapshot, recorded_ts: datetime) -> bool:
        inserted.append((snapshot.book_type, snapshot.instrument))
        return True

    report = await record_books_once(
        client=FakeBookClient(fail_order_for={"GBP_USD"}),
        engine=object(),  # type: ignore[arg-type]
        instruments=("GBP_USD", "EUR_USD"),
        now=NOW,
        snapshot_writer=writer,
        event_writer=_event_writer(events),
    )

    assert report.requested == 4
    assert report.inserted == 3
    assert report.errors == (
        {
            "book_type": "order",
            "instrument": "GBP_USD",
            "message": "order unavailable for GBP_USD",
        },
    )
    assert ("position", "GBP_USD") in inserted
    assert ("order", "EUR_USD") in inserted
    assert any(event["event_type"] == "book_poll_failed" for event in events)


class FakeBookClient:
    def __init__(self, *, fail_order_for: set[str] | None = None) -> None:
        self._fail_order_for = fail_order_for or set()

    async def get_order_book(self, *, instrument: str) -> BookSnapshot:
        if instrument in self._fail_order_for:
            raise RuntimeError(f"order unavailable for {instrument}")
        return _snapshot("order", instrument)

    async def get_position_book(self, *, instrument: str) -> BookSnapshot:
        return _snapshot("position", instrument)


def _snapshot(book_type: str, instrument: str) -> BookSnapshot:
    return BookSnapshot(
        book_type=book_type,
        instrument=instrument,
        time=datetime(2026, 1, 15, 14, 40, tzinfo=UTC),
        price=Decimal("1.09000"),
        bucket_width=Decimal("0.00050"),
        buckets=(
            BookBucket(
                price=Decimal("1.08500"),
                long_percent=Decimal("0.20"),
                short_percent=Decimal("0.15"),
            ),
        ),
    )


def _event_writer(events: list[dict[str, Any]]):
    async def write(**kwargs: Any) -> None:
        events.append(kwargs)

    return write
