from datetime import UTC, date, datetime, timedelta

import pytest

from harbor_bot.feed.backfill import (
    BackfillFetch,
    BackfillPlan,
    InstrumentBackfillPlan,
    backfill_status_from_plan,
    build_backfill_plan,
    mark_fetch_completed,
    month_status,
)
from harbor_bot.feed.source_service import CandleSourceService
from harbor_bot.settings import Settings

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)


def test_backfill_plan_fetches_recent_tail_and_missing_historical_weekdays() -> None:
    plan = build_backfill_plan(
        moment=NOW,
        instruments=("EUR_USD",),
        coverages={
            "EUR_USD": {
                "instrument": "EUR_USD",
                "candle_count": 100,
                "from": datetime(2026, 1, 1, tzinfo=UTC),
                "to": datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
            }
        },
        daily_coverages={
            "EUR_USD": {
                date(2024, 7, 1): {"candle_count": 1440},
                date(2024, 7, 3): {"candle_count": 1440},
            }
        },
    )

    instrument = plan.instruments[0]

    assert instrument.recent_fetches[0].from_time == datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    assert instrument.recent_fetches[0].include_first is False
    assert date(2024, 7, 2) in instrument.missing_days
    assert date(2024, 7, 6) not in instrument.missing_days
    assert all(fetch.to_time > fetch.from_time for fetch in instrument.historical_fetches)


def test_backfill_status_marks_completed_historical_months() -> None:
    plan = build_backfill_plan(
        moment=NOW,
        instruments=("EUR_USD",),
        coverages={"EUR_USD": {"candle_count": 0, "from": None, "to": None}},
        daily_coverages={"EUR_USD": {}},
    )
    status = backfill_status_from_plan(plan, job_id="job-1")
    historical_fetch = plan.instruments[0].historical_fetches[0]

    mark_fetch_completed(status, historical_fetch, imported=1440)

    instrument = status["instruments"][0]
    assert status["historical"]["filled_days"] == historical_fetch.day_count
    assert instrument["historical"]["filled_days"] == historical_fetch.day_count
    assert instrument["historical"]["months"][0]["filled_days"] > 0


def test_month_status_reports_loaded_missing_and_pending_days() -> None:
    result = month_status(
        expected_days=(date(2026, 1, 1), date(2026, 1, 2)),
        loaded_days=(date(2026, 1, 1),),
        missing_days=(date(2026, 1, 2),),
        filled_days=(),
    )

    assert result == [
        {
            "month": "2026-01",
            "expected_days": 2,
            "loaded_days": 1,
            "missing_days": 1,
            "filled_days": 0,
            "pending_days": 1,
            "complete_days": 1,
            "completion_ratio": 0.5,
        }
    ]


@pytest.mark.asyncio
async def test_backfill_worker_does_not_replace_existing_candles() -> None:
    missing_day = date(2026, 6, 26)
    fetch = BackfillFetch(
        instrument="EUR_USD",
        horizon="historical",
        from_time=NOW - timedelta(days=1),
        to_time=NOW,
        include_first=True,
        days=(missing_day,),
    )
    months = tuple(
        month_status(
            expected_days=(missing_day,),
            loaded_days=(),
            missing_days=(missing_day,),
            filled_days=(),
        )
    )
    plan = BackfillPlan(
        created_at=NOW,
        historical_start=missing_day,
        historical_end=missing_day,
        instruments=(
            InstrumentBackfillPlan(
                instrument="EUR_USD",
                recent_fetches=(),
                historical_fetches=(fetch,),
                expected_days=(missing_day,),
                loaded_days=(),
                missing_days=(missing_day,),
                months=months,
            ),
        ),
    )
    calls: list[dict[str, object]] = []

    async def ingestor(**kwargs: object) -> int:
        calls.append(kwargs)
        return 1440

    service = CandleSourceService(
        engine=object(),  # type: ignore[arg-type]
        settings=Settings(OANDA_API_TOKEN="token", OANDA_ACCOUNT_ID="account"),
        client_factory=lambda _settings: _FakeOandaClient(),
        historical_ingestor=ingestor,
    )
    service._backfill_status = backfill_status_from_plan(plan, job_id="job-1")

    await service._run_backfill_worker(plan)

    assert calls[0]["replace_existing"] is False
    assert service._backfill_status["status"] == "completed"


class _FakeOandaClient:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None
