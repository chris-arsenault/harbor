from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

RECENT_FALLBACK_DAYS = 7
HISTORICAL_LOOKBACK_DAYS = 730
HISTORICAL_END_OFFSET_DAYS = 182


@dataclass(frozen=True)
class BackfillFetch:
    instrument: str
    horizon: str
    from_time: datetime
    to_time: datetime
    include_first: bool
    days: tuple[date, ...] = ()

    @property
    def day_count(self) -> int:
        return len(self.days)


@dataclass(frozen=True)
class InstrumentBackfillPlan:
    instrument: str
    recent_fetches: tuple[BackfillFetch, ...]
    historical_fetches: tuple[BackfillFetch, ...]
    expected_days: tuple[date, ...]
    loaded_days: tuple[date, ...]
    missing_days: tuple[date, ...]
    months: tuple[dict[str, Any], ...]

    @property
    def fetches(self) -> tuple[BackfillFetch, ...]:
        return self.recent_fetches + self.historical_fetches


@dataclass(frozen=True)
class BackfillPlan:
    created_at: datetime
    historical_start: date
    historical_end: date
    instruments: tuple[InstrumentBackfillPlan, ...]

    @property
    def fetches(self) -> tuple[BackfillFetch, ...]:
        return tuple(fetch for instrument in self.instruments for fetch in instrument.fetches)


def build_backfill_plan(
    *,
    moment: datetime,
    instruments: tuple[str, ...],
    coverages: dict[str, dict[str, Any]],
    daily_coverages: dict[str, dict[date, dict[str, Any]]],
) -> BackfillPlan:
    now = moment.astimezone(UTC)
    historical_start = (now - timedelta(days=HISTORICAL_LOOKBACK_DAYS)).date()
    historical_end = (now - timedelta(days=HISTORICAL_END_OFFSET_DAYS)).date()
    expected_days = tuple(_weekdays_between(historical_start, historical_end))
    instrument_plans = tuple(
        _instrument_plan(
            instrument=instrument,
            now=now,
            expected_days=expected_days,
            coverage=coverages.get(instrument, {}),
            daily_coverage=daily_coverages.get(instrument, {}),
        )
        for instrument in instruments
    )
    return BackfillPlan(
        created_at=now,
        historical_start=historical_start,
        historical_end=historical_end,
        instruments=instrument_plans,
    )


def backfill_status_from_plan(plan: BackfillPlan, *, job_id: str) -> dict[str, Any]:
    fetches = plan.fetches
    total_missing_days = sum(len(instrument.missing_days) for instrument in plan.instruments)
    total_loaded_days = sum(len(instrument.loaded_days) for instrument in plan.instruments)
    total_expected_days = sum(len(instrument.expected_days) for instrument in plan.instruments)
    return {
        "status": "running",
        "job_id": job_id,
        "started_at": _iso(plan.created_at),
        "finished_at": None,
        "error": None,
        "current_instrument": None,
        "imported_count": 0,
        "completed_ranges": 0,
        "total_ranges": len(fetches),
        "historical": {
            "start": plan.historical_start.isoformat(),
            "end": plan.historical_end.isoformat(),
            "expected_days": total_expected_days,
            "loaded_days": total_loaded_days,
            "missing_days": total_missing_days,
            "filled_days": 0,
            "pending_days": total_missing_days,
        },
        "recent": {
            "pending_ranges": sum(
                len(instrument.recent_fetches) for instrument in plan.instruments
            ),
            "completed_ranges": 0,
        },
        "instruments": [_instrument_status(instrument) for instrument in plan.instruments],
    }


