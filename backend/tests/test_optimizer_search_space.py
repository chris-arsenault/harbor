from decimal import Decimal

import optuna

from harbor_bot.config.defaults import load_default_config
from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import (
    SearchParameter,
    SearchParameterType,
    SearchSpace,
)
from harbor_bot.optimizer.search_space import sample_search_space, strategy_config_for_params
from harbor_bot.strategy.models import strategy_config_from_defaults


def test_sample_search_space_uses_optuna_trial_suggest_methods_and_jsonable_values() -> None:
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
            SearchParameter(
                name="max_trades_per_day",
                parameter_type=SearchParameterType.CATEGORICAL,
                choices=(1, 2, 3),
            ),
        )
    )
    trial = optuna.trial.FixedTrial(
        {
            "fvg_window": 8,
            "rr_floor": 2.5,
            "max_trades_per_day": 2,
        }
    )

    assert sample_search_space(trial, search_space) == {
        "fvg_window": 8,
        "rr_floor": "2.5",
        "max_trades_per_day": 2,
    }


def test_default_search_space_samples_all_configured_parameters() -> None:
    config = load_optimizer_config()
    trial = optuna.trial.FixedTrial(
        {
            "asia_start_offset_minutes": 0,
            "asia_end_offset_minutes": 0,
            "london_start_offset_minutes": 0,
            "london_end_offset_minutes": 0,
            "ny_trade_start_offset_minutes": 15,
            "ny_trade_end_offset_minutes": -15,
            "sweep_buffer_pips": 2.0,
            "fvg_window": 8,
            "swing_lookback": 5,
            "rr_floor": 2.5,
            "liquidity_rr_floor": 1.0,
            "target_mode": "rr_or_liquidity",
            "require_mss": False,
            "exit_mode": "bracket",
            "max_spread_pips": 1.2,
            "max_trades_per_day": 2,
        }
    )

    params = sample_search_space(trial, config.search_space)

    assert set(params) == set(config.search_space.by_name())
    assert params["ny_trade_start_offset_minutes"] == 15
    assert params["sweep_buffer_pips"] == "2.0"
    assert params["rr_floor"] == "2.5"
    assert params["liquidity_rr_floor"] == "1.0"
    assert params["target_mode"] == "rr_or_liquidity"


def test_strategy_config_for_params_updates_variant_without_mutating_defaults() -> None:
    base = strategy_config_from_defaults(load_default_config())
    variant = strategy_config_for_params(
        base,
        {
            "ny_trade_start_offset_minutes": 15,
            "ny_trade_end_offset_minutes": -15,
            "target_mode": "rr",
            "rr_floor": "2.5",
            "liquidity_rr_floor": "1.5",
            "fvg_window": 10,
        },
    )

    assert variant.sessions["ny_trade"] == {"start": "09:45", "end": "11:15"}
    assert variant.target_mode == "rr"
    assert variant.rr_floor == Decimal("2.5")
    assert variant.liquidity_rr_floor == Decimal("1.5")
    assert variant.fvg_window == 10
    assert base.sessions["ny_trade"] == {"start": "09:30", "end": "11:30"}
    assert variant.instrument == "EUR_USD"
