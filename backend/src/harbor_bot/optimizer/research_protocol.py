from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestConfig, BacktestInput
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationConfig,
    OptimizationStatus,
    TrialRecord,
    WalkForwardConfig,
)
from harbor_bot.optimizer.objective import candidate_gate_score, objective_score
from harbor_bot.optimizer.runner import OptimizationRunResult, run_optimization
from harbor_bot.optimizer.walkforward import StrategyDayStatus
from harbor_bot.strategy.models import InstrumentRules, StrategyConfig
from harbor_bot.strategy.sessions import (
    compute_session_levels,
    session_windows_for_date,
    trading_date_for_candle,
)


@dataclass(frozen=True)
class ResearchProtocolConfig:
    trial_count: int = 96
    candidate_count: int = 5
    discovery_candidate_count: int = 30
    min_evaluable_days: int = 120
    min_discovery_days: int = 90
    holdout_days: int = 30
    max_session_gap_minutes: int = 1
    min_holdout_trades: int = 5
    train_window_days: int = 60
    oos_window_days: int = 20
    step_days: int = 20
    min_in_sample_trades: int = 12
    min_oos_trades: int = 4


@dataclass(frozen=True)
class ResearchProtocolResult:
    run_result: OptimizationRunResult
    report: dict[str, Any]


DEFAULT_RESEARCH_PROTOCOL_CONFIG = ResearchProtocolConfig()


def research_optimizer_config(
    base: OptimizationConfig | None = None,
    *,
    protocol_config: ResearchProtocolConfig = DEFAULT_RESEARCH_PROTOCOL_CONFIG,
) -> OptimizationConfig:
    config = base or load_optimizer_config()
    return replace(
        config,
        trial_count=protocol_config.trial_count,
        candidate_count=protocol_config.candidate_count,
        walk_forward=WalkForwardConfig(
            train_window_days=protocol_config.train_window_days,
            oos_window_days=protocol_config.oos_window_days,
            step_days=protocol_config.step_days,
        ),
        min_in_sample_trades=protocol_config.min_in_sample_trades,
        min_oos_trades=protocol_config.min_oos_trades,
        robustness_neighbor_count=0,
    )