def mark_fetch_completed(
    status: dict[str, Any],
    fetch: BackfillFetch,
    *,
    imported: int,
) -> None:
    status["completed_ranges"] = int(status["completed_ranges"]) + 1
    status["imported_count"] = int(status["imported_count"]) + imported
    status["current_instrument"] = fetch.instrument
    instrument = _find_instrument_status(status, fetch.instrument)
    instrument["imported_count"] = int(instrument["imported_count"]) + imported
    instrument["completed_ranges"] = int(instrument["completed_ranges"]) + 1
    if int(instrument["completed_ranges"]) >= int(instrument["total_ranges"]):
        instrument["status"] = "completed"
    if fetch.horizon == "recent":
        status["recent"]["completed_ranges"] = int(status["recent"]["completed_ranges"]) + 1
        instrument["recent"]["status"] = "completed"
        instrument["recent"]["imported_count"] = (
            int(instrument["recent"]["imported_count"]) + imported
        )
        return

    filled_days = set(instrument["_filled_days"])
    filled_days.update(day.isoformat() for day in fetch.days)
    instrument["_filled_days"] = sorted(filled_days)
    instrument["historical"]["filled_days"] = len(filled_days)
    instrument["historical"]["pending_days"] = max(
        0,
        int(instrument["historical"]["missing_days"]) - len(filled_days),
    )
    instrument["historical"]["months"] = _month_status_from_json_days(
        expected_days=instrument["_expected_days"],
        loaded_days=instrument["_loaded_days"],
        missing_days=instrument["_missing_days"],
        filled_days=instrument["_filled_days"],
    )
    status["historical"]["filled_days"] = sum(
        int(item["historical"]["filled_days"]) for item in status["instruments"]
    )
    status["historical"]["pending_days"] = max(
        0,
        int(status["historical"]["missing_days"]) - int(status["historical"]["filled_days"]),
    )


def public_backfill_status(status: dict[str, Any]) -> dict[str, Any]:
    result = dict(status)
    result["historical"] = dict(status["historical"])
    result["recent"] = dict(status["recent"])
    instruments = []
    for instrument in status["instruments"]:
        item = {
            key: value
            for key, value in instrument.items()
            if key not in {"_expected_days", "_loaded_days", "_missing_days", "_filled_days"}
        }
        item["recent"] = dict(instrument["recent"])
        item["historical"] = dict(instrument["historical"])
        item["historical"]["months"] = [dict(month) for month in instrument["historical"]["months"]]
        instruments.append(item)
    result["instruments"] = instruments
    return result


def idle_backfill_status() -> dict[str, Any]:
    return {
        "status": "idle",
        "job_id": None,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "current_instrument": None,
        "imported_count": 0,
        "completed_ranges": 0,
        "total_ranges": 0,
        "historical": {
            "start": None,
            "end": None,
            "expected_days": 0,
            "loaded_days": 0,
            "missing_days": 0,
            "filled_days": 0,
            "pending_days": 0,
        },
        "recent": {"pending_ranges": 0, "completed_ranges": 0},
        "instruments": [],
    }


def _instrument_plan(
    *,
    instrument: str,
    now: datetime,
    expected_days: tuple[date, ...],
    coverage: dict[str, Any],
    daily_coverage: dict[date, dict[str, Any]],
) -> InstrumentBackfillPlan:
    loaded_days = tuple(day for day in expected_days if _day_loaded(daily_coverage.get(day)))
    loaded = set(loaded_days)
    missing_days = tuple(day for day in expected_days if day not in loaded)
    recent_fetches = _recent_fetches(instrument=instrument, now=now, coverage=coverage)
    historical_fetches = tuple(
        BackfillFetch(
            instrument=instrument,
            horizon="historical",
            from_time=_day_start(days[0]),
            to_time=_day_start(days[-1] + timedelta(days=1)),
            include_first=True,
            days=days,
        )
        for days in _group_contiguous_days(missing_days)
    )
    return InstrumentBackfillPlan(
        instrument=instrument,
        recent_fetches=tuple(recent_fetches),
        historical_fetches=historical_fetches,
        expected_days=expected_days,
        loaded_days=loaded_days,
        missing_days=missing_days,
        months=tuple(
            month_status(
                expected_days=expected_days,
                loaded_days=loaded_days,
                missing_days=missing_days,
                filled_days=(),
            )
        ),
    )


def _recent_fetches(
    *,
    instrument: str,
    now: datetime,
    coverage: dict[str, Any],
) -> tuple[BackfillFetch, ...]:
    coverage_to = coverage.get("to")
    if coverage_to is None:
        return (
            BackfillFetch(
                instrument=instrument,
                horizon="recent",
                from_time=now - timedelta(days=RECENT_FALLBACK_DAYS),
                to_time=now,
                include_first=True,
            ),
        )
    coverage_to = coverage_to.astimezone(UTC)
    if now - coverage_to <= timedelta(minutes=2):
        return ()
    return (
        BackfillFetch(
            instrument=instrument,
            horizon="recent",
            from_time=coverage_to,
            to_time=now,
            include_first=False,
        ),
    )


