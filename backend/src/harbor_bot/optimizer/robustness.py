from collections.abc import Callable
from decimal import Decimal

from harbor_bot.optimizer.models import (
    OptimizationConfig,
    SearchParameter,
    SearchParameterType,
    SearchSpace,
)
from harbor_bot.optimizer.objective import ObjectiveEvaluation

ObjectiveEvaluator = Callable[[dict[str, object]], ObjectiveEvaluation]


def generate_neighbor_params(
    params: dict[str, object],
    search_space: SearchSpace,
    optimizer_config: OptimizationConfig,
) -> tuple[dict[str, object], ...]:
    neighbors: list[dict[str, object]] = []
    for parameter in search_space.parameters:
        if len(neighbors) >= optimizer_config.robustness_neighbor_count:
            break
        if (
            parameter.name not in params
            or parameter.parameter_type == SearchParameterType.CATEGORICAL
        ):
            continue
        for direction in (-1, 1):
            neighbor_value = _neighbor_value(
                value=params[parameter.name],
                parameter=parameter,
                direction=direction,
                optimizer_config=optimizer_config,
            )
            if neighbor_value is None:
                continue
            neighbor = dict(params)
            neighbor[parameter.name] = neighbor_value
            neighbors.append(neighbor)
            if len(neighbors) >= optimizer_config.robustness_neighbor_count:
                break
    return tuple(neighbors)


def calculate_robustness_score(
    *,
    params: dict[str, object],
    base_oos_score: Decimal,
    search_space: SearchSpace,
    optimizer_config: OptimizationConfig,
    objective_evaluator: ObjectiveEvaluator,
) -> Decimal:
    neighbors = generate_neighbor_params(params, search_space, optimizer_config)
    if not neighbors:
        return base_oos_score
    neighbor_scores = [_neighbor_score(neighbor, objective_evaluator) for neighbor in neighbors]
    average_neighbor_score = sum(neighbor_scores, Decimal("0")) / Decimal(len(neighbor_scores))
    return min(base_oos_score, average_neighbor_score)


def _neighbor_score(
    neighbor: dict[str, object],
    objective_evaluator: ObjectiveEvaluator,
) -> Decimal:
    try:
        return objective_evaluator(neighbor).score.out_of_sample_score
    except ValueError:
        return Decimal("0")


def _neighbor_value(
    *,
    value: object,
    parameter: SearchParameter,
    direction: int,
    optimizer_config: OptimizationConfig,
) -> object | None:
    step = (parameter.step or Decimal("1")) * optimizer_config.robustness_step_scale
    candidate = Decimal(str(value)) + (step * Decimal(direction))
    if candidate < parameter.minimum or candidate > parameter.maximum:
        return None
    if parameter.parameter_type == SearchParameterType.INT:
        return int(candidate)
    return str(candidate)
