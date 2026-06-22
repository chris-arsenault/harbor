from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.backtester.data import candles_from_records, load_candle_fixture
from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestConfig, BacktestInput, BacktestRunResult
from harbor_bot.config.defaults import load_default_config
from harbor_bot.instruments import default_instrument_rules
from harbor_bot.optimizer.config import apply_params_to_strategy_config
from harbor_bot.persistence.backtest_repository import append_backtest_result, get_backtest_run
from harbor_bot.persistence.market_repository import (
    latest_complete_candle_window,
    list_candles_range,
)
from harbor_bot.strategy.models import (
    InstrumentRules,
    StrategyConfig,
    strategy_config_from_defaults,
)

CandleRangeReader = Callable[..., Awaitable[list[dict[str, Any]]]]
BacktestWindowSelector = Callable[..., Awaitable[dict[str, Any] | None]]
BacktestRunner = Callable[[BacktestInput], BacktestRunResult]
_UTC_OFFSET = timedelta(0)
DEFAULT_BACKTEST_WINDOW_DAYS = 30


@dataclass(frozen=True)
class BacktestService:
    persistence_engine: AsyncEngine | None = None
    fixture_base_path: Path | None = None
    candle_reader: CandleRangeReader = None
    candle_window_selector: BacktestWindowSelector = None
    backtest_runner: BacktestRunner = run_backtest

    async def start_backtest(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        payload = await _payload_with_persisted_candles(
            payload,
            engine=self.persistence_engine,
            fixture_base_path=self.fixture_base_path,
            candle_reader=self.candle_reader or read_persisted_candle_records,
            candle_window_selector=(
                self.candle_window_selector or select_latest_complete_candle_window
            ),
        )
        result = self.backtest_runner(
            _input_from_payload(payload, fixture_base_path=self.fixture_base_path)
        )
        result = replace(
            result,
            params_json=_result_params_from_payload(payload, base=result.params_json),
        )
        run_id = None
        if self.persistence_engine is not None:
            run_id = await append_backtest_result(self.persistence_engine, result)
        return result_to_response(result, run_id=run_id)

    async def get_backtest(self, run_id: int) -> dict[str, Any] | None:
        if self.persistence_engine is None:
            return None
        async with self.persistence_engine.connect() as connection:
            stored = await get_backtest_run(connection, run_id=run_id)
        if stored is None:
            return None
        return {
            "run_id": stored["id"],
            "created_ts": stored["created_ts"].isoformat(),
            "params": stored["params_json"],
            "stats": stored["stats_json"],
            "trades": [
                {
                    "side": trade["side"],
                    "units": str(trade["units"]),
                    "entry_price": str(trade["entry_price"]),
                    "entry_ts": trade["entry_ts"].isoformat(),
                    "exit_price": str(trade["exit_price"]),
                    "exit_ts": trade["exit_ts"].isoformat(),
                    "pnl": str(trade["pnl"]),
                    "r_multiple": str(trade["r_multiple"]),
                    "exit_reason": trade["exit_reason"],
                }
                for trade in stored["trades"]
            ],
        }


async def read_persisted_candle_records(
    engine: AsyncEngine | None,
    *,
    instrument: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    if engine is None:
        msg = "persisted candle range requests require a persistence engine"
        raise ValueError(msg)
    async with engine.connect() as connection:
        rows = await list_candles_range(
            connection,
            instrument=instrument,
            start=start,
            end=end,
        )
    return [_candle_record(row) for row in rows]


def _candle_record(row: Mapping[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "instrument": row["instrument"],
        "ts": row["ts"].isoformat(),
        "o": str(row["o"]),
        "h": str(row["h"]),
        "low": str(row["l"]),
        "c": str(row["c"]),
        "volume": row["volume"],
        "complete": row["complete"],
    }
    bid = _ohlc_extremes(row.get("bid_h"), row.get("bid_l"))
    ask = _ohlc_extremes(row.get("ask_h"), row.get("ask_l"))
    if bid is not None:
        record["bid"] = bid
    if ask is not None:
        record["ask"] = ask
    return record


def _ohlc_extremes(high: Any, low: Any) -> dict[str, str] | None:
    if high is None or low is None:
        return None
    return {"h": str(high), "l": str(low)}


async def select_latest_complete_candle_window(
    engine: AsyncEngine | None,
    *,
    instrument: str,
    required_days: int,
) -> dict[str, Any] | None:
    if engine is None:
        msg = "persisted candle range requests require a persistence engine"
        raise ValueError(msg)
    async with engine.connect() as connection:
        return await latest_complete_candle_window(
            connection,
            instrument=instrument,
            required_days=required_days,
        )


async def _payload_with_persisted_candles(
    payload: Mapping[str, Any],
    *,
    engine: AsyncEngine | None,
    fixture_base_path: Path | None,
    candle_reader: CandleRangeReader,
    candle_window_selector: BacktestWindowSelector,
) -> dict[str, Any]:
    if "candles" in payload or "fixture" in payload:
        return dict(payload)
    if payload.get("source") != "persisted_candles" and "candle_range" not in payload:
        return dict(payload)

    strategy_config = strategy_config_from_defaults(load_default_config())
    instrument = str(payload.get("instrument") or strategy_config.instrument)
    raw_range = payload.get("candle_range")
    if isinstance(raw_range, Mapping):
        start = _parse_utc_ts(str(raw_range["from"]))
        end = _parse_utc_ts(str(raw_range["to"]))
    else:
        selected_window = await candle_window_selector(
            engine,
            instrument=instrument,
            required_days=_backtest_window_days(payload),
        )
        if selected_window is None:
            msg = (
                f"no complete persisted backtest window is available for {instrument}; "
                "import historical candles before running a backtest"
            )
            raise ValueError(msg)
        start = selected_window["from"]
        end = selected_window["to"]
    candles = await candle_reader(engine, instrument=instrument, start=start, end=end)
    next_payload = dict(payload)
    next_payload["candles"] = candles
    next_payload["candle_range"] = {"from": start.isoformat(), "to": end.isoformat()}
    next_payload.pop("fixture", None)
    return next_payload


def result_to_response(result: BacktestRunResult, *, run_id: int | None = None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": result.status.value,
        "params": result.params_json,
        "stats": result.stats.to_jsonable(),
        "trades": [trade.to_jsonable() for trade in result.trades],
    }


def _input_from_payload(
    payload: Mapping[str, Any],
    *,
    fixture_base_path: Path | None,
) -> BacktestInput:
    strategy_config = strategy_config_from_defaults(load_default_config())
    instrument = str(payload.get("instrument") or strategy_config.instrument)
    strategy_config = _strategy_config_from_payload(payload, instrument=instrument)

    if "candles" in payload:
        raw_candles = payload["candles"]
        if not isinstance(raw_candles, list):
            msg = "candles must be a list"
            raise TypeError(msg)
        candles = candles_from_records(raw_candles, default_instrument=instrument)
    elif "fixture" in payload:
        if fixture_base_path is None:
            msg = "fixture loading is not configured"
            raise ValueError(msg)
        candles = load_candle_fixture(fixture_base_path / str(payload["fixture"]))
    else:
        msg = "backtest request must include candles or fixture"
        raise ValueError(msg)

    backtest_config = _backtest_config_from_payload(payload.get("backtest_config", {}))
    return BacktestInput(
        instrument=instrument,
        candles=candles,
        strategy_config=strategy_config,
        instrument_rules=_instrument_rules_from_payload(
            payload.get("instrument_rules", {}), instrument
        ),
        backtest_config=backtest_config,
    )


def _strategy_config_from_payload(
    payload: Mapping[str, Any],
    *,
    instrument: str,
) -> StrategyConfig:
    strategy_config = replace(
        strategy_config_from_defaults(load_default_config()),
        instrument=instrument,
    )
    raw_params = payload.get("strategy_params", {})
    if not isinstance(raw_params, Mapping):
        msg = "strategy_params must be an object"
        raise TypeError(msg)
    if raw_params:
        strategy_config = apply_params_to_strategy_config(strategy_config, dict(raw_params))
    return strategy_config


def _backtest_config_from_payload(raw: Any) -> BacktestConfig:
    if not isinstance(raw, Mapping):
        msg = "backtest_config must be an object"
        raise TypeError(msg)
    return BacktestConfig(
        initial_nav=raw.get("initial_nav", BacktestConfig.initial_nav),
        spread_pips=raw.get("spread_pips", BacktestConfig.spread_pips),
        slippage_pips=raw.get("slippage_pips", BacktestConfig.slippage_pips),
        commission_per_unit=raw.get("commission_per_unit", BacktestConfig.commission_per_unit),
        ambiguous_fill_policy=raw.get(
            "ambiguous_fill_policy",
            BacktestConfig.ambiguous_fill_policy,
        ),
        force_ny_close=bool(raw.get("force_ny_close", BacktestConfig.force_ny_close)),
    )


def _instrument_rules_from_payload(raw: Any, instrument: str) -> InstrumentRules:
    if not isinstance(raw, Mapping):
        msg = "instrument_rules must be an object"
        raise TypeError(msg)
    defaults = default_instrument_rules(instrument)
    return InstrumentRules(
        instrument=instrument,
        pip_location=int(raw.get("pip_location", defaults.pip_location)),
        display_precision=int(raw.get("display_precision", defaults.display_precision)),
        trade_units_precision=int(raw.get("trade_units_precision", defaults.trade_units_precision)),
        minimum_trade_size=Decimal(str(raw.get("minimum_trade_size", defaults.minimum_trade_size))),
        unit_step=Decimal(str(raw.get("unit_step", defaults.unit_step))),
        quote_home_conversion=Decimal(
            str(raw.get("quote_home_conversion", defaults.quote_home_conversion))
        ),
    )


def _result_params_from_payload(
    payload: Mapping[str, Any],
    *,
    base: Mapping[str, Any],
) -> dict[str, Any]:
    params = dict(base)
    default_source = "inline_candles" if "candles" in payload else "fixture"
    params["source"] = payload.get("source", default_source)
    params["target"] = (
        "paper_variant"
        if payload.get("strategy_params") and payload.get("variant_id") is not None
        else "strategy_params"
        if payload.get("strategy_params")
        else "default_strategy"
    )
    for key in ("instrument", "candle_range", "strategy_params", "variant_id", "variant_label"):
        if key in payload:
            value = payload[key]
            params[key] = dict(value) if isinstance(value, Mapping) else value
    return params


def _backtest_window_days(payload: Mapping[str, Any]) -> int:
    raw = payload.get("candle_window_days", DEFAULT_BACKTEST_WINDOW_DAYS)
    days = int(raw)
    if days <= 0:
        msg = "candle_window_days must be positive"
        raise ValueError(msg)
    return days


def _parse_utc_ts(raw: str) -> datetime:
    value = raw
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None or ts.utcoffset() != _UTC_OFFSET:
        msg = "candle range timestamps must be timezone-aware UTC"
        raise ValueError(msg)
    return ts.astimezone(UTC)
