from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationStatus,
    TrialRecord,
    TrialScore,
)
from harbor_bot.optimizer.runner import OptimizationRunResult
from harbor_bot.optimizer.service import OptimizerService


@pytest.mark.asyncio
async def test_optimizer_service_runs_injected_runner_over_inline_closed_candles() -> None:
    calls = []

    def runner(**kwargs) -> OptimizationRunResult:
        calls.append(kwargs)
        return _run_result()

    service = OptimizerService(optimization_runner=runner)
    response = await service.start_optimization(
        {
            "instrument": "EUR_USD",
            "candles": [_record("2026-01-15T01:00:00+00:00"), _record("2026-01-16T01:00:00+00:00")],
            "optimizer_config": {"trial_count": 2, "candidate_count": 1},
            "backtest_config": {"spread_pips": "0.9"},
        }
    )

    assert response["study_id"] is None
    assert response["status"] == "completed"
    assert response["sampler"] == "TPESampler"
    assert response["pruner"] == "MedianPruner"
    assert response["candidates"][0]["status"] == "paper"
    assert response["data_separation"]["no_live_forward_data"] is True
    assert response["data_separation"]["variant_trades_used"] is False
    assert len(calls) == 1
    assert calls[0]["optimizer_config"].trial_count == 2
    assert calls[0]["optimizer_config"].candidate_count == 1
    assert calls[0]["backtest_config"].spread_pips == Decimal("0.9")


@pytest.mark.asyncio
async def test_optimizer_service_uses_requested_instrument_and_default_jpy_rules() -> None:
    calls = []

    def runner(**kwargs) -> OptimizationRunResult:
        calls.append(kwargs)
        return _run_result()

    service = OptimizerService(optimization_runner=runner)
    response = await service.start_optimization(
        {
            "instrument": "USD_JPY",
            "candles": [
                _record("2026-01-15T01:00:00+00:00", instrument="USD_JPY"),
                _record("2026-01-16T01:00:00+00:00", instrument="USD_JPY"),
            ],
        }
    )

    assert response["status"] == "completed"
    assert calls[0]["base_strategy_config"].instrument == "USD_JPY"
    assert calls[0]["instrument_rules"].instrument == "USD_JPY"
    assert calls[0]["instrument_rules"].pip_location == -2
    assert calls[0]["instrument_rules"].display_precision == 3


@pytest.mark.asyncio
async def test_optimizer_service_persists_when_engine_is_configured() -> None:
    writes = []

    async def writer(engine, **kwargs) -> int:
        writes.append((engine, kwargs))
        return 42

    service = OptimizerService(
        persistence_engine=object(),
        optimization_runner=lambda **_: _run_result(),
        persistence_writer=writer,
    )
    response = await service.start_optimization(
        {
            "instrument": "EUR_USD",
            "candles": [_record("2026-01-15T01:00:00+00:00"), _record("2026-01-16T01:00:00+00:00")],
        }
    )

    assert response["study_id"] == 42
    assert len(writes) == 1
    assert writes[0][1]["status"] == OptimizationStatus.COMPLETED
    assert len(writes[0][1]["trials"]) == 1
    assert len(writes[0][1]["candidates"]) == 1