def run_research_protocol(
    *,
    candles: tuple[ClosedCandle, ...],
    base_strategy_config: StrategyConfig,
    instrument_rules: InstrumentRules,
    backtest_config: BacktestConfig,
    optimizer_config: OptimizationConfig,
    protocol_config: ResearchProtocolConfig = DEFAULT_RESEARCH_PROTOCOL_CONFIG,
) -> ResearchProtocolResult:
    optimizer_config = research_optimizer_config(
        optimizer_config,
        protocol_config=protocol_config,
    )
    readiness = research_readiness(
        candles,
        base_strategy_config,
        protocol_config=protocol_config,
    )
    if readiness["status"] != "ready":
        raise ValueError(readiness["message"])

    groups = _strict_strategy_day_groups(candles, base_strategy_config)
    evaluable_dates = tuple(
        date.fromisoformat(item["trading_date"])
        for item in readiness["evaluable_days"]
        if item["evaluable"]
    )
    holdout_dates = evaluable_dates[-protocol_config.holdout_days :]
    discovery_dates = evaluable_dates[: -protocol_config.holdout_days]
    discovery_candles = _candles_for_dates(groups, discovery_dates)
    holdout_candles = _candles_for_dates(groups, holdout_dates)

    discovery_result = run_optimization(
        candles=discovery_candles,
        base_strategy_config=base_strategy_config,
        instrument_rules=instrument_rules,
        backtest_config=backtest_config,
        optimizer_config=optimizer_config,
        backtest_runner=run_backtest,
    )
    discovery_shortlist = _rank_discovery_candidates(
        discovery_result.trials,
        protocol_config.discovery_candidate_count,
    )
    validation_rows = _validate_candidates_on_holdout(
        trials=discovery_result.trials,
        candidates=discovery_shortlist,
        holdout_candles=holdout_candles,
        base_strategy_config=base_strategy_config,
        instrument_rules=instrument_rules,
        backtest_config=backtest_config,
        optimizer_config=optimizer_config,
        protocol_config=protocol_config,
    )
    passed_trial_numbers = {
        int(row["source_trial_no"]) for row in validation_rows if row["status"] == "passed"
    }
    validated_candidates = _relabel_candidates(
        candidate
        for candidate in discovery_shortlist
        if candidate.source_trial_no in passed_trial_numbers
    )[: protocol_config.candidate_count]
    validated_source_trial_numbers = {
        candidate.source_trial_no for candidate in validated_candidates
    }
    validation_rows = [
        {
            **row,
            "selected": int(row["source_trial_no"]) in validated_source_trial_numbers,
        }
        for row in validation_rows
    ]
    result = OptimizationRunResult(
        status=OptimizationStatus.COMPLETED,
        trials=discovery_result.trials,
        candidates=validated_candidates,
        sampler_name=discovery_result.sampler_name,
        pruner_name=discovery_result.pruner_name,
    )
    return ResearchProtocolResult(
        run_result=result,
        report={
            "protocol": "fixed_walk_forward_holdout_v1",
            "dataset": {
                "candle_count": len(candles),
                "evaluable_day_count": len(evaluable_dates),
                "from_trading_date": evaluable_dates[0].isoformat(),
                "to_trading_date": evaluable_dates[-1].isoformat(),
            },
            "data_requirements": _requirements(protocol_config),
            "split": {
                "discovery_day_count": len(discovery_dates),
                "discovery_from": discovery_dates[0].isoformat(),
                "discovery_to": discovery_dates[-1].isoformat(),
                "holdout_day_count": len(holdout_dates),
                "holdout_from": holdout_dates[0].isoformat(),
                "holdout_to": holdout_dates[-1].isoformat(),
            },
            "optimizer_config": optimizer_config.to_jsonable(),
            "discovery_shortlist_count": len(discovery_shortlist),
            "holdout_validation": validation_rows,
        },
    )


def research_readiness(
    candles: tuple[ClosedCandle, ...],
    strategy_config: StrategyConfig,
    *,
    protocol_config: ResearchProtocolConfig = DEFAULT_RESEARCH_PROTOCOL_CONFIG,
) -> dict[str, Any]:
    if not candles:
        return _not_ready(
            "no persisted closed candles are available",
            protocol_config=protocol_config,
            day_statuses=(),
        )
    day_statuses = strict_strategy_day_statuses(
        candles,
        strategy_config,
        max_gap_minutes=protocol_config.max_session_gap_minutes,
    )
    evaluable = tuple(status for status in day_statuses if status.evaluable)
    required_total = protocol_config.min_discovery_days + protocol_config.holdout_days
    if len(evaluable) < protocol_config.min_evaluable_days:
        return _not_ready(
            (
                f"{len(evaluable)} complete strategy days available; "
                f"{protocol_config.min_evaluable_days} required"
            ),
            protocol_config=protocol_config,
            day_statuses=day_statuses,
        )
    if len(evaluable) < required_total:
        return _not_ready(
            f"{len(evaluable)} complete strategy days available; {required_total} required",
            protocol_config=protocol_config,
            day_statuses=day_statuses,
        )
    return {
        "status": "ready",
        "message": "dataset satisfies the fixed research protocol",
        "data_requirements": _requirements(protocol_config),
        "evaluable_day_count": len(evaluable),
        "partial_day_count": len(day_statuses) - len(evaluable),
        "evaluable_days": [_day_status_json(status) for status in day_statuses],
    }


