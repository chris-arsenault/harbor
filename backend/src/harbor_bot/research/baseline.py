"""Reproducible backtest baseline capture (pure).

Anchors the current midpoint-fill backtest stats over canonical fixtures so
later fill-realism work (ADR 0006) can report an expectancy-survival delta
against a committed "before" reference rather than a remembered number.
"""

from decimal import Decimal
from typing import Any

from harbor_bot.backtester.models import BacktestRunResult
from harbor_bot.backtester.stats import result_snapshot


def baseline_from_results(results: dict[str, BacktestRunResult]) -> dict[str, Any]:
    """Snapshot each named backtest result into a stable, JSON-able baseline."""
    return {name: result_snapshot(results[name]) for name in sorted(results)}


def _expectancy(entry: dict[str, Any]) -> Decimal:
    return Decimal(str(entry.get("stats", {}).get("expectancy", "0")))


def expectancy_delta(
    recorded: dict[str, Any], current: dict[str, Any]
) -> dict[str, dict[str, str]]:
    """Per-fixture expectancy survival: current run versus the recorded baseline."""
    delta: dict[str, dict[str, str]] = {}
    for name in sorted(recorded):
        before = _expectancy(recorded[name])
        after = _expectancy(current.get(name, {}))
        delta[name] = {
            "before": str(before),
            "after": str(after),
            "delta": str(after - before),
        }
    return delta
