from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.lab.models import (
    CandidateScatterPoint,
    LabActionResult,
    LabSnapshot,
    LabVariantOverview,
)
from harbor_bot.paper_engine.models import LabStudySnapshot, PaperVariant


def test_optimize_endpoint_starts_optimizer_through_injected_service() -> None:
    optimizer = FakeOptimizerService()
    client = TestClient(create_app(optimizer_service=optimizer, lab_service=FakeLabService()))

    response = client.post("/api/optimize", json={"fixture": "clean_signal_day.json"})

    assert response.status_code == 200
    assert response.json()["study_id"] == 42
    assert optimizer.started_payloads == [{"fixture": "clean_signal_day.json"}]


def test_lab_endpoints_read_study_variants_and_paper_only_actions() -> None:
    lab = FakeLabService()
    client = TestClient(create_app(optimizer_service=FakeOptimizerService(), lab_service=lab))

    study = client.get("/api/optimize/1")
    variants = client.get("/api/variants")
    created = client.post("/api/variants", json={"trial_id": 2, "label": "paper-trial-1"})
    retired = client.post("/api/variants/7/retire")
    promote = client.post("/api/variants/7/promote")

    assert study.status_code == 200
    assert study.json()["study"]["study_id"] == 1
    assert study.json()["candidates"][0]["trial_no"] == 0
    assert variants.status_code == 200
    assert variants.json()["variants"][0]["status"] == "paper"
    assert created.json() == {
        "action": "create_paper_variant",
        "variant_id": 7,
        "status": "paper",
    }
    assert retired.json() == {
        "action": "retire_paper_variant",
        "variant_id": 7,
        "status": "retired",
    }
    assert promote.json() == {
        "action": "promote_practice_variant",
        "variant_id": 7,
        "status": "promoted",
    }
    assert lab.created == [(2, "paper-trial-1")]
    assert lab.retired == [7]
    assert lab.promoted == [7]


def test_get_optimize_returns_404_for_unknown_study() -> None:
    client = TestClient(
        create_app(optimizer_service=FakeOptimizerService(), lab_service=FakeLabService())
    )

    response = client.get("/api/optimize/404")

    assert response.status_code == 404
    assert response.json() == {"detail": "optimization study not found"}


class FakeOptimizerService:
    def __init__(self) -> None:
        self.started_payloads: list[dict[str, Any]] = []

    async def start_optimization(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.started_payloads.append(payload)
        return {
            "study_id": 42,
            "status": "completed",
            "trials": [],
            "candidates": [],
            "data_separation": {"variant_trades_used": False},
        }


class FakeLabService:
    def __init__(self) -> None:
        self.created: list[tuple[int, str | None]] = []
        self.retired: list[int] = []
        self.promoted: list[int] = []

    async def get_lab_snapshot(self, *, study_id: int) -> LabSnapshot | None:
        if study_id == 404:
            return None
        return LabSnapshot(
            study=LabStudySnapshot(
                study_id=1,
                status="completed",
                trial_count=1,
                candidate_count=1,
                paper_variant_count=1,
                created_ts=datetime(2026, 1, 15, 13, 0, tzinfo=UTC),
            ),
            candidates=(
                CandidateScatterPoint(
                    trial_id=2,
                    trial_no=0,
                    params={"fvg_window": 8},
                    in_sample_score=Decimal("1.25"),
                    out_of_sample_score=Decimal("1.5"),
                    robustness_score=Decimal("1.4"),
                    pruned=False,
                ),
            ),
            variants=await self.get_variant_overview(),
            data_separation={"optimizer_uses_variant_trades": False},
        )

    async def get_variant_overview(self) -> LabVariantOverview:
        return LabVariantOverview(
            variants=(
                PaperVariant(
                    id=7,
                    label="paper-trial-1",
                    params={"fvg_window": 8},
                    source_trial_id=2,
                ),
            ),
            leaderboard=(),
            equity_curves=(),
            data_separation={"optimizer_uses_variant_trades": False},
        )

    async def create_paper_variant(
        self,
        *,
        trial_id: int,
        label: str | None = None,
    ) -> LabActionResult:
        self.created.append((trial_id, label))
        return LabActionResult(
            action="create_paper_variant",
            variant_id=7,
            status="paper",
        )

    async def retire_paper_variant(self, *, variant_id: int) -> LabActionResult:
        self.retired.append(variant_id)
        return LabActionResult(
            action="retire_paper_variant",
            variant_id=variant_id,
            status="retired",
        )

    async def promote_variant_for_practice(
        self,
        *,
        variant_id: int,
        trading_enabled: bool = False,
        open_broker_trade_count: int = 0,
    ) -> LabActionResult:
        self.promoted.append(variant_id)
        assert trading_enabled is False
        assert open_broker_trade_count == 0
        return LabActionResult(
            action="promote_practice_variant",
            variant_id=variant_id,
            status="promoted",
        )
