import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.backtester.service import BacktestService
from harbor_bot.lab.models import LabSnapshot, LabVariantOverview
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationStatus,
    TrialRecord,
    TrialScore,
)
from harbor_bot.optimizer.runner import OptimizationRunResult
from harbor_bot.optimizer.service import OptimizerService
from harbor_bot.paper_engine.models import LabStudySnapshot


def test_experiment_collection_routes_orchestrate_backtests_and_tuning() -> None:
    backtests = FakeBacktestService()
    optimizer = FakeOptimizerService()
    product = FakeProductQueryService()
    client = TestClient(
        create_app(
            backtest_service=backtests,
            optimizer_service=optimizer,
            lab_service=FakeLabService(),
            product_query_service=product,
            candle_source_service=FakeCandleSourceService(),
        )
    )

    listed_backtests = client.get("/api/backtests?limit=5")
    started_backtest = client.post(
        "/api/backtests",
        json={
            "source": "persisted_candles",
            "instrument": "EUR_USD",
            "candle_range": {
                "from": "2026-01-15T14:00:00Z",
                "to": "2026-01-15T15:00:00Z",
            },
        },
    )
    listed_studies = client.get("/api/optimize?limit=4")
    started_study = client.post(
        "/api/optimize",
        json={"fixture": "clean_signal_day.json", "optimizer_config": {"trial_count": 2}},
    )

    assert listed_backtests.json()["runs"][0]["run_id"] == 42
    assert started_backtest.json()["run_id"] == 43
    assert listed_studies.json()["studies"][0]["best_trial_id"] == 9
    assert started_study.json()["best_trial_history"][0]["trial_no"] == 0
    assert backtests.started_payloads[0]["source"] == "persisted_candles"
    assert optimizer.started_payloads[0]["optimizer_config"]["trial_count"] == 2
    assert product.calls == [("backtests", 5), ("studies", 4)]


def test_candle_source_routes_report_coverage_and_import_historical_data() -> None:
    source = FakeCandleSourceService()
    client = TestClient(
        create_app(
            backtest_service=FakeBacktestService(),
            optimizer_service=FakeOptimizerService(),
            lab_service=FakeLabService(),
            product_query_service=FakeProductQueryService(),
            candle_source_service=source,
        )
    )

    status = client.get("/api/candles/source?instrument=EUR_USD")
    imported = client.post("/api/candles/import", json={"instrument": "EUR_USD", "count": 500})

    assert status.json()["coverage"]["candle_count"] == 0
    assert imported.json()["imported_count"] == 500
    assert source.import_payloads == [{"instrument": "EUR_USD", "count": 500}]


def test_candle_source_routes_accept_research_universe_import() -> None:
    source = FakeCandleSourceService()
    client = TestClient(
        create_app(
            backtest_service=FakeBacktestService(),
            optimizer_service=FakeOptimizerService(),
            lab_service=FakeLabService(),
            product_query_service=FakeProductQueryService(),
            candle_source_service=source,
        )
    )

    imported = client.post(
        "/api/candles/import",
        json={"instrument": "research_universe", "instruments": ["GBP_USD", "USD_JPY"], "count": 2},
    )

    assert imported.json()["instrument"] == "research_universe"
    assert imported.json()["imported_count"] == 4
    assert source.import_payloads == [
        {"instrument": "research_universe", "instruments": ["GBP_USD", "USD_JPY"], "count": 2}
    ]


def test_default_optimizer_service_loads_packaged_validation_fixture() -> None:
    app = create_app(
        observability_service=object(),
        lab_service=FakeLabService(),
        paper_forward_service=object(),
        product_query_service=FakeProductQueryService(),
        config_service=object(),
        readiness_checker=FakeReadinessChecker(),
    )
    fixture_base_path = app.state.optimizer_service.fixture_base_path

    assert fixture_base_path.joinpath("walkforward_validation.json").is_file()

    service = OptimizerService(fixture_base_path=fixture_base_path)
    response = asyncio.run(
        service.start_optimization(
            {
                "fixture": "walkforward_validation.json",
                "optimizer_config": {"trial_count": 1, "candidate_count": 1},
            }
        )
    )

    assert response["study_id"] is None
    assert response["status"] == "completed"
    assert response["trial_count"] == 1


