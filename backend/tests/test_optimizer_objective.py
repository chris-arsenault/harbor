from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
from harbor_bot.optimizer.models import OptimizationConfig, WalkForwardConfig
from harbor_bot.optimizer.objective import (
    InsufficientTradeCountError,
    aggregate_stats,
    evaluate_params,
    objective_score,
)
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults


def test_objective_score_is_oos_expectancy_divided_by_drawdown_floor() -> None:
    config = load_optimizer_config()
    stats = BacktestStats(
        trade_count=2,
        win_rate=Decimal("0.5"),
        net_pnl=Decimal("20"),
        expectancy=Decimal("10"),
        average_r=Decimal("0.5"),
        max_drawdown=Decimal("0"),
        ending_nav=Decimal("10020"),
        lookahead_sanity_passed=True,
    )

    assert objective_score(stats, config) == Decimal("10")


def test_evaluate_params_runs_m5_backtester_for_each_train_and_oos_window() -> None:
    calls: list[BacktestInput] = []

    def fake_runner(backtest_input: BacktestInput) -> BacktestRunResult:
        calls.append(backtest_input)
        return _result(pnl=Decimal("20"), r_multiple=Decimal("1"))

    evaluation = evaluate_params(
        params={"fvg_window": 12},
        candles=_session_day("2026-01-15") + _session_day("2026-01-16"),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        backtest_config=BacktestConfig(),
        optimizer_config=_test_optimizer_config(),
        backtest_runner=fake_runner,
    )

    assert len(calls) == 2
    assert calls[0].strategy_config.fvg_window == 12
    assert calls[1].strategy_config.fvg_window == 12
    assert calls[0].candles[0].ts.date().isoformat() == "2026-01-15"
    assert calls[1].candles[0].ts.date().isoformat() == "2026-01-16"
    assert evaluation.windows_evaluated == 1
    assert evaluation.score.out_of_sample_score == Decimal("20")


def test_evaluate_params_rejects_results_below_trade_count_floor() -> None:
    config = _test_optimizer_config()
    strict_config = OptimizationConfig(
        search_space=config.search_space,
        walk_forward=config.walk_forward,
        trial_count=config.trial_count,
        candidate_count=config.candidate_count,
        tpe_seed=config.tpe_seed,
        min_in_sample_trades=1,
        min_oos_trades=1,
        drawdown_floor=config.drawdown_floor,
        robustness_neighbor_count=config.robustness_neighbor_count,
        robustness_step_scale=config.robustness_step_scale,
    )

    with pytest.raises(InsufficientTradeCountError, match="trade count"):
        evaluate_params(
            params={},
            candles=_session_day("2026-01-15") + _session_day("2026-01-16"),
            base_strategy_config=strategy_config_from_defaults(load_default_config()),
            instrument_rules=_rules(),
            backtest_config=BacktestConfig(),
            optimizer_config=strict_config,
            backtest_runner=lambda _: _result(trades=()),
        )


def test_aggregate_stats_combines_window_results() -> None:
    stats = aggregate_stats(
        [
            _result(pnl=Decimal("20"), r_multiple=Decimal("1")),
            _result(pnl=Decimal("-10"), r_multiple=Decimal("-0.5")),
        ],
        initial_nav=Decimal("10000"),
    )

    assert stats.trade_count == 2
    assert stats.net_pnl == Decimal("10")
    assert stats.win_rate == Decimal("0.5")
    assert stats.expectancy == Decimal("5")
    assert stats.average_r == Decimal("0.25")
    assert stats.ending_nav == Decimal("10010")


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


def _test_optimizer_config() -> OptimizationConfig:
    config = load_optimizer_config()
    return OptimizationConfig(
        search_space=config.search_space,
        walk_forward=WalkForwardConfig(train_window_days=1, oos_window_days=1, step_days=1),
        trial_count=4,
        candidate_count=3,
        tpe_seed=config.tpe_seed,
        min_in_sample_trades=0,
        min_oos_trades=0,
        drawdown_floor=config.drawdown_floor,
        robustness_neighbor_count=config.robustness_neighbor_count,
        robustness_step_scale=config.robustness_step_scale,
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
        exit_reason="take_profit" if pnl > 0 else "stop_loss",
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


def _session_day(day: str) -> tuple[ClosedCandle, ...]:
    return (
        _candle(f"{day}T01:00:00+00:00"),
        _candle(f"{day}T07:00:00+00:00"),
        _candle(f"{day}T14:30:00+00:00"),
        _candle(f"{day}T16:31:00+00:00"),
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
