from decimal import Decimal

from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import (
    SearchParameter,
    SearchParameterType,
    SearchSpace,
    TrialScore,
)
from harbor_bot.optimizer.objective import ObjectiveEvaluation
from harbor_bot.optimizer.robustness import calculate_robustness_score, generate_neighbor_params


def test_generate_neighbor_params_steps_numeric_parameters_within_bounds() -> None:
    config = load_optimizer_config()
    search_space = SearchSpace(
        (
            SearchParameter(
                name="fvg_window",
                parameter_type=SearchParameterType.INT,
                minimum=Decimal("1"),
                maximum=Decimal("20"),
                step=Decimal("1"),
            ),
            SearchParameter(
                name="rr_floor",
                parameter_type=SearchParameterType.DECIMAL,
                minimum=Decimal("1.0"),
                maximum=Decimal("4.0"),
                step=Decimal("0.5"),
            ),
        )
    )

    neighbors = generate_neighbor_params(
        {"fvg_window": 8, "rr_floor": "2.0"},
        search_space,
        config,
    )

    assert neighbors == (
        {"fvg_window": 7, "rr_floor": "2.0"},
        {"fvg_window": 9, "rr_floor": "2.0"},
    )


def test_generate_neighbor_params_skips_out_of_bounds_neighbors() -> None:
    config = load_optimizer_config()
    search_space = SearchSpace(
        (
            SearchParameter(
                name="fvg_window",
                parameter_type=SearchParameterType.INT,
                minimum=Decimal("1"),
                maximum=Decimal("2"),
                step=Decimal("1"),
            ),
        )
    )

    assert generate_neighbor_params({"fvg_window": 1}, search_space, config) == ({"fvg_window": 2},)


def test_robustness_score_penalizes_lone_spikes_with_neighbor_average() -> None:
    config = load_optimizer_config()
    search_space = SearchSpace(
        (
            SearchParameter(
                name="fvg_window",
                parameter_type=SearchParameterType.INT,
                minimum=Decimal("1"),
                maximum=Decimal("20"),
                step=Decimal("1"),
            ),
        )
    )
    observed_neighbors = []

    def evaluator(params: dict[str, object]) -> ObjectiveEvaluation:
        observed_neighbors.append(params)
        return ObjectiveEvaluation(
            params=params,
            score=TrialScore(
                in_sample_score=Decimal("0"),
                out_of_sample_score=Decimal(str(params["fvg_window"])),
            ),
            in_sample_stats=None,
            out_of_sample_stats=None,
            windows_evaluated=1,
        )

    score = calculate_robustness_score(
        params={"fvg_window": 10},
        base_oos_score=Decimal("100"),
        search_space=search_space,
        optimizer_config=config,
        objective_evaluator=evaluator,
    )

    assert observed_neighbors == [{"fvg_window": 9}, {"fvg_window": 11}]
    assert score == Decimal("10")
