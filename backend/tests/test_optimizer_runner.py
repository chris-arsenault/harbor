from datetime import UTC, datetime
from decimal import Decimal

from harbor_bot.backtester.models import (
    BacktestConfig,
    BacktestInput,
    BacktestRunResult,
    BacktestStats,
    BacktestStatus,
    BacktestTrade,
)
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import OptimizationConfig, OptimizationStatus
from harbor_bot.optimizer.runner import run_optimization
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults


def test_runner_uses_optuna_tpe_median_pruner_and_returns_ranked_candidates() -> None:
    config = load_optimizer_config()

    result = run_optimization(
        candles=(
            _candle("2026-01-15T01:00:00+00:00"),
            _candle("2026-01-16T01:00:00+00:00"),
        ),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        backtest_config=BacktestConfig(),
        optimizer_config=config,
        backtest_runner=_scoring_runner,
    )

    assert result.status == OptimizationStatus.COMPLETED
    assert result.sampler_name == "TPESampler"
    assert result.pruner_name == "MedianPruner"
    assert len(result.trials) == config.trial_count
    assert len(result.candidates) <= config.candidate_count
    assert all(candidate.status == "paper" for candidate in result.candidates)
    assert result.candidates[0].params["fvg_window"] >= result.candidates[-1].params["fvg_window"]


def test_runner_records_pruned_trials_when_trade_floor_rejects_params() -> None:
    config = load_optimizer_config()
    strict_config = OptimizationConfig(
        search_space=config.search_space,
        walk_forward=config.walk_forward,
        trial_count=2,
        candidate_count=1,
        tpe_seed=config.tpe_seed,
        min_in_sample_trades=1,
        min_oos_trades=1,
        drawdown_floor=config.drawdown_floor,
        robustness_neighbor_count=config.robustness_neighbor_count,
        robustness_step_scale=config.robustness_step_scale,
    )

    result = run_optimization(
        candles=(
            _candle("2026-01-15T01:00:00+00:00"),
            _candle("2026-01-16T01:00:00+00:00"),
        ),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        backtest_config=BacktestConfig(),
        optimizer_config=strict_config,
        backtest_runner=lambda _: _result(trades=()),
    )

    assert [trial.status for trial in result.trials] == [
        OptimizationStatus.PRUNED,
        OptimizationStatus.PRUNED,
    ]
    assert result.candidates == ()


def _scoring_runner(backtest_input: BacktestInput) -> BacktestRunResult:
    fvg_window = backtest_input.strategy_config.fvg_window
    pnl = Decimal(fvg_window)
    return _result(pnl=pnl, r_multiple=pnl / Decimal("10"))


def _result(
    *,
    pnl: Decimal = Decimal("0"),
    r_multiple: Decimal = Decimal("0"),
    trades: tuple[BacktestTrade, ...] | None = None,
) -> BacktestRunResult:
    result_trades = trades if trades is not None else (_trade(pnl=pnl, r_multiple=r_multiple),)
    trade_count = len(result_trades)
    return BacktestRunResult(
        status=BacktestStatus.COMPLETED,
        stats=BacktestStats(
            trade_count=trade_count,
            win_rate=Decimal("1") if pnl > 0 else Decimal("0"),
            net_pnl=pnl,
            expectancy=pnl / Decimal(trade_count) if trade_count else Decimal("0"),
            average_r=r_multiple,
            max_drawdown=Decimal("0"),
            ending_nav=Decimal("10000") + pnl,
            lookahead_sanity_passed=True,
        ),
        trades=result_trades,
    )


def _trade(*, pnl: Decimal, r_multiple: Decimal) -> BacktestTrade:
    return BacktestTrade(
        instrument="EUR_USD",
        side="long",
        units=Decimal("10000"),
        entry_price=Decimal("1.1000"),
        entry_ts=datetime(2026, 1, 15, 14, 34, tzinfo=UTC),
        stop=Decimal("1.0980"),
        target=Decimal("1.1040"),
        exit_price=Decimal("1.1040"),
        exit_ts=datetime(2026, 1, 15, 14, 40, tzinfo=UTC),
        pnl=pnl,
        r_multiple=r_multiple,
        exit_reason="take_profit",
    )


def _candle(ts: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.1000"),
        h=Decimal("1.1010"),
        low=Decimal("1.0990"),
        c=Decimal("1.1005"),
        volume=100,
    )


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
