from dataclasses import dataclass
from decimal import Decimal

import optuna

from harbor_bot.backtester.models import BacktestConfig
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationConfig,
    OptimizationStatus,
    TrialRecord,
    TrialScore,
)
from harbor_bot.optimizer.objective import (
    BacktestRunner,
    InsufficientTradeCountError,
    evaluate_params,
)
from harbor_bot.optimizer.robustness import calculate_robustness_score
from harbor_bot.optimizer.search_space import sample_search_space
from harbor_bot.strategy.models import InstrumentRules, StrategyConfig


@dataclass(frozen=True)
class OptimizationRunResult:
    status: OptimizationStatus
    trials: tuple[TrialRecord, ...]
    candidates: tuple[CandidateVariant, ...]
    sampler_name: str
    pruner_name: str


def run_optimization(
    *,
    candles: tuple[ClosedCandle, ...],
    base_strategy_config: StrategyConfig,
    instrument_rules: InstrumentRules,
    backtest_config: BacktestConfig,
    optimizer_config: OptimizationConfig,
    backtest_runner: BacktestRunner,
) -> OptimizationRunResult:
    sampler = optuna.samplers.TPESampler(seed=optimizer_config.tpe_seed)
    pruner = optuna.pruners.MedianPruner()
    study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)
    records: dict[int, TrialRecord] = {}

    def objective(trial: optuna.trial.Trial) -> float:
        params = sample_search_space(trial, optimizer_config.search_space)
        try:
            evaluation = evaluate_params(
                params=params,
                candles=candles,
                base_strategy_config=base_strategy_config,
                instrument_rules=instrument_rules,
                backtest_config=backtest_config,
                optimizer_config=optimizer_config,
                backtest_runner=backtest_runner,
            )
            trial.report(float(evaluation.score.out_of_sample_score), step=0)
            if trial.should_prune():
                records[trial.number] = _record(
                    trial.number,
                    params,
                    status=OptimizationStatus.PRUNED,
                    pruned=True,
                )
                raise optuna.TrialPruned()

            robustness = calculate_robustness_score(
                params=params,
                base_oos_score=evaluation.score.out_of_sample_score,
                search_space=optimizer_config.search_space,
                optimizer_config=optimizer_config,
                objective_evaluator=lambda neighbor: evaluate_params(
                    params=neighbor,
                    candles=candles,
                    base_strategy_config=base_strategy_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                    optimizer_config=optimizer_config,
                    backtest_runner=backtest_runner,
                ),
            )
            score = TrialScore(
                in_sample_score=evaluation.score.in_sample_score,
                out_of_sample_score=evaluation.score.out_of_sample_score,
                robustness_score=robustness,
            )
            records[trial.number] = TrialRecord(
                trial_no=trial.number,
                params=params,
                score=score,
                status=OptimizationStatus.COMPLETED,
            )
            return float(score.out_of_sample_score)
        except InsufficientTradeCountError:
            records[trial.number] = _record(
                trial.number,
                params,
                status=OptimizationStatus.PRUNED,
                pruned=True,
            )
            raise optuna.TrialPruned() from None
        except Exception:
            records[trial.number] = _record(
                trial.number,
                params,
                status=OptimizationStatus.FAILED,
                pruned=False,
            )
            raise

    study.optimize(
        objective,
        n_trials=optimizer_config.trial_count,
        catch=(Exception,),
        show_progress_bar=False,
    )
    trials = tuple(records[index] for index in sorted(records))
    candidates = _rank_candidates(trials, optimizer_config.candidate_count)
    return OptimizationRunResult(
        status=OptimizationStatus.COMPLETED,
        trials=trials,
        candidates=candidates,
        sampler_name=sampler.__class__.__name__,
        pruner_name=pruner.__class__.__name__,
    )


def _rank_candidates(
    trials: tuple[TrialRecord, ...],
    candidate_count: int,
) -> tuple[CandidateVariant, ...]:
    completed = [
        trial
        for trial in trials
        if trial.status == OptimizationStatus.COMPLETED
        and not trial.pruned
        and trial.score.in_sample_score > 0
        and trial.score.out_of_sample_score > 0
    ]
    ranked = sorted(
        completed,
        key=lambda trial: (trial.score.out_of_sample_score, trial.score.robustness_score),
        reverse=True,
    )
    return tuple(
        CandidateVariant(
            label=f"candidate-{index}",
            params=trial.params,
            source_trial_no=trial.trial_no,
        )
        for index, trial in enumerate(ranked[:candidate_count], start=1)
    )


def _record(
    trial_no: int,
    params: dict[str, object],
    *,
    status: OptimizationStatus,
    pruned: bool,
) -> TrialRecord:
    return TrialRecord(
        trial_no=trial_no,
        params=params,
        score=TrialScore(
            in_sample_score=Decimal("0"),
            out_of_sample_score=Decimal("0"),
            robustness_score=Decimal("0"),
        ),
        pruned=pruned,
        status=status,
    )
