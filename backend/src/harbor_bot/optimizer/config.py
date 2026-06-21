from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from harbor_bot.optimizer.models import (
    OptimizationConfig,
    SearchParameter,
    SearchParameterType,
    SearchSpace,
    WalkForwardConfig,
)
from harbor_bot.strategy.models import StrategyConfig

DEFAULT_OPTIMIZER_CONFIG_PATH = Path(__file__).with_name("defaults.yaml")

_SESSION_OFFSET_PARAMS = {
    "asia_start_offset_minutes": ("asia", "start"),
    "asia_end_offset_minutes": ("asia", "end"),
    "london_start_offset_minutes": ("london", "start"),
    "london_end_offset_minutes": ("london", "end"),
    "ny_trade_start_offset_minutes": ("ny_trade", "start"),
    "ny_trade_end_offset_minutes": ("ny_trade", "end"),
}


def load_optimizer_config(path: Path = DEFAULT_OPTIMIZER_CONFIG_PATH) -> OptimizationConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "optimizer defaults must be a mapping"
        raise ValueError(msg)
    return optimizer_config_from_mapping(raw)


def optimizer_config_from_mapping(raw: dict[str, Any]) -> OptimizationConfig:
    minimum_trade_count = raw["minimum_trade_count"]
    robustness = raw["robustness"]
    walk_forward = raw["walk_forward"]
    return OptimizationConfig(
        search_space=_search_space_from_mapping(raw["search_space"]),
        walk_forward=WalkForwardConfig(
            train_window_days=int(walk_forward["train_window_days"]),
            oos_window_days=int(walk_forward["oos_window_days"]),
            step_days=int(walk_forward["step_days"]),
        ),
        trial_count=int(raw["trial_count"]),
        candidate_count=int(raw["candidate_count"]),
        tpe_seed=int(raw["tpe_seed"]),
        min_in_sample_trades=int(minimum_trade_count["in_sample"]),
        min_oos_trades=int(minimum_trade_count["out_of_sample"]),
        drawdown_floor=Decimal(str(raw["drawdown_floor"])),
        robustness_neighbor_count=int(robustness["neighbor_count"]),
        robustness_step_scale=Decimal(str(robustness["step_scale"])),
    )


def apply_params_to_strategy_config(
    config: StrategyConfig,
    params: dict[str, Any],
) -> StrategyConfig:
    sessions = {name: dict(window) for name, window in config.sessions.items()}
    for param_name, (session_name, boundary_name) in _SESSION_OFFSET_PARAMS.items():
        if param_name in params:
            sessions[session_name][boundary_name] = _offset_time(
                sessions[session_name][boundary_name],
                int(params[param_name]),
            )

    return replace(
        config,
        sessions=sessions,
        sweep_buffer_pips=_decimal_param(params, "sweep_buffer_pips", config.sweep_buffer_pips),
        fvg_window=int(params.get("fvg_window", config.fvg_window)),
        swing_lookback=int(params.get("swing_lookback", config.swing_lookback)),
        target_mode=str(params.get("target_mode", config.target_mode)),
        rr_floor=_decimal_param(params, "rr_floor", config.rr_floor),
        liquidity_rr_floor=_decimal_param(
            params,
            "liquidity_rr_floor",
            config.liquidity_rr_floor,
        ),
        max_spread_pips=_decimal_param(params, "max_spread_pips", config.max_spread_pips),
        max_trades_per_day=int(params.get("max_trades_per_day", config.max_trades_per_day)),
    )


def _search_space_from_mapping(raw: dict[str, Any]) -> SearchSpace:
    return SearchSpace(
        tuple(_search_parameter_from_mapping(name, value) for name, value in raw.items())
    )


def _search_parameter_from_mapping(name: str, raw: dict[str, Any]) -> SearchParameter:
    parameter_type = SearchParameterType(raw["type"])
    if parameter_type == SearchParameterType.CATEGORICAL:
        return SearchParameter(
            name=name,
            parameter_type=parameter_type,
            choices=tuple(raw["choices"]),
        )
    return SearchParameter(
        name=name,
        parameter_type=parameter_type,
        minimum=Decimal(str(raw["min"])),
        maximum=Decimal(str(raw["max"])),
        step=Decimal(str(raw["step"])) if "step" in raw else None,
    )


def _offset_time(value: str, offset_minutes: int) -> str:
    base = datetime.strptime(value, "%H:%M")
    shifted = base + timedelta(minutes=offset_minutes)
    return shifted.strftime("%H:%M")


def _decimal_param(params: dict[str, Any], key: str, default: Decimal) -> Decimal:
    if key not in params:
        return default
    return Decimal(str(params[key]))
