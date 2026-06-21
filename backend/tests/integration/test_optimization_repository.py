import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationStatus,
    TrialRecord,
    TrialScore,
)
from harbor_bot.persistence.database import create_engine
from harbor_bot.persistence.optimization_repository import (
    append_optimization_run,
    complete_optimization_run,
    fail_optimization_run,
    get_optimization_study,
    start_optimization_run,
)
from harbor_bot.persistence.schema import opt_studies, opt_trials, variants
from harbor_bot.settings import Settings


def test_optimization_study_trials_and_variants_persist_transactionally(
    postgres_url: str,
) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_optimization_round_trip(postgres_url))


def test_optimization_run_rolls_back_when_variant_insert_fails(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_optimization_rollback(postgres_url))


def test_queued_optimization_run_transitions_to_completed_and_failed(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_queued_optimization_transitions(postgres_url))


async def _assert_optimization_round_trip(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    config = load_optimizer_config()
    try:
        study_id = await append_optimization_run(
            engine,
            search_space_json=config.search_space.to_jsonable(),
            walkforward_json=config.walk_forward.to_jsonable(),
            status=OptimizationStatus.COMPLETED,
            trials=_trials(),
            candidates=(
                CandidateVariant(
                    label="candidate-1",
                    params={"fvg_window": 8},
                    source_trial_no=0,
                ),
            ),
        )

        async with engine.connect() as connection:
            stored = await get_optimization_study(connection, study_id=study_id)

        assert stored is not None
        assert stored["id"] == study_id
        assert stored["status"] == "completed"
        assert stored["search_space_json"] == config.search_space.to_jsonable()
        assert stored["walkforward_json"] == config.walk_forward.to_jsonable()
        assert len(stored["trials"]) == 2
        assert stored["trials"][0]["trial_no"] == 0
        assert stored["trials"][0]["params_json"] == {"fvg_window": 8}
        assert stored["trials"][0]["is_score"] == Decimal("1.25000000")
        assert stored["trials"][0]["oos_score"] == Decimal("1.50000000")
        assert stored["trials"][0]["robustness_score"] == Decimal("1.40000000")
        assert stored["trials"][0]["status"] == "completed"
        assert stored["trials"][0]["failure_reason"] is None
        assert stored["trials"][1]["pruned"] is True
        assert stored["trials"][1]["status"] == "pruned"
        assert (
            stored["trials"][1]["failure_reason"] == "in-sample trade count below configured floor"
        )
        assert stored["variants"][0]["label"] == "candidate-1"
        assert stored["variants"][0]["status"] == "paper"
    finally:
        await engine.dispose()


async def _assert_queued_optimization_transitions(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    config = load_optimizer_config()
    try:
        completed_study_id = await start_optimization_run(
            engine,
            search_space_json=config.search_space.to_jsonable(),
            walkforward_json={"queued": True},
        )
        failed_study_id = await start_optimization_run(
            engine,
            search_space_json=config.search_space.to_jsonable(),
            walkforward_json={"queued": True},
        )

        async with engine.connect() as connection:
            queued = await get_optimization_study(connection, study_id=completed_study_id)
        assert queued is not None
        assert queued["status"] == "running"
        assert queued["trials"] == []

        await complete_optimization_run(
            engine,
            study_id=completed_study_id,
            search_space_json=config.search_space.to_jsonable(),
            walkforward_json={"completed": True},
            trials=_trials(),
            candidates=(
                CandidateVariant(
                    label="candidate-1",
                    params={"fvg_window": 8},
                    source_trial_no=0,
                ),
            ),
        )
        await fail_optimization_run(
            engine,
            study_id=failed_study_id,
            search_space_json=config.search_space.to_jsonable(),
            walkforward_json={"failure_reason": "optimizer failed"},
        )

        async with engine.connect() as connection:
            completed = await get_optimization_study(connection, study_id=completed_study_id)
            failed = await get_optimization_study(connection, study_id=failed_study_id)

        assert completed is not None
        assert completed["status"] == "completed"
        assert completed["walkforward_json"] == {"completed": True}
        assert len(completed["trials"]) == 2
        assert completed["variants"][0]["label"] == "candidate-1"
        assert failed is not None
        assert failed["status"] == "failed"
        assert failed["walkforward_json"] == {"failure_reason": "optimizer failed"}
        assert failed["trials"] == []
    finally:
        await engine.dispose()


async def _assert_optimization_rollback(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    config = load_optimizer_config()
    bad_candidate = CandidateVariant(
        label="candidate-1",
        params={"fvg_window": 8},
        source_trial_no=0,
    )
    object.__setattr__(bad_candidate, "status", "invalid")
    try:
        with pytest.raises(IntegrityError):
            await append_optimization_run(
                engine,
                search_space_json=config.search_space.to_jsonable(),
                walkforward_json=config.walk_forward.to_jsonable(),
                status=OptimizationStatus.COMPLETED,
                trials=_trials(),
                candidates=(bad_candidate,),
            )

        async with engine.connect() as connection:
            study_count = await connection.scalar(select(func.count()).select_from(opt_studies))
            trial_count = await connection.scalar(select(func.count()).select_from(opt_trials))
            variant_count = await connection.scalar(select(func.count()).select_from(variants))

        assert study_count == 0
        assert trial_count == 0
        assert variant_count == 0
    finally:
        await engine.dispose()


def _trials() -> tuple[TrialRecord, ...]:
    return (
        TrialRecord(
            trial_no=0,
            params={"fvg_window": 8},
            score=TrialScore(
                in_sample_score=Decimal("1.25"),
                out_of_sample_score=Decimal("1.5"),
                robustness_score=Decimal("1.4"),
            ),
        ),
        TrialRecord(
            trial_no=1,
            params={"fvg_window": 9},
            score=TrialScore(
                in_sample_score=Decimal("0"),
                out_of_sample_score=Decimal("0"),
                robustness_score=Decimal("0"),
            ),
            pruned=True,
            status=OptimizationStatus.PRUNED,
            failure_reason="in-sample trade count below configured floor",
        ),
    )


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
