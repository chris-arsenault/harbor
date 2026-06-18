from pathlib import Path
from typing import Any

import yaml

from harbor_bot.execution.models import PracticeExecutionConfig

DEFAULT_PRACTICE_EXECUTION_CONFIG_PATH = Path(__file__).with_name("defaults.yaml")


def load_practice_execution_config(
    path: Path = DEFAULT_PRACTICE_EXECUTION_CONFIG_PATH,
) -> PracticeExecutionConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "practice execution default config must be a mapping"
        raise ValueError(msg)
    return practice_execution_config_from_mapping(raw)


def practice_execution_config_from_mapping(raw: dict[str, Any]) -> PracticeExecutionConfig:
    return PracticeExecutionConfig(
        mode=raw.get("mode", "practice"),
        trading_enabled_default=bool(raw.get("trading_enabled_default", False)),
        max_open_positions=int(raw.get("max_open_positions", 1)),
        signal_id_namespace=str(raw.get("signal_id_namespace", "harbor-practice")),
        max_daily_loss_pct=raw.get("max_daily_loss_pct", "2.0"),
        max_spread_pips=raw.get("max_spread_pips", "1.5"),
        reconciliation_lag_tolerance_seconds=int(
            raw.get("reconciliation_lag_tolerance_seconds", 30)
        ),
        heartbeat_interval_seconds=int(raw.get("heartbeat_interval_seconds", 300)),
        ny_close_flatten_enabled=bool(raw.get("ny_close_flatten_enabled", True)),
        ntfy_enabled=bool(raw.get("ntfy_enabled", False)),
        telegram_enabled=bool(raw.get("telegram_enabled", False)),
        confirmation_token=str(raw.get("confirmation_token", "OANDA_PRACTICE")),
    )
