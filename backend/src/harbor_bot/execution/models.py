from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

Jsonable = str | int | bool | None | list["Jsonable"] | dict[str, "Jsonable"]


class ExecutionMode(StrEnum):
    PRACTICE = "practice"


class KillSwitchState(StrEnum):
    CLEAR = "clear"
    TRIPPED = "tripped"


@dataclass(frozen=True)
class PracticeExecutionConfig:
    mode: ExecutionMode | str = ExecutionMode.PRACTICE
    trading_enabled_default: bool = False
    max_open_positions: int = 1
    signal_id_namespace: str = "harbor-practice"
    max_daily_loss_pct: Decimal = Decimal("2.0")
    max_spread_pips: Decimal = Decimal("1.5")
    reconciliation_lag_tolerance_seconds: int = 30
    heartbeat_interval_seconds: int = 300
    ny_close_flatten_enabled: bool = True
    ntfy_enabled: bool = False
    telegram_enabled: bool = False
    confirmation_token: str = "OANDA_PRACTICE"

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "mode", ExecutionMode(self.mode))
        except ValueError as exc:
            msg = "M9 execution config supports practice mode only"
            raise ValueError(msg) from exc
        object.__setattr__(self, "max_daily_loss_pct", Decimal(str(self.max_daily_loss_pct)))
        object.__setattr__(self, "max_spread_pips", Decimal(str(self.max_spread_pips)))
        if self.mode is not ExecutionMode.PRACTICE:
            msg = "M9 execution config supports practice mode only"
            raise ValueError(msg)
        if self.trading_enabled_default:
            msg = "practice trading must default to disabled"
            raise ValueError(msg)
        if self.max_open_positions != 1:
            msg = "M9 practice execution supports exactly one open position"
            raise ValueError(msg)
        if not self.signal_id_namespace:
            msg = "signal_id_namespace is required"
            raise ValueError(msg)
        if self.max_daily_loss_pct <= 0:
            msg = "max_daily_loss_pct must be positive"
            raise ValueError(msg)
        if self.max_spread_pips < 0:
            msg = "max_spread_pips cannot be negative"
            raise ValueError(msg)
        if self.reconciliation_lag_tolerance_seconds < 0:
            msg = "reconciliation lag tolerance cannot be negative"
            raise ValueError(msg)
        if self.heartbeat_interval_seconds <= 0:
            msg = "heartbeat interval must be positive"
            raise ValueError(msg)
        if not self.confirmation_token:
            msg = "confirmation_token is required"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "mode": self.mode.value,
            "trading_enabled_default": self.trading_enabled_default,
            "max_open_positions": self.max_open_positions,
            "signal_id_namespace": self.signal_id_namespace,
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_spread_pips": str(self.max_spread_pips),
            "reconciliation_lag_tolerance_seconds": self.reconciliation_lag_tolerance_seconds,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "ny_close_flatten_enabled": self.ny_close_flatten_enabled,
            "ntfy_enabled": self.ntfy_enabled,
            "telegram_enabled": self.telegram_enabled,
            "confirmation_token": self.confirmation_token,
        }


@dataclass(frozen=True)
class TradingControls:
    trading_enabled: bool
    confirmation_token: str
    kill_switch_state: KillSwitchState | str = KillSwitchState.CLEAR
    kill_switch_reason: str | None = None
    updated_ts: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kill_switch_state", KillSwitchState(self.kill_switch_state))
        if self.updated_ts is not None:
            object.__setattr__(self, "updated_ts", _utc(self.updated_ts))

    @classmethod
    def disabled(cls, config: PracticeExecutionConfig) -> "TradingControls":
        return cls(
            trading_enabled=config.trading_enabled_default,
            confirmation_token=config.confirmation_token,
        )

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "confirmation_token": self.confirmation_token,
            "kill_switch_reason": self.kill_switch_reason,
            "kill_switch_state": self.kill_switch_state.value,
            "trading_enabled": self.trading_enabled,
            "updated_ts": _json_datetime(self.updated_ts),
        }


@dataclass(frozen=True)
class ExecutionSignal:
    signal_key: str
    variant_id: int
    instrument: str
    direction: str
    entry_price: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    units: Decimal
    ts: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_price", Decimal(str(self.entry_price)))
        object.__setattr__(self, "stop_loss_price", Decimal(str(self.stop_loss_price)))
        object.__setattr__(self, "take_profit_price", Decimal(str(self.take_profit_price)))
        object.__setattr__(self, "units", Decimal(str(self.units)))
        object.__setattr__(self, "ts", _utc(self.ts))
        if self.variant_id <= 0:
            msg = "variant_id must be positive"
            raise ValueError(msg)
        if self.direction not in {"long", "short"}:
            msg = "execution signal direction must be long or short"
            raise ValueError(msg)
        if not self.signal_key:
            msg = "signal_key is required"
            raise ValueError(msg)
        if self.units <= 0:
            msg = "execution signal units must be positive"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "direction": self.direction,
            "entry_price": str(self.entry_price),
            "instrument": self.instrument,
            "signal_key": self.signal_key,
            "stop_loss_price": str(self.stop_loss_price),
            "take_profit_price": str(self.take_profit_price),
            "ts": self.ts.isoformat(),
            "units": str(self.units),
            "variant_id": self.variant_id,
        }


