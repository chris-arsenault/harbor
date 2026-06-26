from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from harbor_bot.feed.candles import ClosedCandle


class LevelName(StrEnum):
    ASIA_HIGH = "asia_high"
    ASIA_LOW = "asia_low"
    LONDON_HIGH = "london_high"
    LONDON_LOW = "london_low"
    PREV_DAY_HIGH = "prev_day_high"
    PREV_DAY_LOW = "prev_day_low"


class Bias(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass(frozen=True)
class StrategyConfig:
    instrument: str
    timezone: str
    sessions: dict[str, dict[str, str]]
    fvg_window: int
    sweep_buffer_pips: Decimal
    risk_per_trade_pct: Decimal
    max_daily_loss_pct: Decimal
    target_mode: str
    rr_floor: Decimal
    liquidity_rr_floor: Decimal
    one_trade_per_level: bool
    max_trades_per_day: int
    max_spread_pips: Decimal
    swing_lookback: int
    max_units: Decimal
    require_mss: bool = False
    require_volume_spike: bool = False
    swing_pivot_width: int = 2
    exit_mode: str = "bracket"
    time_stop_minutes: int = 120
    atr_trail_mult: Decimal = Decimal("1.5")
    partial_fraction: Decimal = Decimal("0.5")
    partial_at_r: Decimal = Decimal("1.0")


@dataclass(frozen=True)
class InstrumentRules:
    instrument: str
    pip_location: int
    display_precision: int
    trade_units_precision: int
    minimum_trade_size: Decimal
    unit_step: Decimal
    quote_home_conversion: Decimal = Decimal("1")

    @property
    def pip_size(self) -> Decimal:
        return Decimal("1").scaleb(self.pip_location)

    def pips_to_price(self, pips: Decimal) -> Decimal:
        return pips * self.pip_size


@dataclass(frozen=True)
class SessionLevels:
    trading_date: date
    instrument: str
    asia_high: Decimal
    asia_low: Decimal
    london_high: Decimal
    london_low: Decimal
    prev_day_high: Decimal | None = None
    prev_day_low: Decimal | None = None

    def price_for(self, level_name: LevelName) -> Decimal | None:
        return {
            LevelName.ASIA_HIGH: self.asia_high,
            LevelName.ASIA_LOW: self.asia_low,
            LevelName.LONDON_HIGH: self.london_high,
            LevelName.LONDON_LOW: self.london_low,
            LevelName.PREV_DAY_HIGH: self.prev_day_high,
            LevelName.PREV_DAY_LOW: self.prev_day_low,
        }[level_name]

    def opposite_levels(self, bias: Bias) -> dict[LevelName, Decimal]:
        if bias == Bias.BULLISH:
            return {
                LevelName.ASIA_HIGH: self.asia_high,
                LevelName.LONDON_HIGH: self.london_high,
            }
        return {
            LevelName.ASIA_LOW: self.asia_low,
            LevelName.LONDON_LOW: self.london_low,
        }


@dataclass(frozen=True)
class SweepState:
    level_name: LevelName
    level_price: Decimal
    bias: Bias
    sweep_extreme: Decimal
    swept_ts: datetime
    candle_index: int
    fvg_deadline_index: int


@dataclass(frozen=True)
class DayState:
    trading_date: date
    taken_levels: frozenset[LevelName] = frozenset()
    swept_levels: frozenset[LevelName] = frozenset()
    trades_taken: int = 0
    has_open_position: bool = False
    trading_disabled: bool = False
    active_sweep: SweepState | None = None


@dataclass(frozen=True)
class MarketEntrySetup:
    ts: datetime
    instrument: str
    side: str
    level_name: LevelName
    entry_reference: Decimal
    stop: Decimal
    target: Decimal
    risk: Decimal
    units: Decimal


@dataclass(frozen=True)
class FlattenDecision:
    ts: datetime
    reason: str


@dataclass(frozen=True)
class StrategyDecision:
    kind: str
    ts: datetime
    payload: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def __init__(self, *, kind: str, ts: datetime, payload: dict[str, Any] | None = None) -> None:
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "ts", ts)
        object.__setattr__(self, "payload", MappingProxyType(dict(payload or {})))


def strategy_config_from_defaults(defaults: dict[str, dict[str, Any]]) -> StrategyConfig:
    return StrategyConfig(
        instrument=str(_value(defaults, "instrument")),
        timezone=str(_value(defaults, "timezone")),
        sessions=_sessions_value(_value(defaults, "sessions")),
        fvg_window=int(_value(defaults, "fvg_window")),
        sweep_buffer_pips=_decimal_value(defaults, "sweep_buffer_pips"),
        risk_per_trade_pct=_decimal_value(defaults, "risk_per_trade_pct"),
        max_daily_loss_pct=_decimal_value(defaults, "max_daily_loss_pct"),
        target_mode=str(_value(defaults, "target_mode")),
        rr_floor=_decimal_value(defaults, "rr_floor"),
        liquidity_rr_floor=_decimal_value(defaults, "liquidity_rr_floor"),
        one_trade_per_level=bool(_value(defaults, "one_trade_per_level")),
        max_trades_per_day=int(_value(defaults, "max_trades_per_day")),
        max_spread_pips=_decimal_value(defaults, "max_spread_pips"),
        swing_lookback=int(_value(defaults, "swing_lookback")),
        max_units=_decimal_value(defaults, "max_units"),
        require_mss=bool(_value(defaults, "require_mss")),
        require_volume_spike=bool(_value(defaults, "require_volume_spike")),
        swing_pivot_width=int(_value(defaults, "swing_pivot_width")),
        exit_mode=str(_value(defaults, "exit_mode")),
        time_stop_minutes=int(_value(defaults, "time_stop_minutes")),
        atr_trail_mult=_decimal_value(defaults, "atr_trail_mult"),
        partial_fraction=_decimal_value(defaults, "partial_fraction"),
        partial_at_r=_decimal_value(defaults, "partial_at_r"),
    )


def require_closed_candle(candle: ClosedCandle) -> ClosedCandle:
    if not candle.complete:
        msg = "strategy core accepts closed candles only"
        raise ValueError(msg)
    return candle


def _value(defaults: dict[str, dict[str, Any]], key: str) -> Any:
    return defaults[key]["value"]


def _decimal_value(defaults: dict[str, dict[str, Any]], key: str) -> Decimal:
    return Decimal(str(_value(defaults, key)))


def _sessions_value(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        msg = "sessions config must be a mapping"
        raise TypeError(msg)
    return {
        str(name): {"start": str(window["start"]), "end": str(window["end"])}
        for name, window in raw.items()
    }
