"""Coverage-driven historical candle ingestion.

A real data-sourcing pipeline: rather than blindly re-fetching a fixed count,
compare a desired window against what is already persisted and fetch only the
missing head/tail ranges. Idempotent (upsert) and resumable — re-running only
sources gaps. Pulls OANDA bid/ask candles (ADR 0006) for the research universe.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.feed.historical import ingest_historical_candles
from harbor_bot.instruments import RESEARCH_INSTRUMENTS
from harbor_bot.oanda.client import OandaClient
from harbor_bot.persistence.market_repository import get_candle_coverage
from harbor_bot.settings import Settings

MIN_GAP = timedelta(minutes=2)

CoverageProvider = Callable[[str], Awaitable[dict]]
Ingestor = Callable[..., Awaitable[int]]
ClientFactory = Callable[[Settings], object]


@dataclass(frozen=True)
class FetchRange:
    from_time: datetime
    count: int
    include_first: bool


@dataclass(frozen=True)
class SyncReport:
    instrument: str
    imported: int
    candle_count: int
    coverage_from: datetime | None
    coverage_to: datetime | None


def _minutes(start: datetime, end: datetime) -> int:
    return max(1, int((end - start).total_seconds() // 60))


def gap_plan(
    *,
    coverage_from: datetime | None,
    coverage_to: datetime | None,
    candle_count: int,
    target_start: datetime,
    now: datetime,
    min_gap: timedelta = MIN_GAP,
) -> list[FetchRange]:
    """Ranges still missing between ``target_start`` and ``now``.

    Empty coverage → one full-window fetch. Otherwise fill the head (history
    earlier than the earliest candle) and the tail (newer than the latest),
    skipping gaps smaller than ``min_gap``.
    """
    if candle_count == 0 or coverage_from is None or coverage_to is None:
        return [FetchRange(target_start, _minutes(target_start, now), include_first=True)]
    ranges: list[FetchRange] = []
    if coverage_from - target_start > min_gap:
        ranges.append(
            FetchRange(target_start, _minutes(target_start, coverage_from), include_first=True)
        )
    if now - coverage_to > min_gap:
        ranges.append(FetchRange(coverage_to, _minutes(coverage_to, now), include_first=False))
    return ranges


async def sync_instrument(
    *,
    client: object,
    engine: AsyncEngine,
    instrument: str,
    target_start: datetime,
    now: datetime,
    page_size: int,
    request_interval_seconds: float,
    coverage_provider: CoverageProvider,
    ingestor: Ingestor = ingest_historical_candles,
) -> SyncReport:
    before = await coverage_provider(instrument)
    plan = gap_plan(
        coverage_from=before["from"],
        coverage_to=before["to"],
        candle_count=int(before["candle_count"]),
        target_start=target_start,
        now=now,
    )
    imported = 0
    for fetch in plan:
        imported += await ingestor(
            client=client,
            engine=engine,
            instrument=instrument,
            from_time=fetch.from_time,
            count=fetch.count,
            page_size=page_size,
            request_interval_seconds=request_interval_seconds,
            include_first=fetch.include_first,
        )
    after = await coverage_provider(instrument)
    return SyncReport(
        instrument=instrument,
        imported=imported,
        candle_count=int(after["candle_count"]),
        coverage_from=after["from"],
        coverage_to=after["to"],
    )


async def sync_universe(
    *,
    settings: Settings,
    engine: AsyncEngine,
    days: int,
    instruments: tuple[str, ...] | None = None,
    now: datetime | None = None,
    client_factory: ClientFactory = OandaClient.from_settings,
) -> list[SyncReport]:
    if days <= 0:
        msg = "days must be positive"
        raise ValueError(msg)
    resolved = instruments or settings.research_instruments or RESEARCH_INSTRUMENTS
    moment = now or datetime.now(UTC)
    target_start = moment - timedelta(days=days)

    async def coverage_provider(instrument: str) -> dict:
        async with engine.connect() as connection:
            return await get_candle_coverage(connection, instrument=instrument)

    reports: list[SyncReport] = []
    async with client_factory(settings) as client:  # type: ignore[attr-defined]
        for instrument in resolved:
            reports.append(
                await sync_instrument(
                    client=client,
                    engine=engine,
                    instrument=instrument,
                    target_start=target_start,
                    now=moment,
                    page_size=settings.oanda_historical_candle_page_size,
                    request_interval_seconds=settings.oanda_historical_request_interval_seconds,
                    coverage_provider=coverage_provider,
                )
            )
    return reports