@dataclass(frozen=True)
class SignalReservation:
    signal_key: str
    reserved: bool
    existing_trade_id: int | None = None

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "existing_trade_id": self.existing_trade_id,
            "reserved": self.reserved,
            "signal_key": self.signal_key,
        }


@dataclass(frozen=True)
class BrokerOrder:
    client_order_id: str
    broker_order_id: str
    broker_trade_id: str | None
    fill_transaction_id: str | None
    instrument: str
    units: Decimal
    price: Decimal | None
    stop_loss_price: Decimal
    take_profit_price: Decimal
    ts: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "units", Decimal(str(self.units)))
        object.__setattr__(
            self,
            "price",
            None if self.price is None else Decimal(str(self.price)),
        )
        object.__setattr__(self, "stop_loss_price", Decimal(str(self.stop_loss_price)))
        object.__setattr__(self, "take_profit_price", Decimal(str(self.take_profit_price)))
        object.__setattr__(self, "ts", _utc(self.ts))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "broker_order_id": self.broker_order_id,
            "broker_trade_id": self.broker_trade_id,
            "client_order_id": self.client_order_id,
            "fill_transaction_id": self.fill_transaction_id,
            "instrument": self.instrument,
            "price": None if self.price is None else str(self.price),
            "stop_loss_price": str(self.stop_loss_price),
            "take_profit_price": str(self.take_profit_price),
            "ts": self.ts.isoformat(),
            "units": str(self.units),
        }


@dataclass(frozen=True)
class BrokerTrade:
    broker_trade_id: str
    instrument: str
    units: Decimal
    entry_price: Decimal
    entry_ts: datetime
    state: str
    realized_pl: Decimal = Decimal("0")
    unrealized_pl: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "units", Decimal(str(self.units)))
        object.__setattr__(self, "entry_price", Decimal(str(self.entry_price)))
        object.__setattr__(self, "entry_ts", _utc(self.entry_ts))
        object.__setattr__(self, "realized_pl", Decimal(str(self.realized_pl)))
        object.__setattr__(self, "unrealized_pl", Decimal(str(self.unrealized_pl)))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "broker_trade_id": self.broker_trade_id,
            "entry_price": str(self.entry_price),
            "entry_ts": self.entry_ts.isoformat(),
            "instrument": self.instrument,
            "realized_pl": str(self.realized_pl),
            "state": self.state,
            "units": str(self.units),
            "unrealized_pl": str(self.unrealized_pl),
        }


@dataclass(frozen=True)
class BrokerPosition:
    instrument: str
    long_units: Decimal
    short_units: Decimal
    unrealized_pl: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "long_units", Decimal(str(self.long_units)))
        object.__setattr__(self, "short_units", Decimal(str(self.short_units)))
        object.__setattr__(self, "unrealized_pl", Decimal(str(self.unrealized_pl)))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "instrument": self.instrument,
            "long_units": str(self.long_units),
            "short_units": str(self.short_units),
            "unrealized_pl": str(self.unrealized_pl),
        }


@dataclass(frozen=True)
class ReconciliationSummary:
    checked_ts: datetime
    transaction_count: int
    bot_open_trade_count: int
    broker_open_trade_count: int
    broker_open_position_count: int
    drift_detected: bool
    checkpoint_transaction_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_ts", _utc(self.checked_ts))
        if self.transaction_count < 0:
            msg = "transaction_count cannot be negative"
            raise ValueError(msg)
        if self.bot_open_trade_count < 0:
            msg = "bot_open_trade_count cannot be negative"
            raise ValueError(msg)
        if self.broker_open_trade_count < 0:
            msg = "broker_open_trade_count cannot be negative"
            raise ValueError(msg)
        if self.broker_open_position_count < 0:
            msg = "broker_open_position_count cannot be negative"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "bot_open_trade_count": self.bot_open_trade_count,
            "broker_open_position_count": self.broker_open_position_count,
            "broker_open_trade_count": self.broker_open_trade_count,
            "checked_ts": self.checked_ts.isoformat(),
            "checkpoint_transaction_id": self.checkpoint_transaction_id,
            "drift_detected": self.drift_detected,
            "transaction_count": self.transaction_count,
        }


@dataclass(frozen=True)
class FlattenResult:
    requested_ts: datetime
    reason: str
    closed_trade_ids: tuple[str, ...]
    closed_position_instruments: tuple[str, ...]
    reconciliation: ReconciliationSummary

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_ts", _utc(self.requested_ts))
        object.__setattr__(
            self,
            "closed_trade_ids",
            tuple(str(trade_id) for trade_id in self.closed_trade_ids),
        )
        object.__setattr__(
            self,
            "closed_position_instruments",
            tuple(str(instrument) for instrument in self.closed_position_instruments),
        )

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "closed_position_instruments": list(self.closed_position_instruments),
            "closed_trade_ids": list(self.closed_trade_ids),
            "reason": self.reason,
            "reconciliation": self.reconciliation.to_jsonable(),
            "requested_ts": self.requested_ts.isoformat(),
        }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "execution datetimes must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _json_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _utc(value).isoformat()
