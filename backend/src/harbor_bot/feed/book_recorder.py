import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.oanda.client import OandaApiError, OandaClient
from harbor_bot.oanda.types import BookSnapshot
from harbor_bot.persistence.book_repository import (
    BOOK_TYPES,
    get_book_coverage,
    get_latest_book_snapshot,
    upsert_book_snapshot,
)
from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.event_repository import append_event
from harbor_bot.settings import Settings, redact_secret_text

MODULE = "feed.book_recorder"
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]
ClientFactory = Callable[[Settings], Any]
SnapshotWriter = Callable[[BookSnapshot, datetime], Awaitable[bool]]
EventWriter = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class BookRecorderReport:
    requested: int
    inserted: int
    skipped: int
    errors: tuple[dict[str, str], ...]


class BookRecorderStatusService:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        settings: Settings,
        recorder_status_provider: Callable[[], dict[str, Any]],
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._recorder_status_provider = recorder_status_provider

    async def get_status(self) -> dict[str, Any]:
        instruments = self._settings.research_instruments
        async with self._engine.connect() as connection:
            coverage = await get_book_coverage(connection, instruments=instruments)
            latest = {
                instrument: {
                    book_type: _latest_summary(
                        await get_latest_book_snapshot(
                            connection,
                            book_type=book_type,
                            instrument=instrument,
                        )
                    )
                    for book_type in BOOK_TYPES
                }
                for instrument in instruments
            }
        return {
            "recorder": self._recorder_status_provider(),
            "coverage": coverage,
            "latest": latest,
        }


async def record_books_once(
    *,
    client: Any,
    engine: AsyncEngine,
    instruments: Sequence[str],
    now: datetime,
    snapshot_writer: SnapshotWriter | None = None,
    event_writer: EventWriter | None = None,
) -> BookRecorderReport:
    recorded_ts = now.astimezone(UTC)
    write_snapshot = snapshot_writer or _db_snapshot_writer(engine)
    write_event = event_writer or _db_event_writer(engine)
    inserted = 0
    skipped = 0
    errors: list[dict[str, str]] = []

    for instrument in instruments:
        for book_type, fetch in (
            ("order", client.get_order_book),
            ("position", client.get_position_book),
        ):
            try:
                snapshot = await fetch(instrument=instrument)
                if await write_snapshot(snapshot, recorded_ts):
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:  # pragma: no cover - specific behavior tested by report
                error = {
                    "book_type": book_type,
                    "instrument": instrument,
                    "message": redact_secret_text(exc),
                }
                errors.append(error)
                await write_event(
                    ts=recorded_ts,
                    level="error",
                    event_type="book_poll_failed",
                    message=f"{book_type} book poll failed for {instrument}",
                    data=error,
                )

    report = BookRecorderReport(
        requested=len(instruments) * len(BOOK_TYPES),
        inserted=inserted,
        skipped=skipped,
        errors=tuple(errors),
    )
    await write_event(
        ts=recorded_ts,
        level="info" if not errors else "warning",
        event_type="book_poll_completed",
        message="book recorder poll completed",
        data={
            "requested": report.requested,
            "inserted": report.inserted,
            "skipped": report.skipped,
            "error_count": len(report.errors),
        },
    )
    return report


async def run_book_recorder(
    *,
    settings: Settings,
    engine: AsyncEngine,
    interval_seconds: float,
    client_factory: ClientFactory = OandaClient.from_settings,
    sleep: Sleep = asyncio.sleep,
) -> None:
    backoff_seconds = settings.oanda_reconnect_initial_seconds
    while True:
        try:
            async with client_factory(settings) as client:
                await record_books_once(
                    client=client,
                    engine=engine,
                    instruments=settings.research_instruments,
                    now=datetime.now(UTC),
                )
            backoff_seconds = settings.oanda_reconnect_initial_seconds
            await sleep(interval_seconds)
        except asyncio.CancelledError:
            raise
        except OandaApiError as exc:
            await _append_runtime_error(engine, exc)
            await sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, settings.oanda_reconnect_max_seconds)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            await _append_runtime_error(engine, exc)
            await sleep(settings.oanda_reconnect_max_seconds)


def _latest_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "snapshot_time": row["snapshot_time"],
        "bucket_count": row["bucket_count"],
        "mid_price": row["mid_price"],
        "recorded_ts": row["recorded_ts"],
    }


def _db_snapshot_writer(engine: AsyncEngine) -> SnapshotWriter:
    async def write(snapshot: BookSnapshot, recorded_ts: datetime) -> bool:
        async with transaction(engine) as connection:
            return await upsert_book_snapshot(
                connection,
                snapshot=snapshot,
                recorded_ts=recorded_ts,
            )

    return write


def _db_event_writer(engine: AsyncEngine) -> EventWriter:
    async def write(
        *,
        ts: datetime,
        level: str,
        event_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        async with transaction(engine) as connection:
            await append_event(
                connection,
                ts=ts,
                level=level,
                module=MODULE,
                event_type=event_type,
                message=message,
                data=data,
            )

    return write


async def _append_runtime_error(engine: AsyncEngine, exc: Exception) -> None:
    async with transaction(engine) as connection:
        await append_event(
            connection,
            ts=datetime.now(UTC),
            level="error",
            module=MODULE,
            event_type="book_recorder_error",
            message="book recorder runtime error",
            data={"message": redact_secret_text(exc)},
        )
