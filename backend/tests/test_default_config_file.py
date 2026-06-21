from pathlib import Path

import yaml

DEFAULTS_PATH = Path("src/harbor_bot/config/defaults.yaml")

FIXED_VALUES = {
    "instrument": "EUR_USD",
    "timezone": "America/New_York",
    "fvg_window": 8,
    "risk_per_trade_pct": 0.5,
    "max_daily_loss_pct": 2.0,
    "target_mode": "rr_or_liquidity",
    "rr_floor": 2.0,
    "liquidity_rr_floor": 1.0,
    "one_trade_per_level": True,
    "min_forward_days": 20,
}

TUNABLES = {
    "sweep_buffer_pips",
    "max_trades_per_day",
    "max_spread_pips",
    "swing_lookback",
    "max_units",
}


def test_default_config_file_contains_locked_spec_values() -> None:
    defaults = _load_defaults()

    for key, expected in FIXED_VALUES.items():
        assert defaults[key]["value"] == expected

    assert defaults["sessions"]["value"] == {
        "asia": {"start": "20:00", "end": "00:00"},
        "london": {"start": "02:00", "end": "05:00"},
        "ny_trade": {"start": "09:30", "end": "11:30"},
    }


def test_tunable_defaults_are_config_values_with_bounds() -> None:
    defaults = _load_defaults()

    for key in TUNABLES:
        entry = defaults[key]
        assert set(entry) == {"value", "bounds"}
        assert entry["bounds"]["min"] <= entry["value"] <= entry["bounds"]["max"]


def _load_defaults() -> dict:
    assert DEFAULTS_PATH.exists()
    return yaml.safe_load(DEFAULTS_PATH.read_text())
