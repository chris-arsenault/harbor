import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.research.service import ResearchService, research_window_from_coverage

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


class FakeResearchService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    async def edge_study(
        self, *, instrument: str, horizon: int, algorithm_id: str, window_days: int
    ) -> dict[str, Any]:
        self.calls.append((instrument, horizon, algorithm_id))
        return {
            "algorithm_id": algorithm_id,
            "instrument": instrument,
            "horizon": horizon,
            "window_days": window_days,
            "total_sweeps": 0,
            "has_edge": False,
        }

    def edge_algorithms(self) -> dict[str, Any]:
        return {"algorithms": []}

    async def capture_scan(self, **kwargs: Any) -> dict[str, Any]:
        return {"received": kwargs, "results": []}

    async def cross_scan(self, **kwargs: Any) -> dict[str, Any]:
        return {"received": kwargs, "results": []}

    async def direction_scan(self, **kwargs: Any) -> dict[str, Any]:
        return {"received": kwargs, "results": []}

    def cross_algorithms(self) -> dict[str, Any]:
        return {"algorithms": []}

    async def triangular_capture(self, **kwargs: Any) -> dict[str, Any]:
        return {"received": kwargs, "results": []}


def test_get_edge_study_routes_through_injected_service() -> None:
    service = FakeResearchService()
    client = TestClient(create_app(research_service=service))

    response = client.get("/api/research/edge", params={"instrument": "GBP_USD", "horizon": 5})

    assert response.status_code == 200
    assert response.json()["instrument"] == "GBP_USD"
    assert service.calls == [("GBP_USD", 5, "generic_sweep_reversal")]
    assert response.json()["window_days"] == 90


def test_capture_scan_routes_payload_to_research_service() -> None:
    service = FakeResearchService()
    client = TestClient(create_app(research_service=service))

    response = client.post(
        "/api/research/capture",
        json={
            "instrument": "eur_usd",
            "algorithms": ["generic_sweep_continuation"],
            "horizons": [15, 30],
            "window_days": 730,
            "spread_pips": "0.7",
            "slippage_pips": "0.2",
        },
    )

    assert response.status_code == 200
    assert response.json()["received"] == {
        "instrument": "EUR_USD",
        "algorithm_ids": ["generic_sweep_continuation"],
        "horizons": [15, 30],
        "window_days": 730,
        "spread_pips": "0.7",
        "slippage_pips": "0.2",
    }


def test_cross_scan_routes_payload_to_research_service() -> None:
    service = FakeResearchService()
    client = TestClient(create_app(research_service=service))

    response = client.post(
        "/api/research/cross/scan",
        json={
            "instruments": ["EUR_USD", "GBP_USD", "EUR_GBP"],
            "algorithms": ["tri_eur_gbp_residual_5d"],
            "window_days": 730,
        },
    )

    assert response.status_code == 200
    assert response.json()["received"] == {
        "instruments": ["EUR_USD", "GBP_USD", "EUR_GBP"],
        "algorithm_ids": ["tri_eur_gbp_residual_5d"],
        "window_days": 730,
    }


def test_direction_scan_routes_payload_to_research_service() -> None:
    service = FakeResearchService()
    client = TestClient(create_app(research_service=service))

    response = client.post(
        "/api/research/directions/scan",
        json={
            "instruments": ["EUR_USD", "BTC_USD"],
            "algorithms": ["weekend_risk_gap_probe"],
            "window_days": 730,
        },
    )

    assert response.status_code == 200
    assert response.json()["received"] == {
        "instruments": ["EUR_USD", "BTC_USD"],
        "algorithm_ids": ["weekend_risk_gap_probe"],
        "window_days": 730,
    }


def test_triangular_capture_routes_payload_to_research_service() -> None:
    service = FakeResearchService()
    client = TestClient(create_app(research_service=service))

    response = client.post(
        "/api/research/triangular/capture",
        json={
            "thresholds": [1.0, 2.0],
            "horizons": [3, 5],
            "window_days": 730,
            "cost_bps_per_leg": 1.0,
        },
    )

    assert response.status_code == 200
    assert response.json()["received"] == {
        "thresholds": [1.0, 2.0],
        "horizons": [3, 5],
        "window_days": 730,
        "cost_bps_per_leg": 1.0,
    }


def test_edge_study_runs_over_loaded_candles() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_fixed_window)

    result = asyncio.run(service.edge_study(instrument="EUR_USD", horizon=3))

    assert result["total_sweeps"] == 2
    assert result["overall"]["count"] == 1
    assert result["has_edge"] is False
    assert result["statistical_notes"]["standard_error_correction"] == (
        "max(iid, cluster_by_trading_day)"
    )


