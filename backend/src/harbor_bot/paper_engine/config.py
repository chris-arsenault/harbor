from pathlib import Path
from typing import Any

import yaml

from harbor_bot.paper_engine.models import PaperEngineConfig

DEFAULT_PAPER_ENGINE_CONFIG_PATH = Path(__file__).with_name("defaults.yaml")


def load_paper_engine_config(
    path: Path = DEFAULT_PAPER_ENGINE_CONFIG_PATH,
) -> PaperEngineConfig:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        msg = "paper engine default config must be a mapping"
        raise ValueError(msg)
    return paper_engine_config_from_mapping(raw)


def paper_engine_config_from_mapping(raw: dict[str, Any]) -> PaperEngineConfig:
    return PaperEngineConfig(
        initial_nav=raw.get("initial_nav", "10000"),
        spread_pips=raw.get("spread_pips", "0.8"),
        slippage_pips=raw.get("slippage_pips", "0.1"),
        commission_per_unit=raw.get("commission_per_unit", "0"),
        ambiguous_fill_policy=raw.get("ambiguous_fill_policy", "pessimistic"),
        force_ny_close=bool(raw.get("force_ny_close", True)),
        live_forward_drawdown_floor=raw.get("live_forward_drawdown_floor", "1"),
        leaderboard_min_trades=int(raw.get("leaderboard_min_trades", 0)),
        max_lab_rows=int(raw.get("max_lab_rows", 200)),
    )
