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
async def test_optimizer_service_rejects_requests_without_local_data() -> None:
    service = OptimizerService(optimization_runner=lambda **_: _run_result())

    with pytest.raises(ValueError, match="candles or fixture"):
        await service.start_optimization({"instrument": "EUR_USD"})


@pytest.mark.asyncio
async def test_optimizer_service_defaults_persisted_source_to_selected_coverage() -> None:
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
        assert required_days == 2
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
    response = await service.start_optimization({"source": "persisted_candles"})

    assert response["study_id"] == 42
    assert calls == [
        (
            "engine",
            "EUR_USD",
            datetime(2026, 1, 15, tzinfo=UTC),
            datetime(2026, 1, 16, 23, 59, tzinfo=UTC),
        )
    ]
    assert response["data_separation"]["source"] == "persisted closed candles"
    assert response["data_separation"]["candle_source"] == {
        "source": "persisted_candles",
        "origin": "database",
        "instrument": "EUR_USD",
        "from": "2026-01-15T00:00:00+00:00",
        "to": "2026-01-16T23:59:00+00:00",
        "candle_count": 2,
    }


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


def _record(ts: str) -> dict[str, object]:
    return {
        "instrument": "EUR_USD",
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