@pytest.mark.asyncio
async def test_optimizer_service_queues_persisted_source_with_background_tasks() -> None:
    starts = []

    async def starter(engine, **kwargs) -> int:
        starts.append((engine, kwargs))
        return 99

    async def selector(engine, *, instrument: str, required_days: int) -> dict[str, Any]:
        assert engine == "engine"
        assert instrument == "GBP_USD"
        assert required_days == 80
        return {
            "instrument": instrument,
            "from": datetime(2026, 1, 15, tzinfo=UTC),
            "to": datetime(2026, 6, 15, tzinfo=UTC),
            "coverage": {"candle_count": 180_000},
        }

    tasks = _BackgroundTasks()
    service = OptimizerService(
        persistence_engine="engine",
        candle_window_selector=selector,
        study_starter=starter,
    )

    response = await service.start_optimization(
        {"source": "persisted_candles", "instrument": "GBP_USD"},
        background_tasks=tasks,
    )

    assert response["study_id"] == 99
    assert response["status"] == "running"
    assert response["trials"] == []
    assert response["data_separation"]["candle_source"]["instrument"] == "GBP_USD"
    assert starts[0][1]["walkforward_json"]["queued"] is True
    assert len(tasks.calls) == 1
    assert tasks.calls[0][0] == service.finish_queued_optimization
    assert tasks.calls[0][1] == (99, {"source": "persisted_candles", "instrument": "GBP_USD"})


