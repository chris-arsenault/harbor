from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.backtester.data import candles_from_records, load_candle_fixture
from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestConfig, BacktestInput, BacktestStats
from harbor_bot.config.defaults import load_default_config
from harbor_bot.optimizer.config import load_optimizer_config, optimizer_config_from_mapping
from harbor_bot.optimizer.models import OptimizationConfig, OptimizationStatus
from harbor_bot.optimizer.objective import aggregate_stats, objective_score
from harbor_bot.optimizer.runner import OptimizationRunResult, run_optimization
from harbor_bot.optimizer.walkforward import (
    WalkForwardWindow,
    build_walk_forward_windows,
    summarize_strategy_days,
)
from harbor_bot.persistence.market_repository import (
    get_candle_coverage,
    list_candles_range,
)
from harbor_bot.persistence.optimization_repository import append_optimization_run
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults
from harbor_bot.strategy.sessions import trading_date_for_candle

OptimizationRunner = Callable[..., OptimizationRunResult]
PersistenceWriter = Callable[..., Awaitable[int]]
CandleRangeReader = Callable[..., Awaitable[list[dict[str, Any]]]]
CandleWindowSelector = Callable[..., Awaitable[dict[str, Any] | None]]
_UTC_OFFSET = timedelta(0)


@dataclass(frozen=True)
class OptimizerService:
    persistence_engine: AsyncEngine | None = None
    fixture_base_path: Path | None = None
    optimization_runner: OptimizationRunner = run_optimization
    persistence_writer: PersistenceWriter = append_optimization_run
    candle_reader: CandleRangeReader = None
    candle_window_selector: CandleWindowSelector = None

    async def preflight_optimization(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = await _payload_with_persisted_candles(
            payload,
            engine=self.persistence_engine,
            candle_reader=self.candle_reader or read_persisted_candle_records,
            candle_window_selector=(
                self.candle_window_selector or select_persisted_candle_coverage
            ),
        )
        request = _request_from_payload(payload, fixture_base_path=self.fixture_base_path)
        runner_kwargs = request["runner_kwargs"]
        candles = runner_kwargs["candles"]
        optimizer_config = request["optimizer_config"]
        strategy_config = runner_kwargs["base_strategy_config"]
        instrument_rules = runner_kwargs["instrument_rules"]
        backtest_config = runner_kwargs["backtest_config"]

        day_statuses = summarize_strategy_days(candles, strategy_config)
        evaluable_day_count = len([status for status in day_statuses if status.evaluable])
        required_days = (
            optimizer_config.walk_forward.train_window_days
            + optimizer_config.walk_forward.oos_window_days
        )
        try:
            windows = build_walk_forward_windows(
                candles,
                optimizer_config.walk_forward,
                strategy_config=strategy_config,
            )
            window_error = None
        except ValueError as exc:
            windows = ()
            window_error = str(exc)

        baseline = None
        baseline_error = None
        if windows:
            try:
                baseline = _baseline_summary(
                    windows,
                    instrument=strategy_config.instrument,
                    strategy_config=strategy_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                    optimizer_config=optimizer_config,
                )
            except ValueError as exc:
                baseline_error = str(exc)

        readiness = _preflight_readiness(
            candle_count=len(candles),
            evaluable_day_count=evaluable_day_count,
            required_days=required_days,
            window_count=len(windows),
            window_error=window_error,
            baseline=baseline,
            baseline_error=baseline_error,
        )
        return {
            "status": "ready"
            if all(item["status"] != "fail" for item in readiness)
            else "not_ready",
            "instrument": strategy_config.instrument,
            "candle_source": payload.get("_candle_source"),
            "study_config": optimizer_config.to_jsonable(),
            "candidate_gate": {
                "requires": "completed trials with positive in-sample and out-of-sample scores",
                "min_in_sample_trades": optimizer_config.min_in_sample_trades,
                "min_out_of_sample_trades": optimizer_config.min_oos_trades,
            },
            "dataset": {
                "candle_count": len(candles),
                "session_day_count": len(day_statuses),
                "evaluable_session_day_count": evaluable_day_count,
                "partial_session_day_count": len(day_statuses) - evaluable_day_count,
                "first_evaluable_trading_date": _first_evaluable_date(day_statuses),
                "last_evaluable_trading_date": _last_evaluable_date(day_statuses),
                "day_diagnostics": [
                    {
                        "trading_date": status.trading_date.isoformat(),
                        "candle_count": status.candle_count,
                        "evaluable": status.evaluable,
                        "reason": status.reason,
                    }
                    for status in day_statuses
                    if not status.evaluable
                ][:10],
            },
            "walk_forward": {
                "window_count": len(windows),
                "required_session_days": required_days,
                "train_window_days": optimizer_config.walk_forward.train_window_days,
                "out_of_sample_window_days": optimizer_config.walk_forward.oos_window_days,
                "step_days": optimizer_config.walk_forward.step_days,
                "window_error": window_error,
                "windows": [
                    _window_summary(window, strategy_config=strategy_config)
                    for window in windows[:12]
                ],
                "omitted_window_count": max(len(windows) - 12, 0),
            },
            "baseline": baseline,
            "readiness": readiness,
            "recommended_payload": {
                "source": "persisted_candles",
                "instrument": strategy_config.instrument,
                "optimizer_config": optimizer_config.to_jsonable(),
            },
        }

    async def start_optimization(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = await _payload_with_persisted_candles(
            payload,
            engine=self.persistence_engine,
            candle_reader=self.candle_reader or read_persisted_candle_records,
            candle_window_selector=(
                self.candle_window_selector or select_persisted_candle_coverage
            ),
        )
        request = _request_from_payload(payload, fixture_base_path=self.fixture_base_path)
        result = self.optimization_runner(**request["runner_kwargs"])
        study_id = None
        if self.persistence_engine is not None:
            optimizer_config = request["optimizer_config"]
            study_id = await self.persistence_writer(
                self.persistence_engine,
                search_space_json=optimizer_config.search_space.to_jsonable(),
                walkforward_json=optimizer_config.walk_forward.to_jsonable(),
                status=OptimizationStatus.COMPLETED,
                trials=result.trials,
                candidates=result.candidates,
            )
        return optimization_result_to_response(
            result,
            study_id=study_id,
            candle_source=payload.get("_candle_source"),
        )


def optimization_result_to_response(
    result: OptimizationRunResult,
    *,
    study_id: int | None = None,
    candle_source: Any = None,
) -> dict[str, Any]:
    return {
        "study_id": study_id,
        "status": result.status.value,
        "sampler": result.sampler_name,
        "pruner": result.pruner_name,
        "trial_count": len(result.trials),
        "candidates": [
            {
                "label": candidate.label,
                "params": candidate.params,
                "source_trial_no": candidate.source_trial_no,
                "status": candidate.status,
            }
            for candidate in result.candidates
        ],
        "best_trial_history": _best_trial_history(result),
        "trials": [
            {
                "trial_no": trial.trial_no,
                "params": trial.params,
                "is_score": str(trial.score.in_sample_score),
                "oos_score": str(trial.score.out_of_sample_score),
                "robustness_score": str(trial.score.robustness_score),
                "pruned": trial.pruned,
                "status": trial.status.value,
                "failure_reason": trial.failure_reason,
            }
            for trial in result.trials
        ],
        "data_separation": {
            "source": _data_source_label(candle_source),
            "candle_source": candle_source,
            "no_live_forward_data": True,
            "variant_trades_used": False,
            "oanda_streams_used": False,
            "broker_state_used": False,
            "paper_engine_used": False,
            "frontend_ui_used": False,
        },
    }


def _baseline_summary(
    windows: tuple[WalkForwardWindow, ...],
    *,
    instrument: str,
    strategy_config,
    instrument_rules: InstrumentRules,
    backtest_config: BacktestConfig,
    optimizer_config: OptimizationConfig,
) -> dict[str, Any]:
    train_results = []
    oos_results = []
    for window in windows:
        train_results.append(
            run_backtest(
                BacktestInput(
                    instrument=instrument,
                    candles=window.train_candles,
                    strategy_config=strategy_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                )
            )
        )
        oos_results.append(
            run_backtest(
                BacktestInput(
                    instrument=instrument,
                    candles=window.oos_candles,
                    strategy_config=strategy_config,
                    instrument_rules=instrument_rules,
                    backtest_config=backtest_config,
                )
            )
        )

    in_sample_stats = aggregate_stats(train_results, initial_nav=backtest_config.initial_nav)
    out_of_sample_stats = aggregate_stats(oos_results, initial_nav=backtest_config.initial_nav)
    in_sample_score = objective_score(in_sample_stats, optimizer_config)
    out_of_sample_score = objective_score(out_of_sample_stats, optimizer_config)
    return {
        "status": _baseline_status(
            in_sample_stats,
            out_of_sample_stats,
            in_sample_score=in_sample_score,
            out_of_sample_score=out_of_sample_score,
            optimizer_config=optimizer_config,
        ),
        "window_count": len(windows),
        "in_sample": _baseline_side(in_sample_stats, in_sample_score),
        "out_of_sample": _baseline_side(out_of_sample_stats, out_of_sample_score),
    }


def _baseline_side(stats: BacktestStats, score: Decimal) -> dict[str, Any]:
    return {
        "score": str(score),
        "stats": stats.to_jsonable(),
    }


def _baseline_status(
    in_sample_stats: BacktestStats,
    out_of_sample_stats: BacktestStats,
    *,
    in_sample_score: Decimal,
    out_of_sample_score: Decimal,
    optimizer_config: OptimizationConfig,
) -> str:
    if in_sample_stats.trade_count < optimizer_config.min_in_sample_trades:
        return "below_in_sample_trade_floor"
    if out_of_sample_stats.trade_count < optimizer_config.min_oos_trades:
        return "below_out_of_sample_trade_floor"
    if in_sample_score > 0 and out_of_sample_score > 0:
        return "candidate_gate_passed"
    if in_sample_stats.trade_count == 0 and out_of_sample_stats.trade_count == 0:
        return "no_trades"
    return "candidate_gate_failed"


def _preflight_readiness(
    *,
    candle_count: int,
    evaluable_day_count: int,
    required_days: int,
    window_count: int,
    window_error: str | None,
    baseline: dict[str, Any] | None,
    baseline_error: str | None,
) -> list[dict[str, str]]:
    readiness = [
        {
            "name": "candles",
            "status": "pass" if candle_count > 0 else "fail",
            "message": f"{candle_count} persisted closed candles selected",
        },
        {
            "name": "session_days",
            "status": "pass" if evaluable_day_count >= required_days else "fail",
            "message": (
                f"{evaluable_day_count} complete strategy session days available; "
                f"{required_days} required by the study split"
            ),
        },
        {
            "name": "walk_forward",
            "status": "pass" if window_count > 0 else "fail",
            "message": (
                f"{window_count} walk-forward windows"
                if window_count > 0
                else window_error or "no walk-forward windows can be built"
            ),
        },
    ]
    if baseline_error is not None:
        readiness.append({"name": "baseline", "status": "fail", "message": baseline_error})
    elif baseline is not None:
        readiness.append(
            {
                "name": "baseline",
                "status": "pass" if baseline["status"] == "candidate_gate_passed" else "warn",
                "message": _baseline_message(baseline),
            }
        )
    return readiness


def _baseline_message(baseline: dict[str, Any]) -> str:
    if baseline["status"] == "candidate_gate_passed":
        return "baseline passes the same positive IS/OOS candidate gate"
    if baseline["status"] == "no_trades":
        return "baseline produced no trades across the selected walk-forward windows"
    if baseline["status"] == "below_in_sample_trade_floor":
        return "baseline is below the configured in-sample trade floor"
    if baseline["status"] == "below_out_of_sample_trade_floor":
        return "baseline is below the configured out-of-sample trade floor"
    return "baseline does not pass the positive IS/OOS candidate gate"


def _window_summary(window: WalkForwardWindow, *, strategy_config) -> dict[str, Any]:
    train_dates = _trading_dates(window.train_candles, strategy_config)
    out_of_sample_dates = _trading_dates(window.oos_candles, strategy_config)
    return {
        "index": window.index,
        "train_start": train_dates[0].isoformat(),
        "train_end": train_dates[-1].isoformat(),
        "out_of_sample_start": out_of_sample_dates[0].isoformat(),
        "out_of_sample_end": out_of_sample_dates[-1].isoformat(),
        "train_candle_count": len(window.train_candles),
        "out_of_sample_candle_count": len(window.oos_candles),
    }


def _trading_dates(candles, strategy_config) -> tuple:
    return tuple(
        dict.fromkeys(trading_date_for_candle(candle, strategy_config) for candle in candles)
    )


def _first_evaluable_date(day_statuses) -> str | None:
    for status in day_statuses:
        if status.evaluable:
            return status.trading_date.isoformat()
    return None


def _last_evaluable_date(day_statuses) -> str | None:
    for status in reversed(day_statuses):
        if status.evaluable:
            return status.trading_date.isoformat()
    return None


async def read_persisted_candle_records(
    engine: AsyncEngine | None,
    *,
    instrument: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    if engine is None:
        msg = "persisted candle range requests require a persistence engine"
        raise ValueError(msg)
    async with engine.connect() as connection:
        rows = await list_candles_range(
            connection,
            instrument=instrument,
            start=start,
            end=end,
        )
    return [
        {
            "instrument": row["instrument"],
            "ts": row["ts"].isoformat(),
            "o": str(row["o"]),
            "h": str(row["h"]),
            "low": str(row["l"]),
            "c": str(row["c"]),
            "volume": row["volume"],
            "complete": row["complete"],
        }
        for row in rows
    ]


async def select_persisted_candle_coverage(
    engine: AsyncEngine | None,
    *,
    instrument: str,
    required_days: int,
) -> dict[str, Any] | None:
    if engine is None:
        msg = "persisted candle optimization requires a persistence engine"
        raise ValueError(msg)
    if required_days <= 0:
        msg = "required_days must be positive"
        raise ValueError(msg)
    async with engine.connect() as connection:
        coverage = await get_candle_coverage(connection, instrument=instrument)
    if coverage["candle_count"] <= 0 or coverage["from"] is None or coverage["to"] is None:
        return None
    return {
        "instrument": instrument,
        "from": coverage["from"],
        "to": coverage["to"],
        "required_days": required_days,
        "coverage": coverage,
    }


async def _payload_with_persisted_candles(
    payload: Mapping[str, Any],
    *,
    engine: AsyncEngine | None,
    candle_reader: CandleRangeReader,
    candle_window_selector: CandleWindowSelector,
) -> dict[str, Any]:
    if "candles" in payload or "fixture" in payload:
        return dict(payload)
    if payload.get("source") != "persisted_candles" and "candle_range" not in payload:
        return dict(payload)

    strategy_config = strategy_config_from_defaults(load_default_config())
    instrument = str(payload.get("instrument") or strategy_config.instrument)
    raw_range = payload.get("candle_range")
    if not isinstance(raw_range, Mapping):
        optimizer_config = _optimizer_config_from_payload(payload.get("optimizer_config", {}))
        required_days = (
            optimizer_config.walk_forward.train_window_days
            + optimizer_config.walk_forward.oos_window_days
        )
        selected_window = await candle_window_selector(
            engine,
            instrument=instrument,
            required_days=required_days,
        )
        if selected_window is None:
            msg = (
                f"no persisted closed-candle window is available for {instrument}; "
                "import OANDA historical candles before starting a tuning study"
            )
            raise ValueError(msg)
        start = selected_window["from"]
        end = selected_window["to"]
    else:
        start = _parse_utc_ts(str(raw_range["from"]))
        end = _parse_utc_ts(str(raw_range["to"]))
    candles = await candle_reader(engine, instrument=instrument, start=start, end=end)
    if not candles:
        msg = (
            f"no persisted closed candles found for {instrument} from "
            f"{start.isoformat()} to {end.isoformat()}; import OANDA historical candles first"
        )
        raise ValueError(msg)
    next_payload = dict(payload)
    next_payload["candles"] = candles
    next_payload["candle_range"] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
    }
    next_payload["_candle_source"] = {
        "source": "persisted_candles",
        "origin": "database",
        "instrument": instrument,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "candle_count": len(candles),
    }
    next_payload.pop("fixture", None)
    return next_payload


def _best_trial_history(result: OptimizationRunResult) -> list[dict[str, Any]]:
    best_trial = None
    history: list[dict[str, Any]] = []
    for trial in sorted(result.trials, key=lambda item: item.trial_no):
        if best_trial is None or (
            trial.score.out_of_sample_score,
            trial.score.robustness_score,
        ) > (
            best_trial.score.out_of_sample_score,
            best_trial.score.robustness_score,
        ):
            best_trial = trial
        history.append(
            {
                "trial_no": best_trial.trial_no,
                "oos_score": _score_string(best_trial.score.out_of_sample_score),
                "robustness_score": _score_string(best_trial.score.robustness_score),
            }
        )
    return history


def _score_string(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001")))


def _data_source_label(candle_source: Any) -> str:
    if isinstance(candle_source, Mapping) and candle_source.get("source") == "persisted_candles":
        return "persisted closed candles"
    return "closed-candle offline dataset"


def _request_from_payload(
    payload: Mapping[str, Any],
    *,
    fixture_base_path: Path | None,
) -> dict[str, Any]:
    strategy_config = strategy_config_from_defaults(load_default_config())
    instrument = str(payload.get("instrument") or strategy_config.instrument)
    if instrument != strategy_config.instrument:
        msg = "M6 optimizer uses the configured strategy instrument"
        raise ValueError(msg)

    if "candles" in payload:
        raw_candles = payload["candles"]
        if not isinstance(raw_candles, list):
            msg = "candles must be a list"
            raise TypeError(msg)
        candles = candles_from_records(raw_candles, default_instrument=instrument)
    elif "fixture" in payload:
        if fixture_base_path is None:
            msg = "fixture loading is not configured"
            raise ValueError(msg)
        candles = load_candle_fixture(fixture_base_path / str(payload["fixture"]))
    else:
        msg = "optimization request must include candles or fixture"
        raise ValueError(msg)

    optimizer_config = _optimizer_config_from_payload(payload.get("optimizer_config", {}))
    return {
        "optimizer_config": optimizer_config,
        "runner_kwargs": {
            "candles": candles,
            "base_strategy_config": strategy_config,
            "instrument_rules": _instrument_rules_from_payload(
                payload.get("instrument_rules", {}), instrument
            ),
            "backtest_config": _backtest_config_from_payload(payload.get("backtest_config", {})),
            "optimizer_config": optimizer_config,
            "backtest_runner": run_backtest,
        },
    }


def _optimizer_config_from_payload(raw: Any):
    base = load_optimizer_config().to_jsonable()
    if not isinstance(raw, Mapping):
        msg = "optimizer_config must be an object"
        raise TypeError(msg)
    return optimizer_config_from_mapping(_deep_merge(base, dict(raw)))


def _backtest_config_from_payload(raw: Any) -> BacktestConfig:
    if not isinstance(raw, Mapping):
        msg = "backtest_config must be an object"
        raise TypeError(msg)
    return BacktestConfig(
        initial_nav=raw.get("initial_nav", BacktestConfig.initial_nav),
        spread_pips=raw.get("spread_pips", BacktestConfig.spread_pips),
        slippage_pips=raw.get("slippage_pips", BacktestConfig.slippage_pips),
        commission_per_unit=raw.get("commission_per_unit", BacktestConfig.commission_per_unit),
        ambiguous_fill_policy=raw.get(
            "ambiguous_fill_policy",
            BacktestConfig.ambiguous_fill_policy,
        ),
        force_ny_close=bool(raw.get("force_ny_close", BacktestConfig.force_ny_close)),
    )


def _instrument_rules_from_payload(raw: Any, instrument: str) -> InstrumentRules:
    if not isinstance(raw, Mapping):
        msg = "instrument_rules must be an object"
        raise TypeError(msg)
    return InstrumentRules(
        instrument=instrument,
        pip_location=int(raw.get("pip_location", -4)),
        display_precision=int(raw.get("display_precision", 5)),
        trade_units_precision=int(raw.get("trade_units_precision", 0)),
        minimum_trade_size=Decimal(str(raw.get("minimum_trade_size", "1"))),
        unit_step=Decimal(str(raw.get("unit_step", "1"))),
        quote_home_conversion=Decimal(str(raw.get("quote_home_conversion", "1"))),
    )


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _parse_utc_ts(raw: str) -> datetime:
    value = raw
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None or ts.utcoffset() != _UTC_OFFSET:
        msg = "candle range timestamps must be timezone-aware UTC"
        raise ValueError(msg)
    return ts.astimezone(UTC)
