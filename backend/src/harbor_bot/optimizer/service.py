from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.backtester.data import candles_from_records, load_candle_fixture
from harbor_bot.backtester.models import BacktestConfig
from harbor_bot.config.defaults import load_default_config
from harbor_bot.optimizer.config import load_optimizer_config, optimizer_config_from_mapping
from harbor_bot.optimizer.models import OptimizationStatus
from harbor_bot.optimizer.runner import OptimizationRunResult, run_optimization
from harbor_bot.persistence.market_repository import list_candles_range
from harbor_bot.persistence.optimization_repository import append_optimization_run
from harbor_bot.strategy.models import InstrumentRules, strategy_config_from_defaults

OptimizationRunner = Callable[..., OptimizationRunResult]
PersistenceWriter = Callable[..., Awaitable[int]]
CandleRangeReader = Callable[..., Awaitable[list[dict[str, Any]]]]
_UTC_OFFSET = timedelta(0)


@dataclass(frozen=True)
class OptimizerService:
    persistence_engine: AsyncEngine | None = None
    fixture_base_path: Path | None = None
    optimization_runner: OptimizationRunner = run_optimization
    persistence_writer: PersistenceWriter = append_optimization_run
    candle_reader: CandleRangeReader = None

    async def start_optimization(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = await _payload_with_persisted_candles(
            payload,
            engine=self.persistence_engine,
            candle_reader=self.candle_reader or read_persisted_candle_records,
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
        return optimization_result_to_response(result, study_id=study_id)


def optimization_result_to_response(
    result: OptimizationRunResult,
    *,
    study_id: int | None = None,
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
            }
            for trial in result.trials
        ],
        "data_separation": {
            "source": "closed-candle offline dataset",
            "no_live_forward_data": True,
            "variant_trades_used": False,
            "oanda_streams_used": False,
            "broker_state_used": False,
            "paper_engine_used": False,
            "frontend_ui_used": False,
        },
    }


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


async def _payload_with_persisted_candles(
    payload: Mapping[str, Any],
    *,
    engine: AsyncEngine | None,
    candle_reader: CandleRangeReader,
) -> dict[str, Any]:
    if "candles" in payload or "fixture" in payload:
        return dict(payload)
    if payload.get("source") != "persisted_candles" and "candle_range" not in payload:
        return dict(payload)

    strategy_config = strategy_config_from_defaults(load_default_config())
    instrument = str(payload.get("instrument") or strategy_config.instrument)
    raw_range = payload.get("candle_range")
    if not isinstance(raw_range, Mapping):
        msg = "candle_range must include from and to"
        raise TypeError(msg)
    start = _parse_utc_ts(str(raw_range["from"]))
    end = _parse_utc_ts(str(raw_range["to"]))
    candles = await candle_reader(engine, instrument=instrument, start=start, end=end)
    next_payload = dict(payload)
    next_payload["candles"] = candles
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
