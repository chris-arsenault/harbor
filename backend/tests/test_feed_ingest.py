import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from harbor_bot.feed.ingest import gap_plan, repair_plan, sync_instrument

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
START = NOW - timedelta(days=180)


def test_gap_plan_empty_coverage_fetches_full_window() -> None:
    plan = gap_plan(
        coverage_from=None, coverage_to=None, candle_count=0, target_start=START, now=NOW
    )

    assert len(plan) == 1
    assert plan[0].from_time == START
    assert plan[0].include_first is True


def test_gap_plan_full_coverage_fetches_nothing() -> None:
    plan = gap_plan(
        coverage_from=START,
        coverage_to=NOW,
        candle_count=10_000,
        target_start=START,
        now=NOW,
    )

    assert plan == []


def test_gap_plan_fetches_only_the_tail_when_history_is_current_but_stale() -> None:
    stale_to = NOW - timedelta(hours=6)
    plan = gap_plan(
        coverage_from=START,
        coverage_to=stale_to,
        candle_count=10_000,
        target_start=START,
        now=NOW,
    )

    assert len(plan) == 1
    assert plan[0].from_time == stale_to
    assert plan[0].include_first is False


def test_gap_plan_fetches_head_and_tail_when_both_missing() -> None:
    plan = gap_plan(
        coverage_from=START + timedelta(days=30),
        coverage_to=NOW - timedelta(days=2),
        candle_count=5_000,
        target_start=START,
        now=NOW,
    )

    assert [fetch.include_first for fetch in plan] == [True, False]
    assert plan[0].from_time == START
    assert plan[1].from_time == NOW - timedelta(days=2)


def test_repair_plan_refetches_the_full_covered_range() -> None:
    coverage = {
        "candle_count": 1000,
        "from": START,
        "to": NOW - timedelta(hours=1),
        "bid_ask_count": 0,
    }

    plan = repair_plan(coverage, target_start=START, now=NOW)

    assert len(plan) == 1
    assert plan[0].from_time == START  # not just the tail — the whole range
    assert plan[0].include_first is True


def test_sync_instrument_repair_refetches_when_bid_ask_incomplete() -> None:
    coverages = iter(
        [
            {"candle_count": 1000, "from": START, "to": NOW, "bid_ask_count": 0},
            {"candle_count": 1000, "from": START, "to": NOW, "bid_ask_count": 1000},
        ]
    )
    calls: list[dict[str, Any]] = []

    async def coverage_provider(instrument: str) -> dict[str, Any]:
        return next(coverages)

    async def ingestor(**kwargs: Any) -> int:
        calls.append(kwargs)
        return 1000

    report = asyncio.run(_sync(coverage_provider, ingestor, repair=True))

    assert len(calls) == 1
    assert calls[0]["from_time"] == START
    assert calls[0]["include_first"] is True
    assert report.imported == 1000


def test_sync_instrument_repair_skips_when_bid_ask_already_complete() -> None:
    coverage = {"candle_count": 1000, "from": START, "to": NOW, "bid_ask_count": 1000}
    calls: list[dict[str, Any]] = []

    async def coverage_provider(instrument: str) -> dict[str, Any]:
        return coverage

    async def ingestor(**kwargs: Any) -> int:
        calls.append(kwargs)
        return 0

    report = asyncio.run(_sync(coverage_provider, ingestor, repair=True))

    assert calls == []  # already complete — no wasted re-fetch
    assert report.imported == 0
    assert report.candle_count == 1000


def _sync(coverage_provider: Any, ingestor: Any, *, repair: bool):
    return sync_instrument(
        client=object(),
        engine=object(),
        instrument="EUR_USD",
        target_start=START,
        now=NOW,
        page_size=5000,
        request_interval_seconds=0.0,
        coverage_provider=coverage_provider,
        ingestor=ingestor,
        repair=repair,
    )


def test_sync_instrument_runs_plan_and_reports_final_coverage() -> None:
    coverages = iter(
        [
            {"instrument": "EUR_USD", "candle_count": 0, "from": None, "to": None},
            {"instrument": "EUR_USD", "candle_count": 1000, "from": START, "to": NOW},
        ]
    )
    calls: list[dict[str, Any]] = []

    async def coverage_provider(instrument: str) -> dict[str, Any]:
        return next(coverages)

    async def ingestor(**kwargs: Any) -> int:
        calls.append(kwargs)
        return 1000

    report = asyncio.run(
        sync_instrument(
            client=object(),
            engine=object(),
            instrument="EUR_USD",
            target_start=START,
            now=NOW,
            page_size=5000,
            request_interval_seconds=0.0,
            coverage_provider=coverage_provider,
            ingestor=ingestor,
        )
    )

    assert len(calls) == 1  # empty coverage → one full-window fetch
    assert calls[0]["instrument"] == "EUR_USD"
    assert calls[0]["include_first"] is True
    assert report.imported == 1000
    assert report.candle_count == 1000
    assert report.coverage_to == NOW
