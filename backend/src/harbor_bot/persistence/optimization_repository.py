from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from harbor_bot.optimizer.models import CandidateVariant, OptimizationStatus, TrialRecord
from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.schema import opt_studies, opt_trials, variants


async def append_optimization_run(
    engine: AsyncEngine,
    *,
    search_space_json: Mapping[str, Any],
    walkforward_json: Mapping[str, Any],
    status: OptimizationStatus,
    trials: tuple[TrialRecord, ...],
    candidates: tuple[CandidateVariant, ...],
) -> int:
    async with transaction(engine) as connection:
        study_id = await create_optimization_study(
            connection,
            search_space_json=search_space_json,
            walkforward_json=walkforward_json,
            status=status,
        )
        trial_ids: dict[int, int] = {}
        for trial in trials:
            trial_ids[trial.trial_no] = await append_optimization_trial(
                connection,
                study_id=study_id,
                trial=trial,
            )
        for candidate in candidates:
            await append_candidate_variant(
                connection,
                candidate=candidate,
                source_trial_id=trial_ids[candidate.source_trial_no],
            )
        return study_id


async def create_optimization_study(
    connection: AsyncConnection,
    *,
    search_space_json: Mapping[str, Any],
    walkforward_json: Mapping[str, Any],
    status: OptimizationStatus,
) -> int:
    result = await connection.execute(
        insert(opt_studies)
        .values(
            search_space_json=dict(search_space_json),
            walkforward_json=dict(walkforward_json),
            status=OptimizationStatus(status).value,
        )
        .returning(opt_studies.c.id)
    )
    return int(result.scalar_one())


async def append_optimization_trial(
    connection: AsyncConnection,
    *,
    study_id: int,
    trial: TrialRecord,
) -> int:
    result = await connection.execute(
        insert(opt_trials)
        .values(
            study_id=study_id,
            trial_no=trial.trial_no,
            params_json=trial.params,
            is_score=trial.score.in_sample_score,
            oos_score=trial.score.out_of_sample_score,
            robustness_score=trial.score.robustness_score,
            pruned=trial.pruned,
        )
        .returning(opt_trials.c.id)
    )
    return int(result.scalar_one())


async def append_candidate_variant(
    connection: AsyncConnection,
    *,
    candidate: CandidateVariant,
    source_trial_id: int,
) -> int:
    result = await connection.execute(
        insert(variants)
        .values(
            label=candidate.label,
            params_json=candidate.params,
            source_trial_id=source_trial_id,
            status=candidate.status,
        )
        .returning(variants.c.id)
    )
    return int(result.scalar_one())


async def get_optimization_study(
    connection: AsyncConnection,
    *,
    study_id: int,
) -> dict[str, Any] | None:
    study_result = await connection.execute(
        select(
            opt_studies.c.id,
            opt_studies.c.created_ts,
            opt_studies.c.search_space_json,
            opt_studies.c.walkforward_json,
            opt_studies.c.status,
        ).where(opt_studies.c.id == study_id)
    )
    study = study_result.mappings().first()
    if study is None:
        return None

    trial_result = await connection.execute(
        select(
            opt_trials.c.id,
            opt_trials.c.study_id,
            opt_trials.c.trial_no,
            opt_trials.c.params_json,
            opt_trials.c.is_score,
            opt_trials.c.oos_score,
            opt_trials.c.robustness_score,
            opt_trials.c.pruned,
        )
        .where(opt_trials.c.study_id == study_id)
        .order_by(opt_trials.c.trial_no)
    )
    variant_result = await connection.execute(
        select(
            variants.c.id,
            variants.c.label,
            variants.c.params_json,
            variants.c.source_trial_id,
            variants.c.status,
        )
        .join(opt_trials, variants.c.source_trial_id == opt_trials.c.id)
        .where(opt_trials.c.study_id == study_id)
        .order_by(variants.c.id)
    )
    data = dict(study)
    data["trials"] = [dict(row) for row in trial_result.mappings()]
    data["variants"] = [dict(row) for row in variant_result.mappings()]
    return data


def decimal_score(value: str) -> Decimal:
    return Decimal(value)