def strict_strategy_day_statuses(
    candles: tuple[ClosedCandle, ...],
    strategy_config: StrategyConfig,
    *,
    max_gap_minutes: int,
) -> tuple[StrategyDayStatus, ...]:
    groups = _strict_strategy_day_groups(candles, strategy_config)
    return tuple(
        _strict_day_status(
            trading_date,
            day_candles,
            strategy_config=strategy_config,
            max_gap=timedelta(minutes=max_gap_minutes),
        )
        for trading_date, day_candles in sorted(groups.items())
    )


def _strict_strategy_day_groups(
    candles: tuple[ClosedCandle, ...],
    strategy_config: StrategyConfig,
) -> dict[date, list[ClosedCandle]]:
    groups: dict[date, list[ClosedCandle]] = {}
    for candle in candles:
        trading_date = trading_date_for_candle(candle, strategy_config)
        groups.setdefault(trading_date, []).append(candle)
    return groups


def _strict_day_status(
    trading_date: date,
    day_candles: list[ClosedCandle],
    *,
    strategy_config: StrategyConfig,
    max_gap: timedelta,
) -> StrategyDayStatus:
    windows = session_windows_for_date(trading_date, strategy_config)
    for name, window in (
        ("Asia", windows.asia),
        ("London", windows.london),
        ("NY trade", windows.ny_trade),
    ):
        reason = _window_gap_reason(day_candles, window, name=name, max_gap=max_gap)
        if reason is not None:
            return StrategyDayStatus(
                trading_date=trading_date,
                candle_count=len(day_candles),
                evaluable=False,
                reason=reason,
            )
    try:
        compute_session_levels(
            day_candles,
            trading_date=trading_date,
            instrument=day_candles[0].instrument,
            config=strategy_config,
        )
    except ValueError as exc:
        return StrategyDayStatus(
            trading_date=trading_date,
            candle_count=len(day_candles),
            evaluable=False,
            reason=str(exc),
        )
    return StrategyDayStatus(
        trading_date=trading_date,
        candle_count=len(day_candles),
        evaluable=True,
    )


def _window_gap_reason(day_candles, window, *, name: str, max_gap: timedelta) -> str | None:
    timestamps = sorted(candle.ts for candle in day_candles if window.contains(candle.ts))
    if not timestamps:
        return f"no candles inside the {name} window"
    if timestamps[0] > window.start + max_gap:
        return f"{name} window missing opening candles"
    expected_last = window.end - timedelta(minutes=1)
    if timestamps[-1] < expected_last - max_gap:
        return f"{name} window missing closing candles"
    for previous, current in zip(timestamps, timestamps[1:], strict=False):
        if current - previous > max_gap:
            return (
                f"{name} window has a gap greater than {int(max_gap.total_seconds() // 60)} minutes"
            )
    return None


def _validate_candidates_on_holdout(
    *,
    trials: tuple[TrialRecord, ...],
    candidates: tuple[CandidateVariant, ...],
    holdout_candles: tuple[ClosedCandle, ...],
    base_strategy_config: StrategyConfig,
    instrument_rules: InstrumentRules,
    backtest_config: BacktestConfig,
    optimizer_config: OptimizationConfig,
    protocol_config: ResearchProtocolConfig,
) -> list[dict[str, Any]]:
    trial_by_no = {trial.trial_no: trial for trial in trials}
    rows = []
    for candidate in candidates:
        trial = trial_by_no[candidate.source_trial_no]
        variant_config = _strategy_config_for_params(base_strategy_config, candidate.params)
        try:
            holdout_result = run_backtest(
                BacktestInput(
                    instrument=variant_config.instrument,
                    candles=holdout_candles,
                    strategy_config=variant_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                )
            )
        except ValueError as exc:
            rows.append(
                {
                    "label": candidate.label,
                    "source_trial_no": trial.trial_no,
                    "status": "failed",
                    "holdout_score": "0",
                    "holdout_trade_count": 0,
                    "holdout_net_pnl": "0",
                    "reason": str(exc),
                }
            )
            continue

        score = objective_score(holdout_result.stats, optimizer_config)
        passed = (
            holdout_result.stats.trade_count >= protocol_config.min_holdout_trades and score > 0
        )
        rows.append(
            {
                "label": candidate.label,
                "source_trial_no": trial.trial_no,
                "status": "passed" if passed else "failed",
                "holdout_score": str(score),
                "holdout_trade_count": holdout_result.stats.trade_count,
                "holdout_net_pnl": str(holdout_result.stats.net_pnl),
                "reason": None
                if passed
                else _holdout_failure_reason(
                    trade_count=holdout_result.stats.trade_count,
                    score=score,
                    min_trades=protocol_config.min_holdout_trades,
                ),
            }
        )
    return rows