@pytest.mark.asyncio
async def test_backtest_service_reads_persisted_candle_ranges_for_ui_requests() -> None:
    calls = []

    async def reader(
        engine,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        calls.append((engine, instrument, start, end))
        return [_record("2026-01-15T14:00:00+00:00"), _record("2026-01-15T14:01:00+00:00")]

    service = BacktestService(candle_reader=reader)
    response = await service.start_backtest(
        {
            "source": "persisted_candles",
            "instrument": "EUR_USD",
            "candle_range": {
                "from": "2026-01-15T14:00:00Z",
                "to": "2026-01-15T14:01:00Z",
            },
        }
    )

    assert response["status"] == "completed"
    assert calls == [
        (
            None,
            "EUR_USD",
            datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
            datetime(2026, 1, 15, 14, 1, tzinfo=UTC),
        )
    ]


@pytest.mark.asyncio
async def test_optimizer_service_returns_best_trial_history_for_inline_candles() -> None:
    service = OptimizerService(optimization_runner=lambda **_: _run_result())
    response = await service.start_optimization(
        {
            "instrument": "EUR_USD",
            "candles": [
                _record("2026-01-15T14:00:00+00:00"),
                _record("2026-01-15T14:01:00+00:00"),
            ],
        }
    )

    assert response["best_trial_history"] == [
        {"trial_no": 0, "oos_score": "0.80000000", "robustness_score": "0.70000000"},
        {"trial_no": 1, "oos_score": "1.50000000", "robustness_score": "1.40000000"},
    ]


class FakeBacktestService:
    def __init__(self) -> None:
        self.started_payloads: list[dict[str, Any]] = []

    async def start_backtest(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.started_payloads.append(payload)
        return {"run_id": 43, "status": "completed", "stats": {}, "trades": []}

    async def get_backtest(self, run_id: int) -> dict[str, Any] | None:
        return {"run_id": run_id, "status": "completed", "stats": {}, "trades": []}


class FakeOptimizerService:
    def __init__(self) -> None:
        self.started_payloads: list[dict[str, Any]] = []

    async def start_optimization(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.started_payloads.append(payload)
        return {
            "study_id": 44,
            "status": "completed",
            "trials": [],
            "candidates": [],
            "best_trial_history": [
                {"trial_no": 0, "oos_score": "1.50000000", "robustness_score": "1.40000000"}
            ],
        }


class FakeProductQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    async def list_backtest_runs(self, *, limit: int) -> dict[str, Any]:
        self.calls.append(("backtests", limit))
        return {"runs": [{"run_id": 42, "trade_count": 1}]}

    async def list_optimizer_studies(self, *, limit: int) -> dict[str, Any]:
        self.calls.append(("studies", limit))
        return {"studies": [{"study_id": 3, "best_trial_id": 9}]}


class FakeCandleSourceService:
    def __init__(self) -> None:
        self.import_payloads: list[dict[str, Any]] = []

    async def get_status(self, *, instrument: str | None = None) -> dict[str, Any]:
        return {
            "instrument": instrument or "EUR_USD",
            "primary_source": "persisted_candles",
            "granularity": "M1",
            "price_component": "midpoint",
            "coverage": {
                "instrument": instrument or "EUR_USD",
                "candle_count": 0,
                "from": None,
                "to": None,
            },
            "source_methods": ["oanda_historical_import", "oanda_pricing_stream"],
            "research_instruments": ["GBP_USD", "EUR_USD"],
            "historical_import": {
                "page_size": 5000,
                "default_count": 259200,
                "request_interval_seconds": 0.1,
                "upsert_key": "instrument+timestamp",
                "replaces_existing": False,
            },
            "oanda_historical_import_configured": True,
        }

    async def import_historical(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.import_payloads.append(payload)
        if payload.get("instrument") == "research_universe":
            results = [
                {
                    "instrument": instrument,
                    "requested_count": int(payload.get("count") or 0),
                    "imported_count": int(payload.get("count") or 0),
                    "coverage": {
                        "instrument": instrument,
                        "candle_count": int(payload.get("count") or 0),
                        "from": "2026-01-15T00:00:00+00:00",
                        "to": "2026-01-16T23:59:00+00:00",
                    },
                }
                for instrument in payload.get("instruments", [])
            ]
            return {
                "status": "completed",
                "source": "oanda_historical_import",
                "instrument": "research_universe",
                "instruments": [result["instrument"] for result in results],
                "requested_count": sum(result["requested_count"] for result in results),
                "imported_count": sum(result["imported_count"] for result in results),
                "from": "2026-01-15T00:00:00+00:00",
                "coverage": results[0]["coverage"],
                "results": results,
            }
        return {
            "status": "completed",
            "source": "oanda_historical_import",
            "instrument": str(payload.get("instrument") or "EUR_USD"),
            "requested_count": int(payload.get("count") or 0),
            "imported_count": int(payload.get("count") or 0),
            "coverage": {
                "instrument": str(payload.get("instrument") or "EUR_USD"),
                "candle_count": int(payload.get("count") or 0),
                "from": "2026-01-15T00:00:00+00:00",
                "to": "2026-01-16T23:59:00+00:00",
            },
        }


class FakeLabService:
    async def get_lab_snapshot(self, *, study_id: int) -> LabSnapshot | None:
        return LabSnapshot(
            study=LabStudySnapshot(
                study_id=study_id,
                status="completed",
                trial_count=0,
                candidate_count=0,
                paper_variant_count=0,
                created_ts=datetime(2026, 1, 15, 13, 0, tzinfo=UTC),
            ),
            candidates=(),
            variants=LabVariantOverview(
                variants=(),
                leaderboard=(),
                equity_curves=(),
                data_separation={},
            ),
            data_separation={},
        )


class FakeReadinessChecker:
    async def check(self) -> dict[str, object]:
        return {"status": "ready"}


def _run_result() -> OptimizationRunResult:
    return OptimizationRunResult(
        status=OptimizationStatus.COMPLETED,
        trials=(
            TrialRecord(
                trial_no=0,
                params={"fvg_window": 7},
                score=TrialScore(
                    in_sample_score=Decimal("1.0"),
                    out_of_sample_score=Decimal("0.8"),
                    robustness_score=Decimal("0.7"),
                ),
            ),
            TrialRecord(
                trial_no=1,
                params={"fvg_window": 8},
                score=TrialScore(
                    in_sample_score=Decimal("1.1"),
                    out_of_sample_score=Decimal("1.5"),
                    robustness_score=Decimal("1.4"),
                ),
            ),
        ),
        candidates=(
            CandidateVariant(label="candidate-1", params={"fvg_window": 8}, source_trial_no=1),
        ),
        sampler_name="TPESampler",
        pruner_name="MedianPruner",
    )


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
