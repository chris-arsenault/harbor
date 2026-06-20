from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.optimizer.config import (
    apply_params_to_strategy_config,
    load_optimizer_config,
    optimizer_config_from_mapping,
)
from harbor_bot.optimizer.models import (
    CandidateVariant,
    OptimizationConfig,
    OptimizationStatus,
    SearchParameter,
    SearchParameterType,
    SearchSpace,
    TrialRecord,
    TrialScore,
)
from harbor_bot.strategy.models import strategy_config_from_defaults


def test_optimizer_defaults_load_bounded_search_space_and_runtime_config() -> None:
    config = load_optimizer_config()

    assert isinstance(config, OptimizationConfig)
    assert config.trial_count == 32
    assert config.candidate_count == 5
    assert config.tpe_seed == 17
    assert config.drawdown_floor == Decimal("1")
    assert config.min_in_sample_trades == 3
    assert config.min_oos_trades == 1
    assert config.robustness_neighbor_count == 1
    assert config.walk_forward.train_window_days == 10
    assert config.walk_forward.oos_window_days == 5
    assert config.walk_forward.step_days == 5

    names = set(config.search_space.by_name())
    assert names == {
        "asia_start_offset_minutes",
        "asia_end_offset_minutes",
        "london_start_offset_minutes",
        "london_end_offset_minutes",
        "ny_trade_start_offset_minutes",
        "ny_trade_end_offset_minutes",
        "sweep_buffer_pips",
        "fvg_window",
        "swing_lookback",
        "rr_floor",
        "max_spread_pips",
        "max_trades_per_day",
    }
    assert config.search_space.by_name()["sweep_buffer_pips"].minimum == Decimal("0.5")
    assert config.to_jsonable()["search_space"]["rr_floor"]["max"] == "4.0"


def test_search_parameter_validation_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError, match="minimum cannot exceed maximum"):
        SearchParameter(
            name="fvg_window",
            parameter_type=SearchParameterType.INT,
            minimum=Decimal("10"),
            maximum=Decimal("1"),
        )
    with pytest.raises(ValueError, match="choices"):
        SearchParameter(name="target_mode", parameter_type=SearchParameterType.CATEGORICAL)
    with pytest.raises(ValueError, match="unique"):
        SearchSpace(
            (
                SearchParameter(
                    name="fvg_window",
                    parameter_type=SearchParameterType.INT,
                    minimum=Decimal("1"),
                    maximum=Decimal("2"),
                ),
                SearchParameter(
                    name="fvg_window",
                    parameter_type=SearchParameterType.INT,
                    minimum=Decimal("1"),
                    maximum=Decimal("2"),
                ),
            )
        )


def test_optimizer_config_validation_rejects_bad_runtime_values() -> None:
    raw = load_optimizer_config().to_jsonable()
    raw["trial_count"] = 0

    with pytest.raises(ValueError, match="trial_count"):
        optimizer_config_from_mapping(raw)


def test_apply_params_to_strategy_config_keeps_locked_fields_and_updates_search_fields() -> None:
    base = strategy_config_from_defaults(load_default_config())
    updated = apply_params_to_strategy_config(
        base,
        {
            "ny_trade_start_offset_minutes": 15,
            "ny_trade_end_offset_minutes": -15,
            "sweep_buffer_pips": "2.0",
            "fvg_window": 12,
            "swing_lookback": 7,
            "rr_floor": "2.5",
            "max_spread_pips": "1.5",
            "max_trades_per_day": 3,
        },
    )

    assert updated.instrument == base.instrument
    assert updated.timezone == base.timezone
    assert updated.target_mode == "rr_or_liquidity"
    assert updated.risk_per_trade_pct == base.risk_per_trade_pct
    assert updated.max_daily_loss_pct == base.max_daily_loss_pct
    assert updated.sessions["ny_trade"] == {"start": "09:45", "end": "11:15"}
    assert updated.sweep_buffer_pips == Decimal("2.0")
    assert updated.fvg_window == 12
    assert updated.swing_lookback == 7
    assert updated.rr_floor == Decimal("2.5")
    assert updated.max_spread_pips == Decimal("1.5")
    assert updated.max_trades_per_day == 3
    assert base.sessions["ny_trade"] == {"start": "09:30", "end": "11:30"}


def test_trial_and_candidate_models_are_immutable_and_paper_only() -> None:
    score = TrialScore(
        in_sample_score=Decimal("1.2"),
        out_of_sample_score=Decimal("0.8"),
        robustness_score=Decimal("0.7"),
    )
    trial = TrialRecord(trial_no=1, params={"fvg_window": 8}, score=score)
    candidate = CandidateVariant(label="variant-1", params=trial.params, source_trial_no=1)

    assert OptimizationStatus.COMPLETED.value == "completed"
    assert trial.params == {"fvg_window": 8}
    assert candidate.status == "paper"
    with pytest.raises(FrozenInstanceError):
        trial.trial_no = 2
    with pytest.raises(ValueError, match="paper"):
        CandidateVariant(label="bad", params={}, source_trial_no=1, status="promoted")
