from decimal import Decimal
from typing import Any

import optuna

from harbor_bot.optimizer.config import apply_params_to_strategy_config
from harbor_bot.optimizer.models import SearchParameter, SearchParameterType, SearchSpace
from harbor_bot.strategy.models import StrategyConfig


def sample_search_space(
    trial: optuna.trial.Trial | optuna.trial.FixedTrial,
    search_space: SearchSpace,
) -> dict[str, Any]:
    return {
        parameter.name: _sample_parameter(trial, parameter) for parameter in search_space.parameters
    }


def strategy_config_for_params(
    base_config: StrategyConfig,
    params: dict[str, Any],
) -> StrategyConfig:
    return apply_params_to_strategy_config(base_config, params)


def _sample_parameter(
    trial: optuna.trial.Trial | optuna.trial.FixedTrial,
    parameter: SearchParameter,
) -> Any:
    if parameter.parameter_type == SearchParameterType.INT:
        return trial.suggest_int(
            parameter.name,
            int(parameter.minimum),
            int(parameter.maximum),
            step=int(parameter.step or 1),
        )
    if parameter.parameter_type == SearchParameterType.DECIMAL:
        value = trial.suggest_float(
            parameter.name,
            float(parameter.minimum),
            float(parameter.maximum),
            step=float(parameter.step) if parameter.step is not None else None,
        )
        return str(Decimal(str(value)))
    return trial.suggest_categorical(parameter.name, list(parameter.choices))
