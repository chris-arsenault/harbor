"""Service layer for research analyses exposed over the API.

Wraps the pure edge study (ADR 0005) with persisted-candle loading, reusing the
backtester's candle window selection and range reader so the study runs over the
same data the backtester does. Per-instrument: the caller selects the instrument.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.backtester.data import candles_from_records
from harbor_bot.backtester.service import read_persisted_candle_records
from harbor_bot.config.defaults import load_default_config
from harbor_bot.instruments import RESEARCH_INSTRUMENTS, default_instrument_rules
from harbor_bot.persistence.market_repository import get_candle_coverage
from harbor_bot.research.capture import run_capture_scan
from harbor_bot.research.edge import (
    DEFAULT_HORIZON,
    adjust_edge_scan_rows_for_universe,
    available_edge_algorithms,
    default_edge_algorithm_ids,
    run_edge_scan,
    run_edge_study,
)
from harbor_bot.strategy.models import strategy_config_from_defaults

DEFAULT_RESEARCH_WINDOW_DAYS = 90


@dataclass(frozen=True)
class ResearchService:
    persistence_engine: AsyncEngine | None = None
    candle_reader: Any = None
    window_selector: Any = None

    async def edge_study(
        self,
        *,
        instrument: str,
        horizon: int = DEFAULT_HORIZON,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
        algorithm_id: str = "generic_sweep_reversal",
    ) -> dict[str, Any]:
        config = replace(
            strategy_config_from_defaults(load_default_config()), instrument=instrument
        )
        rules = default_instrument_rules(instrument)
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records

        window = await selector(
            self.persistence_engine, instrument=instrument, required_days=window_days
        )
        warnings = _window_warnings(window, instrument=instrument, requested_days=window_days)
        candles: list[Any] = []
        if window is not None:
            records = await reader(
                self.persistence_engine,
                instrument=instrument,
                start=window["from"],
                end=window["to"],
            )
            candles = candles_from_records(records, default_instrument=instrument)
            if not candles:
                warnings.append(
                    {
                        "instrument": instrument,
                        "type": "empty_window",
                        "message": "selected research window returned no candle rows",
                        "requested_days": window_days,
                    }
                )

        result = run_edge_study(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=rules,
            horizon=horizon,
            algorithm_id=algorithm_id,
        )
        response = result.to_jsonable()
        response["window"] = _window_jsonable(window)
        response["warnings"] = warnings
        return response

    async def edge_scan(
        self,
        *,
        instruments: tuple[str, ...] | None = None,
        horizons: tuple[int, ...] = (15, 30, 60, 120),
        algorithm_ids: tuple[str, ...] | None = None,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
    ) -> dict[str, Any]:
        resolved = instruments or RESEARCH_INSTRUMENTS
        resolved_algorithms = algorithm_ids or default_edge_algorithm_ids()
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        all_rows: list[Any] = []
        windows: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for instrument in resolved:
            config = replace(
                strategy_config_from_defaults(load_default_config()),
                instrument=instrument,
            )
            rules = default_instrument_rules(instrument)
            window = await selector(
                self.persistence_engine,
                instrument=instrument,
                required_days=window_days,
            )
            warnings.extend(
                _window_warnings(window, instrument=instrument, requested_days=window_days)
            )
            if window is None:
                continue
            windows.append(_window_jsonable(window))
            records = await reader(
                self.persistence_engine,
                instrument=instrument,
                start=window["from"],
                end=window["to"],
            )
            candles = candles_from_records(records, default_instrument=instrument)
            if not candles:
                warnings.append(
                    {
                        "instrument": instrument,
                        "type": "empty_window",
                        "message": "selected research window returned no candle rows",
                        "requested_days": window_days,
                    }
                )
                continue
            rows = run_edge_scan(
                candles,
                instrument=instrument,
                config=config,
                instrument_rules=rules,
                horizons=horizons,
                algorithm_ids=resolved_algorithms,
            )
            all_rows.extend(rows)

        adjusted_rows = adjust_edge_scan_rows_for_universe(all_rows)
        adjusted_rows.sort(key=lambda r: float(r.overall.t_stat), reverse=True)
        return {
            "instruments": list(resolved),
            "horizons": list(horizons),
            "requested_window_days": window_days,
            "windows": windows,
            "warnings": warnings,
            "algorithms": [
                algorithm.to_jsonable()
                for algorithm in available_edge_algorithms()
                if algorithm.algorithm_id in resolved_algorithms
            ],
            "results": [row.to_jsonable() for row in adjusted_rows],
            "statistical_notes": {
                "instrument_count": len(resolved),
                "algorithm_count": len(resolved_algorithms),
                "horizon_count": len(horizons),
                "planned_overall_test_count": (
                    len(resolved) * len(resolved_algorithms) * len(horizons)
                ),
                "overall_test_count": len(adjusted_rows),
                "overall_multiple_test_method": "bonferroni",
                "conditional_multiple_test_method": "bonferroni_per_row",
            },
        }

    async def capture_scan(
        self,
        *,
        instrument: str = "EUR_USD",
        horizons: tuple[int, ...] = (15, 30, 60),
        algorithm_ids: tuple[str, ...] = (
            "generic_sweep_continuation",
            "early_ny_sweep_continuation",
        ),
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
        spread_pips: Any = "0.8",
        slippage_pips: Any = "0.1",
    ) -> dict[str, Any]:
        config = replace(
            strategy_config_from_defaults(load_default_config()),
            instrument=instrument,
        )
        rules = default_instrument_rules(instrument)
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        window = await selector(
            self.persistence_engine,
            instrument=instrument,
            required_days=window_days,
        )
        warnings = _window_warnings(window, instrument=instrument, requested_days=window_days)
        candles: list[Any] = []
        if window is not None:
            records = await reader(
                self.persistence_engine,
                instrument=instrument,
                start=window["from"],
                end=window["to"],
            )
            candles = candles_from_records(records, default_instrument=instrument)
            if not candles:
                warnings.append(
                    {
                        "instrument": instrument,
                        "type": "empty_window",
                        "message": "selected research window returned no candle rows",
                        "requested_days": window_days,
                    }
                )
        rows = run_capture_scan(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=rules,
            algorithm_ids=algorithm_ids,
            horizons=horizons,
            spread_pips=Decimal(str(spread_pips)),
            slippage_pips=Decimal(str(slippage_pips)),
        )
        rows.sort(key=lambda row: row.stats.mean_net_pips, reverse=True)
        return {
            "instrument": instrument,
            "horizons": list(horizons),
            "algorithms": [
                algorithm.to_jsonable()
                for algorithm in available_edge_algorithms()
                if algorithm.algorithm_id in algorithm_ids
            ],
            "spread_pips": str(Decimal(str(spread_pips))),
            "slippage_pips": str(Decimal(str(slippage_pips))),
            "requested_window_days": window_days,
            "window": _window_jsonable(window),
            "warnings": warnings,
            "results": [row.to_jsonable() for row in rows],
        }

    def edge_algorithms(self) -> dict[str, Any]:
        return {
            "algorithms": [algorithm.to_jsonable() for algorithm in available_edge_algorithms()]
        }


async def select_latest_research_candle_window(
    engine: AsyncEngine | None,
    *,
    instrument: str,
    required_days: int,
) -> dict[str, Any] | None:
    """Select the latest available calendar window for research scans.

    Unlike backtests, research scans should not fail just because fewer complete
    trading dates exist than requested. ``required_days`` is interpreted as a
    calendar lookback; if less data exists, the returned window uses all available
    data and carries an explicit warning.
    """
    if engine is None:
        msg = "persisted candle range requests require a persistence engine"
        raise ValueError(msg)
    async with engine.connect() as connection:
        coverage = await get_candle_coverage(connection, instrument=instrument)
    return research_window_from_coverage(
        coverage,
        instrument=instrument,
        requested_days=required_days,
    )


def research_window_from_coverage(
    coverage: dict[str, Any],
    *,
    instrument: str,
    requested_days: int,
) -> dict[str, Any] | None:
    if requested_days <= 0:
        msg = "requested_days must be positive"
        raise ValueError(msg)
    if int(coverage.get("candle_count", 0)) == 0 or coverage.get("from") is None:
        return None

    coverage_from = _as_utc(coverage["from"])
    coverage_to = _as_utc(coverage["to"])
    available_days = max(1, (coverage_to.date() - coverage_from.date()).days + 1)
    requested_start = coverage_to - timedelta(days=requested_days)
    start = max(coverage_from, requested_start)
    used_days = max(1, min(requested_days, (coverage_to.date() - start.date()).days + 1))
    warnings: list[dict[str, Any]] = []
    if available_days < requested_days:
        warnings.append(
            {
                "instrument": instrument,
                "type": "partial_window",
                "message": (
                    f"requested {requested_days} calendar days but only {available_days} "
                    "calendar days of persisted complete candles are available"
                ),
                "requested_days": requested_days,
                "available_days": available_days,
                "used_days": used_days,
            }
        )
    return {
        "instrument": instrument,
        "from": start,
        "to": coverage_to,
        "requested_days": requested_days,
        "available_days": available_days,
        "used_days": used_days,
        "coverage": coverage,
        "warnings": warnings,
    }


def _window_warnings(
    window: dict[str, Any] | None,
    *,
    instrument: str,
    requested_days: int,
) -> list[dict[str, Any]]:
    if window is None:
        return [
            {
                "instrument": instrument,
                "type": "no_data",
                "message": "no persisted complete candles are available for this instrument",
                "requested_days": requested_days,
            }
        ]
    return [dict(warning) for warning in window.get("warnings", [])]


def _window_jsonable(window: dict[str, Any] | None) -> dict[str, Any] | None:
    if window is None:
        return None
    return {
        "instrument": window.get("instrument"),
        "from": window["from"].isoformat(),
        "to": window["to"].isoformat(),
        "requested_days": window.get("requested_days"),
        "available_days": window.get("available_days"),
        "used_days": window.get("used_days"),
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
