import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from harbor_bot.feed.candles import ClosedCandle


def load_candle_fixture(path: str | Path) -> tuple[ClosedCandle, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = "candle fixture must be a JSON object"
        raise TypeError(msg)
    records = raw.get("candles")
    if not isinstance(records, list):
        msg = "candle fixture must contain a candles list"
        raise TypeError(msg)
    default_instrument = str(raw.get("instrument", ""))
    return candles_from_records(records, default_instrument=default_instrument)


def candles_from_records(
    records: Iterable[Mapping[str, Any]],
    *,
    default_instrument: str = "",
) -> tuple[ClosedCandle, ...]:
    candles = [
        _candle_from_record(record, default_instrument=default_instrument) for record in records
    ]
    seen: set[tuple[str, datetime]] = set()
    for candle in candles:
        key = (candle.instrument, candle.ts)
        if key in seen:
            msg = f"duplicate candle for {candle.instrument} at {candle.ts.isoformat()}"
            raise ValueError(msg)
        seen.add(key)
    return tuple(sorted(candles, key=lambda candle: candle.ts))


def _candle_from_record(
    record: Mapping[str, Any],
    *,
    default_instrument: str,
) -> ClosedCandle:
    instrument = str(record.get("instrument") or default_instrument)
    if not instrument:
        msg = "candle record must include an instrument"
        raise ValueError(msg)

    if not bool(record.get("complete", False)):
        msg = "recorded backtest fixtures must contain complete candles only"
        raise ValueError(msg)

    midpoint = record.get("mid")
    prices = midpoint if isinstance(midpoint, Mapping) else record
    ts = _parse_utc_ts(str(record.get("ts") or record.get("time")))
    return ClosedCandle(
        instrument=instrument,
        ts=ts,
        o=Decimal(str(prices["o"])),
        h=Decimal(str(prices["h"])),
        low=Decimal(str(prices.get("low", prices.get("l")))),
        c=Decimal(str(prices["c"])),
        volume=int(record.get("volume", 0)),
        complete=True,
        bid_h=_optional_price(record.get("bid"), "h"),
        bid_low=_optional_price(record.get("bid"), "low", "l"),
        bid_c=_optional_price(record.get("bid"), "c"),
        ask_h=_optional_price(record.get("ask"), "h"),
        ask_low=_optional_price(record.get("ask"), "low", "l"),
        ask_c=_optional_price(record.get("ask"), "c"),
    )


def _optional_price(group: Any, *keys: str) -> Decimal | None:
    if not isinstance(group, Mapping):
        return None
    for key in keys:
        if key in group:
            return Decimal(str(group[key]))
    return None


def _parse_utc_ts(raw: str) -> datetime:
    value = raw
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None or ts.utcoffset() is None:
        msg = "recorded candle timestamps must be timezone-aware UTC"
        raise ValueError(msg)
    if ts.utcoffset() != timedelta(0):
        msg = "recorded candle timestamps must be UTC"
        raise ValueError(msg)
    return ts.astimezone(UTC)
