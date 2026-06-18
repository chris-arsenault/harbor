from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.lab.service import LabService
from harbor_bot.paper_engine.models import PaperEngineConfig, PaperVariant, VariantTrade


def test_lab_service_aggregates_study_progress_candidates_variants_and_equity() -> None:
    service = LabService(
        engine=FakeEngine(),
        repository=FakeLabRepository(),
        paper_config=PaperEngineConfig(),
    )

    snapshot = run(service.get_lab_snapshot(study_id=1))

    assert snapshot.study.study_id == 1
    assert snapshot.study.trial_count == 2
    assert [candidate.trial_no for candidate in snapshot.candidates] == [0, 1]
    assert snapshot.candidates[0].in_sample_score == Decimal("1.25000000")
    assert [row.variant.id for row in snapshot.variants.leaderboard] == [10, 11]
    assert snapshot.variants.leaderboard[0].out_of_sample_score == Decimal("1.50000000")
    assert snapshot.variants.equity_curves[1].points[-1].nav == Decimal("10060.00000000")
    assert snapshot.data_separation["optimizer_uses_variant_trades"] is False
    assert snapshot.to_jsonable()["variants"]["leaderboard"][0]["rank"] == 1


def test_lab_service_exposes_paper_only_create_and_retire_actions() -> None:
    repository = FakeLabRepository()
    service = LabService(
        engine=FakeEngine(),
        repository=repository,
        paper_config=PaperEngineConfig(),
    )

    created = run(service.create_paper_variant(trial_id=2, label="paper-trial-1"))
    retired = run(service.retire_paper_variant(variant_id=12))

    assert created.to_jsonable() == {
        "action": "create_paper_variant",
        "variant_id": 12,
        "status": "paper",
    }
    assert retired.to_jsonable() == {
        "action": "retire_paper_variant",
        "variant_id": 12,
        "status": "retired",
    }
    assert repository.created == [(2, "paper-trial-1")]
    assert repository.retired == [12]


def test_lab_service_promotes_one_variant_for_practice_execution() -> None:
    repository = FakeLabRepository()
    service = LabService(
        engine=FakeEngine(),
        repository=repository,
        paper_config=PaperEngineConfig(),
    )

    promoted = run(
        service.promote_variant_for_practice(
            variant_id=10,
            trading_enabled=False,
            open_broker_trade_count=0,
        )
    )

    assert promoted.to_jsonable() == {
        "action": "promote_practice_variant",
        "variant_id": 10,
        "status": "promoted",
    }
    assert repository.promoted == [(10, False, 0)]


def run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)


class FakeConnection:
    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()


class FakeLabRepository:
    def __init__(self) -> None:
        self.created: list[tuple[int, str | None]] = []
        self.retired: list[int] = []
        self.promoted: list[tuple[int, bool, int]] = []
        self.trades = {
            10: (
                _trade(
                    variant_id=10,
                    pnl=Decimal("20"),
                    exit_ts=datetime(2026, 1, 15, 14, 42, tzinfo=UTC),
                ),
            ),
            11: (
                _trade(
                    variant_id=11,
                    pnl=Decimal("60"),
                    exit_ts=datetime(2026, 1, 15, 14, 43, tzinfo=UTC),
                ),
            ),
        }

    async def get_study_with_trials(self, _connection: object, *, study_id: int) -> dict[str, Any]:
        assert study_id == 1
        return {
            "id": 1,
            "created_ts": datetime(2026, 1, 15, 13, 0, tzinfo=UTC),
            "status": "completed",
            "trial_count": 2,
            "candidate_count": 2,
            "paper_variant_count": 2,
            "trials": [
                {
                    "id": 1,
                    "trial_no": 0,
                    "params_json": {"fvg_window": 8},
                    "is_score": Decimal("1.25000000"),
                    "oos_score": Decimal("1.50000000"),
                    "robustness_score": Decimal("1.40000000"),
                    "pruned": False,
                },
                {
                    "id": 2,
                    "trial_no": 1,
                    "params_json": {"fvg_window": 9},
                    "is_score": Decimal("0.75000000"),
                    "oos_score": Decimal("0.90000000"),
                    "robustness_score": Decimal("0.85000000"),
                    "pruned": False,
                },
            ],
        }

    async def list_active_paper_variants(self, _connection: object, *, limit: int = 200):
        return (
            PaperVariant(
                id=10,
                label="candidate-1",
                params={"fvg_window": 8},
                source_trial_id=1,
                trial_scores={
                    "in_sample_score": Decimal("1.25000000"),
                    "out_of_sample_score": Decimal("1.50000000"),
                    "robustness_score": Decimal("1.40000000"),
                },
            ),
            PaperVariant(
                id=11,
                label="paper-trial-1",
                params={"fvg_window": 9},
                source_trial_id=2,
                trial_scores={
                    "in_sample_score": Decimal("0.75000000"),
                    "out_of_sample_score": Decimal("0.90000000"),
                    "robustness_score": Decimal("0.85000000"),
                },
            ),
        )

    async def list_variant_trades(
        self,
        _connection: object,
        *,
        variant_id: int,
        limit: int,
    ) -> tuple[VariantTrade, ...]:
        return self.trades[variant_id][-limit:]

    async def create_paper_variant_from_trial(
        self,
        _engine: object,
        *,
        trial_id: int,
        label: str | None = None,
    ) -> int:
        self.created.append((trial_id, label))
        return 12

    async def retire_paper_variant(self, _engine: object, *, variant_id: int) -> bool:
        self.retired.append(variant_id)
        return True

    async def promote_paper_variant(
        self,
        _engine: object,
        *,
        variant_id: int,
        trading_enabled: bool = False,
        open_broker_trade_count: int = 0,
    ) -> bool:
        self.promoted.append((variant_id, trading_enabled, open_broker_trade_count))
        return True


def _trade(
    *,
    variant_id: int,
    pnl: Decimal,
    exit_ts: datetime,
) -> VariantTrade:
    return VariantTrade(
        id=variant_id + 100,
        variant_id=variant_id,
        side="long",
        units=Decimal("10000"),
        entry_price=Decimal("1.1010"),
        entry_ts=datetime(2026, 1, 15, 14, 36, tzinfo=UTC),
        exit_price=Decimal("1.1070"),
        exit_ts=exit_ts,
        pnl=pnl,
        r_multiple=Decimal("2"),
        exit_reason="take_profit",
    )