def _rank_discovery_candidates(
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
        key=lambda trial: (
            _candidate_gate_score_from_trial(trial),
            trial.score.out_of_sample_score,
            trial.score.robustness_score,
        ),
        reverse=True,
    )
    return tuple(
        CandidateVariant(
            label=f"discovery-candidate-{index}",
            params=trial.params,
            source_trial_no=trial.trial_no,
        )
        for index, trial in enumerate(ranked[:candidate_count], start=1)
    )


def _candidate_gate_score_from_trial(trial: TrialRecord) -> Decimal:
    return candidate_gate_score(trial.score)


def _relabel_candidates(candidates) -> tuple[CandidateVariant, ...]:
    return tuple(
        CandidateVariant(
            label=f"candidate-{index}",
            params=candidate.params,
            source_trial_no=candidate.source_trial_no,
        )
        for index, candidate in enumerate(candidates, start=1)
    )


def _strategy_config_for_params(base_config: StrategyConfig, params: dict[str, Any]):
    from harbor_bot.optimizer.search_space import strategy_config_for_params

    return strategy_config_for_params(base_config, params)


def _holdout_failure_reason(*, trade_count: int, score: Decimal, min_trades: int) -> str:
    if trade_count < min_trades:
        return f"holdout trade count below {min_trades}"
    if score <= 0:
        return "holdout score is not positive"
    return "holdout validation failed"


def _candles_for_dates(
    groups: dict[date, list[ClosedCandle]],
    dates: tuple[date, ...],
) -> tuple[ClosedCandle, ...]:
    return tuple(candle for trading_date in dates for candle in groups[trading_date])


def _not_ready(
    message: str,
    *,
    protocol_config: ResearchProtocolConfig,
    day_statuses: tuple[StrategyDayStatus, ...],
) -> dict[str, Any]:
    return {
        "status": "not_ready",
        "message": message,
        "data_requirements": _requirements(protocol_config),
        "evaluable_day_count": len([status for status in day_statuses if status.evaluable]),
        "partial_day_count": len([status for status in day_statuses if not status.evaluable]),
        "evaluable_days": [_day_status_json(status) for status in day_statuses],
    }


def _requirements(protocol_config: ResearchProtocolConfig) -> dict[str, int]:
    return {
        "trial_count": protocol_config.trial_count,
        "candidate_count": protocol_config.candidate_count,
        "discovery_candidate_count": protocol_config.discovery_candidate_count,
        "min_evaluable_days": protocol_config.min_evaluable_days,
        "min_discovery_days": protocol_config.min_discovery_days,
        "holdout_days": protocol_config.holdout_days,
        "max_session_gap_minutes": protocol_config.max_session_gap_minutes,
        "min_holdout_trades": protocol_config.min_holdout_trades,
        "train_window_days": protocol_config.train_window_days,
        "oos_window_days": protocol_config.oos_window_days,
        "step_days": protocol_config.step_days,
        "min_in_sample_trades": protocol_config.min_in_sample_trades,
        "min_oos_trades": protocol_config.min_oos_trades,
    }


def _day_status_json(status: StrategyDayStatus) -> dict[str, Any]:
    return {
        "trading_date": status.trading_date.isoformat(),
        "candle_count": status.candle_count,
        "evaluable": status.evaluable,
        "reason": status.reason,
    }
