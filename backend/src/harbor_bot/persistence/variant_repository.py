from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import distinct, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from harbor_bot.paper_engine.models import (
    PaperVariant,
    VariantEquityPoint,
    VariantLeaderboardRow,
    VariantStats,
    VariantTrade,
)
from harbor_bot.persistence.database import transaction
from harbor_bot.persistence.schema import opt_studies, opt_trials, variant_trades, variants


async def list_study_summaries(
    connection: AsyncConnection,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    best_trial_id = (
        select(opt_trials.c.id)
        .select_from(opt_trials)
        .where(opt_trials.c.study_id == opt_studies.c.id, opt_trials.c.pruned.is_(False))
        .order_by(
            opt_trials.c.oos_score.desc(),
            opt_trials.c.robustness_score.desc(),
            opt_trials.c.id,
        )
        .correlate(opt_studies)
        .limit(1)
        .scalar_subquery()
    )
    result = await connection.execute(
        select(
            opt_studies.c.id.label("study_id"),
            opt_studies.c.created_ts,
            opt_studies.c.status,
            opt_studies.c.search_space_json,
            opt_studies.c.walkforward_json,
            best_trial_id.label("best_trial_id"),
            func.count(distinct(opt_trials.c.id)).label("trial_count"),
            func.count(distinct(variants.c.id)).label("candidate_count"),
        )
        .select_from(
            opt_studies.outerjoin(opt_trials, opt_trials.c.study_id == opt_studies.c.id).outerjoin(
                variants,
                variants.c.source_trial_id == opt_trials.c.id,
            )
        )
        .group_by(
            opt_studies.c.id,
            opt_studies.c.created_ts,
            opt_studies.c.status,
            opt_studies.c.search_space_json,
            opt_studies.c.walkforward_json,
        )
        .order_by(opt_studies.c.created_ts.desc(), opt_studies.c.id.desc())
        .limit(limit)
    )
    return [dict(row) for row in result.mappings()]


async def get_variant_detail(
    connection: AsyncConnection,
    *,
    variant_id: int,
    initial_nav: Decimal,
    limit: int = 200,
) -> dict[str, Any] | None:
    result = await connection.execute(
        select(
            variants.c.id,
            variants.c.label,
            variants.c.params_json,
            variants.c.source_trial_id,
            variants.c.status,
            opt_trials.c.is_score,
            opt_trials.c.oos_score,
            opt_trials.c.robustness_score,
        )
        .join(opt_trials, variants.c.source_trial_id == opt_trials.c.id)
        .where(variants.c.id == variant_id)
    )
    row = result.mappings().first()
    if row is None:
        return None

    variant_trades_for_detail = await list_variant_trades(
        connection,
        variant_id=variant_id,
        limit=limit,
    )
    equity_curve = derive_equity_curve(
        variant_id=variant_id,
        trades=variant_trades_for_detail,
        initial_nav=initial_nav,
    )
    return {
        "variant": {
            "id": int(row["id"]),
            "label": row["label"],
            "params": dict(row["params_json"]),
            "source_trial_id": int(row["source_trial_id"]),
            "status": row["status"],
            "trial_scores": {
                "in_sample_score": row["is_score"],
                "out_of_sample_score": row["oos_score"],
                "robustness_score": row["robustness_score"],
            },
        },
        "trades": [trade.to_jsonable() for trade in variant_trades_for_detail],
        "equity_curve": [point.to_jsonable() for point in equity_curve],
    }


async def get_study_with_trials(
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
            opt_trials.c.status,
            opt_trials.c.failure_reason,
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

    trials = [dict(row) for row in trial_result.mappings()]
    candidate_variants = [dict(row) for row in variant_result.mappings()]
    data = dict(study)
    data["trial_count"] = len(trials)
    data["candidate_count"] = len(candidate_variants)
    data["paper_variant_count"] = sum(
        1 for variant in candidate_variants if variant["status"] == "paper"
    )
    data["trials"] = trials
    data["variants"] = candidate_variants
    return data


async def list_active_paper_variants(
    connection: AsyncConnection,
    *,
    limit: int = 200,
) -> tuple[PaperVariant, ...]:
    result = await connection.execute(
        select(
            variants.c.id,
            variants.c.label,
            variants.c.params_json,
            variants.c.source_trial_id,
            variants.c.status,
            opt_trials.c.is_score,
            opt_trials.c.oos_score,
            opt_trials.c.robustness_score,
        )
        .join(opt_trials, variants.c.source_trial_id == opt_trials.c.id)
        .where(variants.c.status == "paper")
        .order_by(variants.c.id)
        .limit(limit)
    )
    return tuple(_paper_variant_from_row(row) for row in result.mappings())


async def create_paper_variant_from_trial(
    engine: AsyncEngine,
    *,
    trial_id: int,
    label: str | None = None,
) -> int:
    async with transaction(engine) as connection:
        trial_result = await connection.execute(
            select(
                opt_trials.c.id,
                opt_trials.c.study_id,
                opt_trials.c.trial_no,
                opt_trials.c.params_json,
            ).where(opt_trials.c.id == trial_id)
        )
        trial = trial_result.mappings().first()
        if trial is None:
            msg = f"optimizer trial {trial_id} was not found"
            raise ValueError(msg)

        result = await connection.execute(
            insert(variants)
            .values(
                label=label or f"study-{trial['study_id']}-trial-{trial['trial_no']}",
                params_json=dict(trial["params_json"]),
                source_trial_id=trial["id"],
                status="paper",
            )
            .returning(variants.c.id)
        )
        return int(result.scalar_one())


async def retire_paper_variant(
    engine: AsyncEngine,
    *,
    variant_id: int,
) -> bool:
    async with transaction(engine) as connection:
        result = await connection.execute(
            update(variants)
            .where(variants.c.id == variant_id, variants.c.status == "paper")
            .values(status="retired")
            .returning(variants.c.id)
        )
        return result.scalar_one_or_none() is not None


async def promote_paper_variant(
    engine: AsyncEngine,
    *,
    variant_id: int,
    trading_enabled: bool = False,
    open_broker_trade_count: int = 0,
) -> bool:
    if trading_enabled:
        msg = "cannot promote a practice variant while trading is enabled"
        raise ValueError(msg)
    if open_broker_trade_count > 0:
        msg = "cannot promote a practice variant while open broker trades exist"
        raise ValueError(msg)

    async with transaction(engine) as connection:
        result = await connection.execute(
            select(variants.c.id, variants.c.status).where(variants.c.id == variant_id)
        )
        variant = result.mappings().first()
        if variant is None:
            msg = f"variant {variant_id} was not found"
            raise ValueError(msg)
        if variant["status"] == "retired":
            msg = "cannot promote a retired variant"
            raise ValueError(msg)
        if variant["status"] not in {"paper", "promoted"}:
            msg = f"cannot promote variant with status {variant['status']}"
            raise ValueError(msg)

        await connection.execute(
            update(variants)
            .where(variants.c.status == "promoted", variants.c.id != variant_id)
            .values(status="paper")
        )
        update_result = await connection.execute(
            update(variants)
            .where(variants.c.id == variant_id)
            .values(status="promoted")
            .returning(variants.c.id)
        )
        return update_result.scalar_one_or_none() is not None


async def get_promoted_variant(connection: AsyncConnection) -> dict[str, Any] | None:
    result = await connection.execute(
        select(
            variants.c.id,
            variants.c.label,
            variants.c.params_json,
            variants.c.source_trial_id,
            variants.c.status,
            opt_trials.c.is_score,
            opt_trials.c.oos_score,
            opt_trials.c.robustness_score,
        )
        .join(opt_trials, variants.c.source_trial_id == opt_trials.c.id)
        .where(variants.c.status == "promoted")
        .order_by(variants.c.id)
        .limit(1)
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "label": row["label"],
        "params": dict(row["params_json"]),
        "source_trial_id": int(row["source_trial_id"]),
        "status": row["status"],
        "trial_scores": {
            "in_sample_score": row["is_score"],
            "out_of_sample_score": row["oos_score"],
            "robustness_score": row["robustness_score"],
        },
    }


async def append_variant_trades(
    engine: AsyncEngine,
    trades: Iterable[VariantTrade],
) -> tuple[int, ...]:
    async with transaction(engine) as connection:
        trade_ids: list[int] = []
        for trade in trades:
            result = await connection.execute(
                insert(variant_trades)
                .values(**trade.to_persistence_row())
                .returning(variant_trades.c.id)
            )
            trade_ids.append(int(result.scalar_one()))
        return tuple(trade_ids)


async def list_variant_trades(
    connection: AsyncConnection,
    *,
    variant_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
) -> tuple[VariantTrade, ...]:
    conditions = [variant_trades.c.variant_id == variant_id]
    if start is not None:
        conditions.append(variant_trades.c.exit_ts >= start)
    if end is not None:
        conditions.append(variant_trades.c.exit_ts <= end)

    result = await connection.execute(
        select(
            variant_trades.c.id,
            variant_trades.c.variant_id,
            variant_trades.c.side,
            variant_trades.c.units,
            variant_trades.c.entry_price,
            variant_trades.c.entry_ts,
            variant_trades.c.exit_price,
            variant_trades.c.exit_ts,
            variant_trades.c.pnl,
            variant_trades.c.r_multiple,
            variant_trades.c.exit_reason,
        )
        .where(*conditions)
        .order_by(variant_trades.c.exit_ts, variant_trades.c.id)
        .limit(limit)
    )
    return tuple(_variant_trade_from_row(row) for row in result.mappings())


def derive_equity_curve(
    *,
    variant_id: int,
    trades: Sequence[VariantTrade],
    initial_nav: Decimal,
) -> tuple[VariantEquityPoint, ...]:
    nav = Decimal(str(initial_nav))
    high_water = nav
    points: list[VariantEquityPoint] = []
    for trade in _ordered_trades(trades):
        nav += trade.pnl
        high_water = max(high_water, nav)
        points.append(
            VariantEquityPoint(
                variant_id=variant_id,
                ts=trade.exit_ts,
                nav=nav,
                drawdown=high_water - nav,
            )
        )
    return tuple(points)


def compute_variant_stats(
    *,
    variant_id: int,
    trades: Sequence[VariantTrade],
    initial_nav: Decimal,
    drawdown_floor: Decimal,
) -> VariantStats:
    ordered = _ordered_trades(trades)
    if not ordered:
        return VariantStats.empty(variant_id=variant_id, initial_nav=Decimal(str(initial_nav)))

    trade_count = len(ordered)
    net_pnl = sum((trade.pnl for trade in ordered), Decimal("0"))
    win_count = sum(1 for trade in ordered if trade.pnl > 0)
    average_r = sum((trade.r_multiple for trade in ordered), Decimal("0")) / Decimal(trade_count)
    equity = derive_equity_curve(variant_id=variant_id, trades=ordered, initial_nav=initial_nav)
    max_drawdown = max((point.drawdown for point in equity), default=Decimal("0"))
    score_denominator = max(max_drawdown, Decimal(str(drawdown_floor)))
    return VariantStats(
        variant_id=variant_id,
        trade_count=trade_count,
        win_rate=Decimal(win_count) / Decimal(trade_count),
        net_pnl=net_pnl,
        expectancy=net_pnl / Decimal(trade_count),
        average_r=average_r,
        max_drawdown=max_drawdown,
        ending_nav=Decimal(str(initial_nav)) + net_pnl,
        live_forward_score=net_pnl / score_denominator,
    )


def compute_leaderboard_rows(
    *,
    variants: Sequence[PaperVariant],
    trades_by_variant: Mapping[int, Sequence[VariantTrade]],
    initial_nav: Decimal,
    drawdown_floor: Decimal,
    min_trades: int,
) -> tuple[VariantLeaderboardRow, ...]:
    rows: list[tuple[PaperVariant, VariantStats, Decimal, Decimal]] = []
    for variant in variants:
        stats = compute_variant_stats(
            variant_id=variant.id,
            trades=trades_by_variant.get(variant.id, ()),
            initial_nav=initial_nav,
            drawdown_floor=drawdown_floor,
        )
        if stats.trade_count < min_trades:
            continue
        oos_score = Decimal(str(variant.trial_scores.get("out_of_sample_score", "0")))
        robustness_score = Decimal(str(variant.trial_scores.get("robustness_score", "0")))
        rows.append((variant, stats, oos_score, robustness_score))

    ranked = sorted(
        rows,
        key=lambda item: (
            item[2],
            item[1].live_forward_score,
            item[3],
            Decimal(-item[0].id),
        ),
        reverse=True,
    )
    return tuple(
        VariantLeaderboardRow(
            rank=index,
            variant=variant,
            stats=stats,
            out_of_sample_score=oos_score,
            robustness_score=robustness_score,
        )
        for index, (variant, stats, oos_score, robustness_score) in enumerate(ranked, start=1)
    )


def _paper_variant_from_row(row: Mapping[str, Any]) -> PaperVariant:
    return PaperVariant(
        id=int(row["id"]),
        label=row["label"],
        params=dict(row["params_json"]),
        source_trial_id=int(row["source_trial_id"]),
        status=row["status"],
        trial_scores={
            "in_sample_score": row["is_score"],
            "out_of_sample_score": row["oos_score"],
            "robustness_score": row["robustness_score"],
        },
    )


def _variant_trade_from_row(row: Mapping[str, Any]) -> VariantTrade:
    return VariantTrade(
        id=int(row["id"]),
        variant_id=int(row["variant_id"]),
        side=row["side"],
        units=row["units"],
        entry_price=row["entry_price"],
        entry_ts=row["entry_ts"],
        exit_price=row["exit_price"],
        exit_ts=row["exit_ts"],
        pnl=row["pnl"],
        r_multiple=row["r_multiple"],
        exit_reason=row["exit_reason"],
    )


def _ordered_trades(trades: Sequence[VariantTrade]) -> tuple[VariantTrade, ...]:
    return tuple(sorted(trades, key=lambda trade: (trade.exit_ts, trade.id or 0)))