def month_status(
    *,
    expected_days: tuple[date, ...],
    loaded_days: tuple[date, ...],
    missing_days: tuple[date, ...],
    filled_days: tuple[date, ...],
) -> list[dict[str, Any]]:
    loaded = set(loaded_days)
    missing = set(missing_days)
    filled = set(filled_days)
    months = sorted({day.strftime("%Y-%m") for day in expected_days})
    return [
        _month_summary(
            month=month,
            expected_days=tuple(day for day in expected_days if day.strftime("%Y-%m") == month),
            loaded_days=loaded,
            missing_days=missing,
            filled_days=filled,
        )
        for month in months
    ]


def _month_status_from_json_days(
    *,
    expected_days: list[str],
    loaded_days: list[str],
    missing_days: list[str],
    filled_days: list[str],
) -> list[dict[str, Any]]:
    return month_status(
        expected_days=tuple(date.fromisoformat(day) for day in expected_days),
        loaded_days=tuple(date.fromisoformat(day) for day in loaded_days),
        missing_days=tuple(date.fromisoformat(day) for day in missing_days),
        filled_days=tuple(date.fromisoformat(day) for day in filled_days),
    )


def _month_summary(
    *,
    month: str,
    expected_days: tuple[date, ...],
    loaded_days: set[date],
    missing_days: set[date],
    filled_days: set[date],
) -> dict[str, Any]:
    expected = len(expected_days)
    loaded = sum(1 for day in expected_days if day in loaded_days)
    missing = sum(1 for day in expected_days if day in missing_days)
    filled = sum(1 for day in expected_days if day in filled_days)
    pending = max(0, missing - filled)
    complete = loaded + filled
    return {
        "month": month,
        "expected_days": expected,
        "loaded_days": loaded,
        "missing_days": missing,
        "filled_days": filled,
        "pending_days": pending,
        "complete_days": complete,
        "completion_ratio": 1.0 if expected == 0 else complete / expected,
    }


def _instrument_status(instrument: InstrumentBackfillPlan) -> dict[str, Any]:
    expected_days = [day.isoformat() for day in instrument.expected_days]
    loaded_days = [day.isoformat() for day in instrument.loaded_days]
    missing_days = [day.isoformat() for day in instrument.missing_days]
    return {
        "instrument": instrument.instrument,
        "status": "pending" if instrument.fetches else "completed",
        "imported_count": 0,
        "completed_ranges": 0,
        "total_ranges": len(instrument.fetches),
        "recent": {
            "status": "pending" if instrument.recent_fetches else "completed",
            "from": _iso(instrument.recent_fetches[0].from_time)
            if instrument.recent_fetches
            else None,
            "to": _iso(instrument.recent_fetches[-1].to_time)
            if instrument.recent_fetches
            else None,
            "imported_count": 0,
        },
        "historical": {
            "expected_days": len(instrument.expected_days),
            "loaded_days": len(instrument.loaded_days),
            "missing_days": len(instrument.missing_days),
            "filled_days": 0,
            "pending_days": len(instrument.missing_days),
            "months": [dict(month) for month in instrument.months],
        },
        "_expected_days": expected_days,
        "_loaded_days": loaded_days,
        "_missing_days": missing_days,
        "_filled_days": [],
    }


def _find_instrument_status(status: dict[str, Any], instrument: str) -> dict[str, Any]:
    for item in status["instruments"]:
        if item["instrument"] == instrument:
            return item
    msg = f"unknown backfill instrument {instrument}"
    raise KeyError(msg)


def _day_loaded(coverage: dict[str, Any] | None) -> bool:
    return bool(coverage and int(coverage.get("candle_count", 0)) > 0)


def _weekdays_between(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _group_contiguous_days(days: tuple[date, ...]) -> list[tuple[date, ...]]:
    if not days:
        return []
    groups: list[list[date]] = [[days[0]]]
    for day in days[1:]:
        if day == groups[-1][-1] + timedelta(days=1):
            groups[-1].append(day)
        else:
            groups.append([day])
    return [tuple(group) for group in groups]


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
