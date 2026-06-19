from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import (
    BacktestConfig,
    BacktestInput,
    BacktestRunResult,
    BacktestStats,
)
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.models import OptimizationConfig, TrialScore
from harbor_bot.optimizer.search_space import strategy_config_for_params
from harbor_bot.optimizer.walkforward import build_walk_forward_windows
from harbor_bot.strategy.models import InstrumentRules, StrategyConfig

BacktestRunner = Callable[[BacktestInput], BacktestRunResult]


class InsufficientTradeCountError(ValueError):
    pass


@dataclass(frozen=True)
class ObjectiveEvaluation:
    params: dict[str, object]
    score: TrialScore
    in_sample_stats: BacktestStats
    out_of_sample_stats: BacktestStats
    windows_evaluated: int


def evaluate_params(
    *,
    params: dict[str, object],
    candles: tuple[ClosedCandle, ...],
    base_strategy_config: StrategyConfig,
    instrument_rules: InstrumentRules,
    backtest_config: BacktestConfig,
    optimizer_config: OptimizationConfig,
    backtest_runner: BacktestRunner = run_backtest,
) -> ObjectiveEvaluation:
    variant_config = strategy_config_for_params(base_strategy_config, params)
    windows = build_walk_forward_windows(
        candles,
        optimizer_config.walk_forward,
        strategy_config=variant_config,
    )
    in_sample_results: list[BacktestRunResult] = []
    oos_results: list[BacktestRunResult] = []

    for window in windows:
        in_sample_results.append(
            backtest_runner(
                BacktestInput(
                    instrument=variant_config.instrument,
                    candles=window.train_candles,
                    strategy_config=variant_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                )
            )
        )
        oos_results.append(
            backtest_runner(
                BacktestInput(
                    instrument=variant_config.instrument,
                    candles=window.oos_candles,
                    strategy_config=variant_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                )
            )
        )

    in_sample_stats = aggregate_stats(in_sample_results, initial_nav=backtest_config.initial_nav)
    oos_stats = aggregate_stats(oos_results, initial_nav=backtest_config.initial_nav)
    if in_sample_stats.trade_count < optimizer_config.min_in_sample_trades:
        msg = "in-sample trade count below configured floor"
        raise InsufficientTradeCountError(msg)
    if oos_stats.trade_count < optimizer_config.min_oos_trades:
        msg = "out-of-sample trade count below configured floor"
        raise InsufficientTradeCountError(msg)

    return ObjectiveEvaluation(
        params=dict(params),
        score=TrialScore(
            in_sample_score=objective_score(in_sample_stats, optimizer_config),
            out_of_sample_score=objective_score(oos_stats, optimizer_config),
        ),
        in_sample_stats=in_sample_stats,
        out_of_sample_stats=oos_stats,
        windows_evaluated=len(windows),
    )


def objective_score(stats: BacktestStats, optimizer_config: OptimizationConfig) -> Decimal:
    drawdown = max(stats.max_drawdown, optimizer_config.drawdown_floor)
    return stats.expectancy / drawdown


def aggregate_stats(
    results: list[BacktestRunResult],
    *,
    initial_nav: Decimal,
) -> BacktestStats:
    trades = [trade for result in results for trade in result.trades]
    trade_count = len(trades)
    net_pnl = sum((result.stats.net_pnl for result in results), Decimal("0"))
    win_count = len([trade for trade in trades if trade.pnl > 0])
    return BacktestStats(
        trade_count=trade_count,
        win_rate=Decimal(win_count) / Decimal(trade_count) if trade_count else Decimal("0"),
        net_pnl=net_pnl,
        expectancy=net_pnl / Decimal(trade_count) if trade_count else Decimal("0"),
        average_r=(
            sum((trade.r_multiple for trade in trades), Decimal("0")) / Decimal(trade_count)
            if trade_count
            else Decimal("0")
        ),
        max_drawdown=max(
            (result.stats.max_drawdown for result in results),
            default=Decimal("0"),
        ),
        ending_nav=initial_nav + net_pnl,
        lookahead_sanity_passed=all(result.stats.lookahead_sanity_passed for result in results),
    )
