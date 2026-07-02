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
from harbor_bot.persistence.book_repository import get_book_coverage, list_book_snapshots_range
from harbor_bot.persistence.market_repository import get_candle_coverage
from harbor_bot.research.capture import run_capture_scan
from harbor_bot.research.cross_instrument import (
    available_cross_algorithms,
    default_cross_algorithm_ids,
    run_cross_scan,
)
from harbor_bot.research.directions import (
    RISK_PROXIES,
    SweepProbeEvent,
    available_direction_algorithms,
    default_direction_algorithm_ids,
    run_direction_scan,
)
from harbor_bot.research.edge import (
    DEFAULT_HORIZON,
    adjust_edge_scan_rows_for_universe,
    available_edge_algorithms,
    default_edge_algorithm_ids,
    get_edge_algorithm,
    run_barrier_scan,
    run_edge_scan,
    run_edge_study,
    run_pooled_edge_scan,
)
from harbor_bot.research.triangular_capture import run_triangular_capture
from harbor_bot.strategy.models import strategy_config_from_defaults

DEFAULT_RESEARCH_WINDOW_DAYS = 90


@dataclass(frozen=True)
class ResearchService:
    persistence_engine: AsyncEngine | None = None
    candle_reader: Any = None
    window_selector: Any = None

    async def direction_scan(
        self,
        *,
        instruments: tuple[str, ...] | None = None,
        algorithm_ids: tuple[str, ...] | None = None,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
    ) -> dict[str, Any]:
        resolved = instruments or tuple(dict.fromkeys((*RESEARCH_INSTRUMENTS, *RISK_PROXIES)))
        resolved_algorithms = algorithm_ids or default_direction_algorithm_ids()
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        candles_by_instrument: dict[str, list[Any]] = {}
        sweep_events_by_instrument: dict[str, list[SweepProbeEvent]] = {}
        windows: list[dict[str, Any]] = []
        window_bounds: list[tuple[datetime, datetime]] = []
        warnings: list[dict[str, Any]] = []

        for instrument in resolved:
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
            window_bounds.append((window["from"], window["to"]))
            records = await reader(
                self.persistence_engine,
                instrument=instrument,
                start=window["from"],
                end=window["to"],
            )
            candles = candles_from_records(records, default_instrument=instrument)
            if candles:
                candles_by_instrument[instrument] = list(candles)
                if instrument in RESEARCH_INSTRUMENTS:
                    config = replace(
                        strategy_config_from_defaults(load_default_config()),
                        instrument=instrument,
                    )
                    rules = default_instrument_rules(instrument)
                    ordered = tuple(sorted(candles, key=lambda candle: candle.ts))
                    edge_algorithm = get_edge_algorithm("generic_sweep_reversal")
                    sweep_events_by_instrument[instrument] = [
                        SweepProbeEvent(
                            instrument=instrument,
                            index=event.index,
                            ts=ordered[event.index].ts,
                            bias=event.bias,
                            pip_size=event.pip_size,
                        )
                        for event in edge_algorithm.event_builder(
                            ordered,
                            instrument=instrument,
                            config=config,
                            instrument_rules=rules,
                            atr_window=14,
                        )
                    ]
            else:
                warnings.append(
                    {
                        "instrument": instrument,
                        "type": "empty_window",
                        "message": "selected research window returned no candle rows",
                        "requested_days": window_days,
                    }
                )

        book_coverage: list[dict[str, Any]] = []
        book_snapshots: list[dict[str, Any]] = []
        book_instruments = tuple(i for i in resolved if i in RESEARCH_INSTRUMENTS)
        if self.persistence_engine is not None and book_instruments:
            async with self.persistence_engine.connect() as connection:
                book_coverage = await get_book_coverage(connection, instruments=book_instruments)
                # The jsonable window dicts hold isoformat strings; the range
                # query needs the raw aware datetimes tracked in window_bounds.
                if window_bounds:
                    book_snapshots = await list_book_snapshots_range(
                        connection,
                        instruments=book_instruments,
                        start=min(start for start, _ in window_bounds),
                        end=max(end for _, end in window_bounds),
                    )

        rows = run_direction_scan(
            candles_by_instrument,
            algorithm_ids=resolved_algorithms,
            book_coverage=book_coverage,
            book_snapshots=book_snapshots,
            sweep_events_by_instrument=sweep_events_by_instrument,
        )
        return {
            "instruments": list(resolved),
            "requested_window_days": window_days,
            "windows": windows,
            "warnings": warnings,
            "algorithms": [
                algorithm
                for algorithm in available_direction_algorithms()
                if algorithm["algorithm_id"] in resolved_algorithms
            ],
            "book_coverage": book_coverage,
            "results": [row.to_jsonable() for row in rows],
        }

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
                "overall_multiple_test_method": "benjamini_hochberg",
                "conditional_multiple_test_method": "benjamini_hochberg_per_row",
            },
        }

    async def pooled_edge_scan(
        self,
        *,
        instruments: tuple[str, ...] | None = None,
        horizons: tuple[int, ...] = (15, 30, 60, 120),
        algorithm_ids: tuple[str, ...] | None = None,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
    ) -> dict[str, Any]:
        """Panel scan: pool ATR-normalized sweep observations across the
        instrument universe so realistic (1-4 pip scale) effects become
        statistically resolvable at all."""
        resolved = instruments or RESEARCH_INSTRUMENTS
        resolved_algorithms = algorithm_ids or ("generic_sweep_reversal",)
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        candles_by_instrument: dict[str, list[Any]] = {}
        configs_by_instrument: dict[str, Any] = {}
        rules_by_instrument: dict[str, Any] = {}
        windows: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for instrument in resolved:
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
            candles_by_instrument[instrument] = list(candles)
            configs_by_instrument[instrument] = replace(
                strategy_config_from_defaults(load_default_config()),
                instrument=instrument,
            )
            rules_by_instrument[instrument] = default_instrument_rules(instrument)

        rows = run_pooled_edge_scan(
            candles_by_instrument,
            configs_by_instrument=configs_by_instrument,
            rules_by_instrument=rules_by_instrument,
            horizons=horizons,
            algorithm_ids=resolved_algorithms,
        )
        rows.sort(key=lambda r: float(r.overall.t_stat), reverse=True)
        return {
            "instruments": list(resolved),
            "pooled_instruments": sorted(candles_by_instrument),
            "horizons": list(horizons),
            "requested_window_days": window_days,
            "windows": windows,
            "warnings": warnings,
            "algorithms": [
                algorithm.to_jsonable()
                for algorithm in available_edge_algorithms()
                if algorithm.algorithm_id in resolved_algorithms
            ],
            "results": [row.to_jsonable() for row in rows],
            "statistical_notes": {
                "outcome_unit": "atr",
                "overall_test_count": len(rows),
                "overall_multiple_test_method": "benjamini_hochberg",
                "cluster_unit": "NY trading day across the pooled panel",
            },
        }

    async def barrier_scan(
        self,
        *,
        instrument: str,
        horizons: tuple[int, ...] = (30, 60, 120),
        barrier_r: Any = "1.0",
        algorithm_ids: tuple[str, ...] | None = None,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
    ) -> dict[str, Any]:
        """H116 triple-barrier scoring of event algorithms for one instrument."""
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
        resolved_algorithms = algorithm_ids or ("generic_sweep_reversal",)
        rows = run_barrier_scan(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=rules,
            horizons=horizons,
            barrier_r=Decimal(str(barrier_r)),
            algorithm_ids=resolved_algorithms,
        )
        rows.sort(key=lambda row: float(row.overall.t_stat), reverse=True)
        return {
            "instrument": instrument,
            "horizons": list(horizons),
            "barrier_r": str(Decimal(str(barrier_r))),
            "requested_window_days": window_days,
            "window": _window_jsonable(window),
            "warnings": warnings,
            "algorithms": [
                algorithm.to_jsonable()
                for algorithm in available_edge_algorithms()
                if algorithm.algorithm_id in resolved_algorithms
            ],
            "results": [row.to_jsonable() for row in rows],
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

    async def cross_scan(
        self,
        *,
        instruments: tuple[str, ...] | None = None,
        algorithm_ids: tuple[str, ...] | None = None,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
    ) -> dict[str, Any]:
        resolved = instruments or RESEARCH_INSTRUMENTS
        resolved_algorithms = algorithm_ids or default_cross_algorithm_ids()
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        candles_by_instrument: dict[str, list[Any]] = {}
        windows: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for instrument in resolved:
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
            if candles:
                candles_by_instrument[instrument] = list(candles)
            else:
                warnings.append(
                    {
                        "instrument": instrument,
                        "type": "empty_window",
                        "message": "selected research window returned no candle rows",
                        "requested_days": window_days,
                    }
                )

        rows = run_cross_scan(candles_by_instrument, algorithm_ids=resolved_algorithms)
        return {
            "instruments": list(resolved),
            "requested_window_days": window_days,
            "windows": windows,
            "warnings": warnings,
            "algorithms": [
                algorithm.to_jsonable()
                for algorithm in available_cross_algorithms()
                if algorithm.algorithm_id in resolved_algorithms
            ],
            "results": [row.to_jsonable() for row in rows],
        }

    def cross_algorithms(self) -> dict[str, Any]:
        return {
            "algorithms": [algorithm.to_jsonable() for algorithm in available_cross_algorithms()]
        }

    async def triangular_capture(
        self,
        *,
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
        thresholds: tuple[float, ...] = (1.0, 1.5, 2.0),
        horizons: tuple[int, ...] = (1, 3, 5, 10),
        cost_bps_per_leg: float = 1.5,
    ) -> dict[str, Any]:
        instruments = ("EUR_USD", "GBP_USD", "EUR_GBP")
        selector = self.window_selector or select_latest_research_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        candles_by_instrument: dict[str, list[Any]] = {}
        windows: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for instrument in instruments:
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
            if candles:
                candles_by_instrument[instrument] = list(candles)
            else:
                warnings.append(
                    {
                        "instrument": instrument,
                        "type": "empty_window",
                        "message": "selected research window returned no candle rows",
                        "requested_days": window_days,
                    }
                )
        rows = run_triangular_capture(
            candles_by_instrument,
            thresholds=thresholds,
            horizons=horizons,
            cost_bps_per_leg=cost_bps_per_leg,
        )
        return {
            "instruments": list(instruments),
            "requested_window_days": window_days,
            "thresholds": [f"{value:.4f}" for value in thresholds],
            "horizons": list(horizons),
            "cost_bps_per_leg": f"{cost_bps_per_leg:.4f}",
            "windows": windows,
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
