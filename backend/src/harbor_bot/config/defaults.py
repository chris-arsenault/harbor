from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).with_name("defaults.yaml")


def load_default_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        msg = "default config must be a mapping"
        raise ValueError(msg)
    return raw