def test_edge_study_with_no_window_returns_empty() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_no_window)

    result = asyncio.run(service.edge_study(instrument="EUR_USD"))

    assert result["total_candles"] == 0
    assert result["total_sweeps"] == 0
    assert result["warnings"][0]["type"] == "no_data"


def test_edge_scan_defaults_to_active_reclaim_algorithm_only() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_fixed_window)

    result = asyncio.run(
        service.edge_scan(instruments=("EUR_USD",), horizons=(3, 5), window_days=1)
    )

    assert result["statistical_notes"]["instrument_count"] == 1
    assert result["statistical_notes"]["algorithm_count"] == 1
    assert result["statistical_notes"]["horizon_count"] == 2
    assert result["statistical_notes"]["planned_overall_test_count"] == 2
    assert result["statistical_notes"]["overall_test_count"] == 2
    assert [algorithm["algorithm_id"] for algorithm in result["algorithms"]] == [
        "multi_candle_sweep_reclaim_reversal"
    ]
    assert {row["algorithm_id"] for row in result["results"]} == {
        "multi_candle_sweep_reclaim_reversal"
    }


def test_explicit_archived_edge_scan_reports_multiple_testing_notes() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_fixed_window)
    archived_algorithm_ids = (
        "generic_sweep_reversal",
        "non_news_proxy_sweep_reversal",
        "mss_confirmed_sweep_reversal",
        "compressed_range_sweep_reversal",
        "clean_level_sweep_reversal",
        "early_ny_sweep_reversal",
        "generic_sweep_continuation",
        "mss_confirmed_sweep_continuation",
        "early_ny_sweep_continuation",
    )

    result = asyncio.run(
        service.edge_scan(
            instruments=("EUR_USD",),
            horizons=(3, 5),
            algorithm_ids=archived_algorithm_ids,
            window_days=1,
        )
    )

    assert result["statistical_notes"]["instrument_count"] == 1
    assert result["statistical_notes"]["algorithm_count"] == 9
    assert result["statistical_notes"]["horizon_count"] == 2
    assert result["statistical_notes"]["planned_overall_test_count"] == 18
    assert result["statistical_notes"]["overall_test_count"] == 18
    assert result["statistical_notes"]["overall_multiple_test_method"] == "benjamini_hochberg"
    assert len(result["algorithms"]) == 9
    assert {row["algorithm_id"] for row in result["results"]} >= {
        "generic_sweep_reversal",
        "mss_confirmed_sweep_reversal",
    }
    assert result["results"][0]["statistical_notes"]["standard_error_correction"] == (
        "max(iid, cluster_by_trading_day)"
    )


def test_edge_scan_can_limit_algorithms() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_fixed_window)

    result = asyncio.run(
        service.edge_scan(
            instruments=("EUR_USD",),
            horizons=(3,),
            algorithm_ids=("generic_sweep_reversal", "clean_level_sweep_reversal"),
            window_days=1,
        )
    )

    assert [algorithm["algorithm_id"] for algorithm in result["algorithms"]] == [
        "generic_sweep_reversal",
        "clean_level_sweep_reversal",
    ]
    assert {row["algorithm_id"] for row in result["results"]} == {
        "generic_sweep_reversal",
        "clean_level_sweep_reversal",
    }


def test_edge_scan_can_use_730_day_confirmatory_window() -> None:
    calls = []

    async def selector(engine: Any, *, instrument: str, required_days: int) -> dict[str, Any]:
        calls.append(required_days)
        return {
            "from": datetime(2024, 1, 1, tzinfo=UTC),
            "to": datetime(2026, 1, 1, tzinfo=UTC),
        }

    service = ResearchService(candle_reader=_fixture_records, window_selector=selector)

    asyncio.run(
        service.edge_scan(
            instruments=("GBP_JPY",),
            horizons=(15, 30),
            algorithm_ids=("clean_level_sweep_reversal",),
            window_days=730,
        )
    )

    assert calls == [730]


def test_research_window_uses_available_data_when_request_exceeds_coverage() -> None:
    window = research_window_from_coverage(
        {
            "instrument": "GBP_JPY",
            "candle_count": 100,
            "from": datetime(2026, 1, 1, tzinfo=UTC),
            "to": datetime(2026, 3, 1, tzinfo=UTC),
        },
        instrument="GBP_JPY",
        requested_days=730,
    )

    assert window is not None
    assert window["used_days"] == 60
    assert window["warnings"][0]["type"] == "partial_window"
    assert "requested 730 calendar days" in window["warnings"][0]["message"]


