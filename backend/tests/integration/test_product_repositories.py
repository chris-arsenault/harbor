import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.backtester.models import (
    BacktestRunResult,
    BacktestStats,
    BacktestStatus,
    BacktestTrade,
)
from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationStatus,
    TrialRecord,
    TrialScore,
)
from harbor_bot.paper_engine.models import VariantTrade
from harbor_bot.persistence.backtest_repository import append_backtest_result, list_backtest_runs
from harbor_bot.persistence.config_repository import list_config_values, upsert_config_value
from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.execution_repository import list_trade_journal
from harbor_bot.persistence.optimization_repository import append_optimization_run
from harbor_bot.persistence.schema import signals, trades
from harbor_bot.persistence.variant_repository import (
    append_variant_trades,
    create_paper_variant_from_trial,
    get_variant_detail,
    list_study_summaries,
)
from harbor_bot.settings import Settings


def test_product_repositories_read_product_surface(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_product_repositories(postgres_url))


async def _assert_product_repositories(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        backtest_run_id = await append_backtest_result(engine, _backtest_result())
        study_id = await _seed_study(engine)

        async with transaction(engine) as connection:
            await upsert_config_value(
                connection,
                key="strategy",
                value={"instrument": "EUR_USD", "risk_per_trade_pct": 0.5},
            )
            signal_id = await _seed_broker_trade(connection)

        async with engine.connect() as connection:
            study = await list_study_summaries(connection)
        source_trial_id = study[0]["best_trial_id"]
        variant_id = await create_paper_variant_from_trial(
            engine,
            trial_id=source_trial_id,
            label="paper-trial-0",
        )
        await append_variant_trades(engine, (_variant_trade(variant_id),))

        async with engine.connect() as connection:
            journal = await list_trade_journal(
                connection,
                start=datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
                end=datetime(2026, 1, 15, 17, 0, tzinfo=UTC),
            )
            runs = await list_backtest_runs(connection)
            studies = await list_study_summaries(connection)
            variant = await get_variant_detail(
                connection,
                variant_id=variant_id,
                initial_nav=Decimal("10000"),
            )
            config = await list_config_values(connection)

        assert journal[0]["signal_id"] == signal_id
        assert journal[0]["instrument"] == "EUR_USD"
        assert journal[0]["broker_trade_id"] == "7001"
        assert runs[0]["run_id"] == backtest_run_id
        assert runs[0]["trade_count"] == 1
        assert studies[0]["study_id"] == study_id
        assert studies[0]["trial_count"] == 2
        assert variant is not None
        assert variant["variant"]["id"] == variant_id
        assert variant["trades"][0]["pnl"] == "60.00000000"
        assert variant["equity_curve"][0]["nav"] == "10060.00000000"
        assert config[0]["key"] == "strategy"
        assert config[0]["value"] == {"instrument": "EUR_USD", "risk_per_trade_pct": 0.5}
    finally:
        await engine.dispose()


async def _seed_broker_trade(connection) -> int:
    signal_result = await connection.execute(
        signals.insert()
        .values(
            signal_key="harbor-practice:7:2026-01-15T14:30:00Z",
            ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
            instrument="EUR_USD",
            direction="long",
            entry=Decimal("1.09020"),
            stop=Decimal("1.08000"),
            target=Decimal("1.11000"),
            risk=Decimal("0.01020"),
            rr=Decimal("2.0"),
            status="filled",
        )
        .returning(signals.c.id)
    )
    signal_id = int(signal_result.scalar_one())
    await connection.execute(
        trades.insert().values(
            signal_id=signal_id,
            broker_order_id="9100",
            client_order_id="harbor-practice:7:2026-01-15T14:30:00Z",
            broker_trade_id="7001",
            open_transaction_id="9101",
            close_transaction_id="9201",
            side="long",
            units=Decimal("1000"),
            entry_price=Decimal("1.09020"),
            entry_ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
            exit_price=Decimal("1.09200"),
            exit_ts=datetime(2026, 1, 15, 16, 59, tzinfo=UTC),
            pnl=Decimal("18"),
            r_multiple=Decimal("2"),
            exit_reason="take_profit",
        )
    )
    return signal_id


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


def _backtest_result() -> BacktestRunResult:
    return BacktestRunResult(
        status=BacktestStatus.COMPLETED,
        stats=BacktestStats(
            trade_count=1,
            win_rate=Decimal("1"),
            net_pnl=Decimal("40"),
            expectancy=Decimal("40"),
            average_r=Decimal("2"),
            max_drawdown=Decimal("0"),
            ending_nav=Decimal("10040"),
            lookahead_sanity_passed=True,
        ),
        trades=(
            BacktestTrade(
                instrument="EUR_USD",
                side="long",
                units=Decimal("10000"),
                entry_price=Decimal("1.1000"),
                entry_ts=datetime(2026, 1, 15, 14, 34, tzinfo=UTC),
                stop=Decimal("1.0980"),
                target=Decimal("1.1040"),
                exit_price=Decimal("1.1040"),
                exit_ts=datetime(2026, 1, 15, 14, 40, tzinfo=UTC),
                pnl=Decimal("40"),
                r_multiple=Decimal("2"),
                exit_reason="take_profit",
            ),
        ),
        params_json={"instrument": "EUR_USD"},
    )


def _variant_trade(variant_id: int) -> VariantTrade:
    return VariantTrade(
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


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
