import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event

from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationStatus,
    TrialRecord,
    TrialScore,
)
from harbor_bot.paper_engine.models import VariantTrade
from harbor_bot.persistence.database import create_engine
from harbor_bot.persistence.optimization_repository import append_optimization_run
from harbor_bot.persistence.variant_repository import (
    append_variant_trades,
    compute_leaderboard_rows,
    compute_variant_stats,
    create_paper_variant_from_trial,
    derive_equity_curve,
    get_promoted_variant,
    get_study_with_trials,
    list_active_paper_variants,
    list_study_summaries,
    list_variant_trades,
    promote_paper_variant,
    retire_paper_variant,
)
from harbor_bot.settings import Settings


def test_variant_repository_round_trips_paper_variants_and_trades(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_variant_repository_round_trip(postgres_url))


async def _assert_variant_repository_round_trip(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        study_id = await _seed_study(engine)

        async with engine.connect() as connection:
            study = await get_study_with_trials(connection, study_id=study_id)
        assert study is not None
        assert study["trial_count"] == 2
        assert study["candidate_count"] == 1
        source_trial_id = study["trials"][1]["id"]

        variant_id = await create_paper_variant_from_trial(
            engine,
            trial_id=source_trial_id,
            label="paper-trial-1",
        )

        async with engine.connect() as connection:
            active = await list_active_paper_variants(connection)

        variant = next(item for item in active if item.id == variant_id)
        assert variant.label == "paper-trial-1"
        assert variant.params == {"fvg_window": 9}
        assert variant.trial_scores == {
            "in_sample_score": Decimal("0.75000000"),
            "out_of_sample_score": Decimal("0.90000000"),
            "robustness_score": Decimal("0.85000000"),
        }

        trade = VariantTrade(
            variant_id=variant_id,
            side="long",
            units=Decimal("10000"),
            entry_price=Decimal("1.1010"),
            entry_ts=datetime(2026, 1, 15, 14, 36, tzinfo=UTC),
            exit_price=Decimal("1.1070"),
            exit_ts=datetime(2026, 1, 15, 14, 42, tzinfo=UTC),
            pnl=Decimal("60"),
            r_multiple=Decimal("2"),
            exit_reason="take_profit",
        )
        trade_ids = await append_variant_trades(engine, (trade,))
        assert len(trade_ids) == 1

        async with engine.connect() as connection:
            stored_trades = await list_variant_trades(connection, variant_id=variant_id)
        assert stored_trades[0].id == trade_ids[0]
        assert stored_trades[0].pnl == Decimal("60.00000000")

        equity = derive_equity_curve(
            variant_id=variant_id,
            trades=stored_trades,
            initial_nav=Decimal("10000"),
        )
        stats = compute_variant_stats(
            variant_id=variant_id,
            trades=stored_trades,
            initial_nav=Decimal("10000"),
            drawdown_floor=Decimal("1"),
        )
        rows = compute_leaderboard_rows(
            variants=active,
            trades_by_variant={variant_id: stored_trades},
            initial_nav=Decimal("10000"),
            drawdown_floor=Decimal("1"),
            min_trades=0,
        )

        assert equity[0].nav == Decimal("10060.00000000")
        assert stats.trade_count == 1
        assert stats.live_forward_score == Decimal("60.00000000")
        created_row = next(row for row in rows if row.variant.id == variant_id)
        assert rows[0].out_of_sample_score == Decimal("1.50000000")
        assert created_row.out_of_sample_score == Decimal("0.90000000")
        assert created_row.stats.live_forward_score == Decimal("60.00000000")

        assert await retire_paper_variant(engine, variant_id=variant_id) is True
        async with engine.connect() as connection:
            active_after_retire = await list_active_paper_variants(connection)
            trades_after_retire = await list_variant_trades(connection, variant_id=variant_id)

        assert all(item.id != variant_id for item in active_after_retire)
        assert trades_after_retire == stored_trades

        promoted_id = active_after_retire[0].id
        assert await promote_paper_variant(engine, variant_id=promoted_id) is True
        async with engine.connect() as connection:
            promoted = await get_promoted_variant(connection)
            active_after_promote = await list_active_paper_variants(connection)
        assert promoted is not None
        assert promoted["id"] == promoted_id
        assert promoted["status"] == "promoted"
        assert promoted["params"] == {"fvg_window": 8}
        assert all(item.id != promoted_id for item in active_after_promote)

        replacement_id = await create_paper_variant_from_trial(
            engine,
            trial_id=source_trial_id,
            label="replacement-paper",
        )
        assert await promote_paper_variant(engine, variant_id=replacement_id) is True
        async with engine.connect() as connection:
            replacement = await get_promoted_variant(connection)
            active_after_replacement = await list_active_paper_variants(connection)
        assert replacement is not None
        assert replacement["id"] == replacement_id
        assert any(item.id == promoted_id for item in active_after_replacement)

        with pytest.raises(ValueError, match="retired"):
            await promote_paper_variant(engine, variant_id=variant_id)
        with pytest.raises(ValueError, match="trading is enabled"):
            await promote_paper_variant(
                engine,
                variant_id=promoted_id,
                trading_enabled=True,
            )
        with pytest.raises(ValueError, match="open broker trades"):
            await promote_paper_variant(
                engine,
                variant_id=promoted_id,
                open_broker_trade_count=1,
            )
    finally:
        await engine.dispose()


def test_study_queries_do_not_read_variant_trades(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_study_queries_avoid_variant_trades(postgres_url))


async def _assert_study_queries_avoid_variant_trades(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    statements: list[str] = []

    def collect_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    try:
        study_id = await _seed_study(engine)
        event.listen(engine.sync_engine, "before_cursor_execute", collect_statement)
        try:
            async with engine.connect() as connection:
                summaries = await list_study_summaries(connection)
                study = await get_study_with_trials(connection, study_id=study_id)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", collect_statement)

        assert summaries[0]["study_id"] == study_id
        assert study is not None
        assert study["id"] == study_id
        assert not any("variant_trades" in statement for statement in statements)
    finally:
        await engine.dispose()


async def _seed_study(engine) -> int:
    config = load_optimizer_config()
    return await append_optimization_run(
        engine,
        search_space_json=config.search_space.to_jsonable(),
        walkforward_json=config.walk_forward.to_jsonable(),
        status=OptimizationStatus.COMPLETED,
        trials=(
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
                    in_sample_score=Decimal("0.75"),
                    out_of_sample_score=Decimal("0.9"),
                    robustness_score=Decimal("0.85"),
                ),
            ),
        ),
        candidates=(
            CandidateVariant(
                label="candidate-1",
                params={"fvg_window": 8},
                source_trial_no=0,
            ),
        ),
    )


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