def test_edge_scan_runs_with_partial_available_window_and_reports_warning() -> None:
    async def selector(engine: Any, *, instrument: str, required_days: int) -> dict[str, Any]:
        return {
            "instrument": instrument,
            "from": datetime(2026, 1, 15, tzinfo=UTC),
            "to": datetime(2026, 1, 16, tzinfo=UTC),
            "requested_days": required_days,
            "available_days": 2,
            "used_days": 2,
            "warnings": [
                {
                    "instrument": instrument,
                    "type": "partial_window",
                    "message": "requested 730 calendar days but only 2 are available",
                    "requested_days": required_days,
                    "available_days": 2,
                    "used_days": 2,
                }
            ],
        }

    service = ResearchService(candle_reader=_fixture_records, window_selector=selector)

    result = asyncio.run(
        service.edge_scan(
            instruments=("GBP_JPY",),
            horizons=(3,),
            algorithm_ids=("clean_level_sweep_reversal",),
            window_days=730,
        )
    )

    assert result["results"]
    assert result["warnings"][0]["type"] == "partial_window"
    assert result["windows"][0]["available_days"] == 2


def test_capture_scan_runs_over_loaded_candles_with_cost_assumptions() -> None:
    service = ResearchService(candle_reader=_fixture_records, window_selector=_fixed_window)

    result = asyncio.run(
        service.capture_scan(
            instrument="EUR_USD",
            horizons=(3,),
            algorithm_ids=("generic_sweep_continuation",),
            spread_pips="0.8",
            slippage_pips="0.1",
        )
    )

    assert result["spread_pips"] == "0.8"
    assert result["slippage_pips"] == "0.1"
    assert result["results"][0]["algorithm_id"] == "generic_sweep_continuation"
    assert result["results"][0]["stats"]["count"] == 1


async def _fixture_records(
    engine: Any, *, instrument: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    return [
        {
            "instrument": instrument,
            "ts": candle.ts.isoformat(),
            "o": str(candle.o),
            "h": str(candle.h),
            "low": str(candle.low),
            "c": str(candle.c),
            "volume": candle.volume,
            "complete": candle.complete,
        }
        for candle in load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")
    ]


class _FakeEngine:
    def connect(self) -> "_FakeConnection":
        return _FakeConnection()


class _FakeConnection:
    async def __aenter__(self) -> "_FakeConnection":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


def test_direction_scan_passes_datetime_bounds_to_book_snapshot_query(monkeypatch) -> None:
    # Regression: the snapshot range query was fed the jsonable window dicts,
    # whose from/to are isoformat strings, and 500ed after minutes of candle
    # loading. The repository requires aware datetimes.
    captured: dict[str, Any] = {}

    async def fake_coverage(connection: Any, *, instruments: tuple[str, ...]) -> list[Any]:
        return [
            {"instrument": "EUR_USD", "book_type": "order", "snapshot_count": 1},
            {"instrument": "EUR_USD", "book_type": "position", "snapshot_count": 1},
        ]

    async def fake_snapshots(
        connection: Any, *, instruments: tuple[str, ...], start: Any, end: Any
    ) -> list[Any]:
        assert isinstance(start, datetime) and start.tzinfo is not None
        assert isinstance(end, datetime) and end.tzinfo is not None
        captured["start"] = start
        captured["end"] = end
        return []

    monkeypatch.setattr("harbor_bot.research.service.get_book_coverage", fake_coverage)
    monkeypatch.setattr("harbor_bot.research.service.list_book_snapshots_range", fake_snapshots)
    service = ResearchService(
        persistence_engine=_FakeEngine(),
        candle_reader=_fixture_records,
        window_selector=_fixed_window,
    )

    result = asyncio.run(service.direction_scan(instruments=("EUR_USD",), window_days=1))

    assert captured["start"] == datetime(2026, 1, 15, tzinfo=UTC)
    assert captured["end"] == datetime(2026, 1, 16, tzinfo=UTC)
    assert result["windows"]


async def _fixed_window(engine: Any, *, instrument: str, required_days: int) -> dict[str, Any]:
    return {"from": datetime(2026, 1, 15, tzinfo=UTC), "to": datetime(2026, 1, 16, tzinfo=UTC)}


async def _no_window(engine: Any, *, instrument: str, required_days: int) -> None:
    return None
