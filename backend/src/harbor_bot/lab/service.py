from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.lab.models import (
    CandidateScatterPoint,
    LabActionResult,
    LabSnapshot,
    LabVariantOverview,
    VariantEquityCurve,
)
from harbor_bot.paper_engine.models import LabStudySnapshot, PaperEngineConfig, PaperVariant
from harbor_bot.persistence import variant_repository


class LabService:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        repository: Any = variant_repository,
        paper_config: PaperEngineConfig,
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._paper_config = paper_config

    async def get_lab_snapshot(self, *, study_id: int) -> LabSnapshot | None:
        async with self._engine.connect() as connection:
            study = await self._repository.get_study_with_trials(connection, study_id=study_id)
            if study is None:
                return None
            active_variants = await self._repository.list_active_paper_variants(
                connection,
                limit=self._paper_config.max_lab_rows,
            )
            study_trial_ids = {int(trial["id"]) for trial in study["trials"]}
            variants = tuple(
                variant for variant in active_variants if variant.source_trial_id in study_trial_ids
            )
            trades_by_variant = {
                variant.id: await self._repository.list_variant_trades(
                    connection,
                    variant_id=variant.id,
                    limit=self._paper_config.max_lab_rows,
                )
                for variant in variants
            }

        overview = self._variant_overview_from_trades(
            variants=variants,
            trades_by_variant=trades_by_variant,
        )
        return LabSnapshot(
            study=LabStudySnapshot(
                study_id=int(study["id"]),
                status=study["status"],
                trial_count=int(study["trial_count"]),
                candidate_count=int(study["candidate_count"]),
                paper_variant_count=int(study["paper_variant_count"]),
                created_ts=study["created_ts"],
            ),
            candidates=tuple(_candidate(trial) for trial in study["trials"]),
            variants=overview,
            data_separation=_data_separation(),
        )

    async def get_variant_overview(self) -> LabVariantOverview:
        async with self._engine.connect() as connection:
            variants = await self._repository.list_active_paper_variants(
                connection,
                limit=self._paper_config.max_lab_rows,
            )
            trades_by_variant = {
                variant.id: await self._repository.list_variant_trades(
                    connection,
                    variant_id=variant.id,
                    limit=self._paper_config.max_lab_rows,
                )
                for variant in variants
            }
        return self._variant_overview_from_trades(
            variants=variants,
            trades_by_variant=trades_by_variant,
        )

    async def create_paper_variant(
        self,
        *,
        trial_id: int,
        label: str | None = None,
    ) -> LabActionResult:
        variant_id = await self._repository.create_paper_variant_from_trial(
            self._engine,
            trial_id=trial_id,
            label=label,
        )
        return LabActionResult(
            action="create_paper_variant",
            variant_id=variant_id,
            status="paper",
        )

    async def retire_paper_variant(self, *, variant_id: int) -> LabActionResult:
        retired = await self._repository.retire_paper_variant(
            self._engine,
            variant_id=variant_id,
        )
        return LabActionResult(
            action="retire_paper_variant",
            variant_id=variant_id,
            status="retired" if retired else "not_found",
        )

    async def promote_variant_for_practice(
        self,
        *,
        variant_id: int,
        trading_enabled: bool = False,
        open_broker_trade_count: int = 0,
    ) -> LabActionResult:
        promoted = await self._repository.promote_paper_variant(
            self._engine,
            variant_id=variant_id,
            trading_enabled=trading_enabled,
            open_broker_trade_count=open_broker_trade_count,
        )
        return LabActionResult(
            action="promote_practice_variant",
            variant_id=variant_id,
            status="promoted" if promoted else "not_found",
        )

    def _variant_overview_from_trades(
        self,
        *,
        variants: tuple[PaperVariant, ...],
        trades_by_variant: dict[int, Any],
    ) -> LabVariantOverview:
        equity_curves = tuple(
            VariantEquityCurve(
                variant_id=variant.id,
                points=variant_repository.derive_equity_curve(
                    variant_id=variant.id,
                    trades=trades_by_variant.get(variant.id, ()),
                    initial_nav=self._paper_config.initial_nav,
                ),
            )
            for variant in variants
        )
        leaderboard = variant_repository.compute_leaderboard_rows(
            variants=variants,
            trades_by_variant=trades_by_variant,
            initial_nav=self._paper_config.initial_nav,
            drawdown_floor=self._paper_config.live_forward_drawdown_floor,
            min_trades=self._paper_config.leaderboard_min_trades,
        )
        return LabVariantOverview(
            variants=variants,
            leaderboard=leaderboard,
            equity_curves=equity_curves,
            data_separation=_data_separation(),
        )


def _candidate(row: dict[str, Any]) -> CandidateScatterPoint:
    return CandidateScatterPoint(
        trial_id=int(row["id"]),
        trial_no=int(row["trial_no"]),
        params=dict(row["params_json"]),
        in_sample_score=row["is_score"],
        out_of_sample_score=row["oos_score"],
        robustness_score=row["robustness_score"],
        pruned=bool(row["pruned"]),
        status=str(row.get("status") or ("pruned" if row["pruned"] else "completed")),
        failure_reason=row.get("failure_reason"),
    )


def _data_separation() -> dict[str, Any]:
    return {
        "optimizer_reads": ["candles", "opt_studies", "opt_trials", "variants"],
        "paper_forward_reads": ["variants", "closed_live_candles"],
        "live_forward_reads": ["variant_trades"],
        "optimizer_uses_variant_trades": False,
        "broker_state_used": False,
        "oanda_streams_opened_by_lab": False,
        "paper_actions_only": True,
    }
