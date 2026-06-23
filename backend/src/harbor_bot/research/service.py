"""Service layer for research analyses exposed over the API.

Wraps the pure edge study (ADR 0005) with persisted-candle loading, reusing the
backtester's candle window selection and range reader so the study runs over the
same data the backtester does. Per-instrument: the caller selects the instrument.
"""

from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.backtester.data import candles_from_records
from harbor_bot.backtester.service import (
    read_persisted_candle_records,
    select_latest_complete_candle_window,
)
from harbor_bot.config.defaults import load_default_config
from harbor_bot.instruments import RESEARCH_INSTRUMENTS, default_instrument_rules
from harbor_bot.research.edge import DEFAULT_HORIZON, run_edge_scan, run_edge_study
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
    ) -> dict[str, Any]:
        config = replace(
            strategy_config_from_defaults(load_default_config()), instrument=instrument
        )
        rules = default_instrument_rules(instrument)
        selector = self.window_selector or select_latest_complete_candle_window
        reader = self.candle_reader or read_persisted_candle_records

        window = await selector(
            self.persistence_engine, instrument=instrument, required_days=window_days
        )
        candles: list[Any] = []
        if window is not None:
            records = await reader(
                self.persistence_engine,
                instrument=instrument,
                start=window["from"],
                end=window["to"],
            )
            candles = candles_from_records(records, default_instrument=instrument)

        result = run_edge_study(
            candles,
            instrument=instrument,
            config=config,
            instrument_rules=rules,
            horizon=horizon,
        )
        return result.to_jsonable()

    async def edge_scan(
        self,
        *,
        instruments: tuple[str, ...] | None = None,
        horizons: tuple[int, ...] = (15, 30, 60, 120),
        window_days: int = DEFAULT_RESEARCH_WINDOW_DAYS,
    ) -> dict[str, Any]:
        resolved = instruments or RESEARCH_INSTRUMENTS
        selector = self.window_selector or select_latest_complete_candle_window
        reader = self.candle_reader or read_persisted_candle_records
        all_rows: list[dict[str, Any]] = []

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
            if window is None:
                continue
            records = await reader(
                self.persistence_engine,
                instrument=instrument,
                start=window["from"],
                end=window["to"],
            )
            candles = candles_from_records(records, default_instrument=instrument)
            if not candles:
                continue
            rows = run_edge_scan(
                candles,
                instrument=instrument,
                config=config,
                instrument_rules=rules,
                horizons=horizons,
            )
            all_rows.extend(row.to_jsonable() for row in rows)

        all_rows.sort(key=lambda r: float(r["overall"]["t_stat"]), reverse=True)
        return {
            "instruments": list(resolved),
            "horizons": list(horizons),
            "results": all_rows,
        }