@pytest.mark.asyncio
async def test_optimizer_service_marks_queued_study_failed_when_background_run_fails() -> None:
    failures = []

    async def selector(engine, *, instrument: str, required_days: int) -> dict[str, Any]:
        return {
            "instrument": instrument,
            "from": datetime(2026, 1, 15, tzinfo=UTC),
            "to": datetime(2026, 1, 16, tzinfo=UTC),
        }

    async def reader(
        engine,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        return [_record("2026-01-15T14:00:00+00:00")]

    async def failure_writer(engine, **kwargs) -> None:
        failures.append((engine, kwargs))

    service = OptimizerService(
        persistence_engine="engine",
        candle_reader=reader,
        candle_window_selector=selector,
        study_failure_writer=failure_writer,
    )

    await service.finish_queued_optimization(42, {"source": "persisted_candles"})

    assert failures[0][0] == "engine"
    assert failures[0][1]["study_id"] == 42
    assert failures[0][1]["walkforward_json"]["failure_reason"].endswith(
        "complete strategy days available; 120 required"
    )


@pytest.mark.asyncio
async def test_optimizer_service_rejects_requests_without_local_data() -> None:
    service = OptimizerService(optimization_runner=lambda **_: _run_result())

    with pytest.raises(ValueError, match="candles or fixture"):
        await service.start_optimization({"instrument": "EUR_USD"})


@pytest.mark.asyncio
async def test_optimizer_service_rejects_persisted_source_below_research_data_floor() -> None:
    calls = []

    async def reader(
        engine,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        calls.append((engine, instrument, start, end))
        return [_record("2026-01-15T14:00:00+00:00"), _record("2026-01-16T14:00:00+00:00")]

    async def selector(engine, *, instrument: str, required_days: int) -> dict[str, Any]:
        assert engine == "engine"
        assert instrument == "EUR_USD"
        assert required_days == 80
        return {
            "instrument": instrument,
            "from": datetime(2026, 1, 15, tzinfo=UTC),
            "to": datetime(2026, 1, 16, 23, 59, tzinfo=UTC),
        }

    service = OptimizerService(
        persistence_engine="engine",
        candle_reader=reader,
        candle_window_selector=selector,
        optimization_runner=lambda **_: _run_result(),
        persistence_writer=_writer,
    )
    with pytest.raises(ValueError, match="complete strategy days available"):
        await service.start_optimization({"source": "persisted_candles"})

    assert calls == [
        (
            "engine",
            "EUR_USD",
            datetime(2026, 1, 15, tzinfo=UTC),
            datetime(2026, 1, 16, 23, 59, tzinfo=UTC),
        )
    ]


@pytest.mark.asyncio
async def test_optimizer_service_preflights_persisted_study_shape_and_baseline() -> None:
    async def reader(
        engine,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        assert engine == "engine"
        assert instrument == "EUR_USD"
        assert start == datetime(2026, 1, 15, tzinfo=UTC)
        assert end == datetime(2026, 1, 16, 23, 59, tzinfo=UTC)
        return [
            _record("2026-01-15T01:00:00+00:00"),
            _record("2026-01-15T07:00:00+00:00"),
            _record("2026-01-15T14:30:00+00:00"),
            _record("2026-01-15T16:31:00+00:00"),
            _record("2026-01-16T01:00:00+00:00"),
            _record("2026-01-16T07:00:00+00:00"),
            _record("2026-01-16T14:30:00+00:00"),
            _record("2026-01-16T16:31:00+00:00"),
        ]

    async def selector(engine, *, instrument: str, required_days: int) -> dict[str, Any]:
        assert required_days == 80
        return {
            "instrument": instrument,
            "from": datetime(2026, 1, 15, tzinfo=UTC),
            "to": datetime(2026, 1, 16, 23, 59, tzinfo=UTC),
        }

    service = OptimizerService(
        persistence_engine="engine",
        candle_reader=reader,
        candle_window_selector=selector,
    )
    response = await service.preflight_optimization(
        {
            "source": "persisted_candles",
            "optimizer_config": {
                "trial_count": 2,
                "candidate_count": 1,
                "walk_forward": {
                    "train_window_days": 1,
                    "oos_window_days": 1,
                    "step_days": 1,
                },
            },
        }
    )

    assert response["status"] == "not_ready"
    assert response["study_config"]["trial_count"] == 96
    assert response["candidate_gate"]["min_in_sample_trades"] == 12
    assert response["candidate_gate"]["min_out_of_sample_trades"] == 4
    assert response["dataset"]["candle_count"] == 8
    assert response["dataset"]["evaluable_session_day_count"] == 2
    assert response["walk_forward"]["required_session_days"] == 80
    assert response["walk_forward"]["train_window_days"] == 60
    assert response["walk_forward"]["out_of_sample_window_days"] == 20
    assert response["walk_forward"]["window_count"] == 0
    assert response["baseline"] is None
    assert response["research_protocol"]["status"] == "not_ready"
    assert response["research_protocol"]["data_requirements"]["min_evaluable_days"] == 120
    assert response["recommended_payload"]["optimizer_config"]["trial_count"] == 96


@pytest.mark.asyncio
async def test_optimizer_service_rejects_persisted_source_without_candle_window() -> None:
    async def selector(engine, *, instrument: str, required_days: int) -> None:
        return None

    service = OptimizerService(
        candle_reader=lambda **_: [],
        candle_window_selector=selector,
        optimization_runner=lambda **_: _run_result(),
    )

    with pytest.raises(ValueError, match="import OANDA historical candles"):
        await service.start_optimization({"source": "persisted_candles"})


def _run_result() -> OptimizationRunResult:
    return OptimizationRunResult(
        status=OptimizationStatus.COMPLETED,
        trials=(
            TrialRecord(
                trial_no=0,
                params={"fvg_window": 8},
                score=TrialScore(
                    in_sample_score=Decimal("1.0"),
                    out_of_sample_score=Decimal("1.5"),
                    robustness_score=Decimal("1.4"),
                ),
            ),
        ),
        candidates=(
            CandidateVariant(label="candidate-1", params={"fvg_window": 8}, source_trial_no=0),
        ),
        sampler_name="TPESampler",
        pruner_name="MedianPruner",
    )


async def _writer(engine, **kwargs) -> int:
    return 42


class _BackgroundTasks:
    def __init__(self) -> None:
        self.calls = []

    def add_task(self, task, *args) -> None:
        self.calls.append((task, args))


def _record(ts: str, *, instrument: str = "EUR_USD") -> dict[str, object]:
    return {
        "instrument": instrument,
        "ts": ts,
        "o": "1.1000",
        "h": "1.1010",
        "low": "1.0990",
        "c": "1.1005",
        "volume": 100,
        "complete": True,
    }


def _candle(ts: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts).astimezone(UTC),
        o=Decimal("1.1000"),
        h=Decimal("1.1010"),
        low=Decimal("1.0990"),
        c=Decimal("1.1005"),
        volume=100,
    )
