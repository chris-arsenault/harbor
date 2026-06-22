from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ObservabilityModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def to_jsonable(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class StatusSnapshot(ObservabilityModel):
    bot_state: str
    session_phase: str
    connection_health: str
    mode: str
    trading_enabled: bool
    trading_controls_available: bool
    kill_switch_state: str
    day_pnl: Decimal
    trades_today: int
    max_trades_per_day: int
    account_nav: Decimal | None
    open_positions: int | None
    unrealized_pnl: Decimal | None
    last_heartbeat: datetime | None
    promoted_variant: dict[str, Any] | None = None
    reconciliation_state: dict[str, Any] | None = None
    open_position: dict[str, Any] | None = None
    notifier_state: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None


class SessionLevelSnapshot(ObservabilityModel):
    date: date
    instrument: str
    asia_high: Decimal
    asia_low: Decimal
    london_high: Decimal
    london_low: Decimal
    prev_day_high: Decimal | None = None
    prev_day_low: Decimal | None = None
    swept_levels: tuple[str, ...] = Field(default_factory=tuple)
    taken_levels: tuple[str, ...] = Field(default_factory=tuple)


class CandlePoint(ObservabilityModel):
    instrument: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    complete: bool


class ChartMarker(ObservabilityModel):
    kind: str
    ts: datetime
    instrument: str
    label: str
    price: Decimal
    direction: str | None = None
    level_name: str | None = None


class FvgBox(ObservabilityModel):
    id: int
    ts: datetime
    instrument: str
    type: str
    top: Decimal
    bottom: Decimal
    midpoint: Decimal
    sweep_id: int


class SignalMarker(ObservabilityModel):
    id: int
    ts: datetime
    instrument: str
    direction: str
    entry: Decimal
    stop: Decimal
    target: Decimal
    status: str


class TradeMarker(ObservabilityModel):
    id: int
    signal_id: int
    side: str
    units: Decimal
    entry_price: Decimal
    entry_ts: datetime
    exit_price: Decimal | None
    exit_ts: datetime | None
    pnl: Decimal | None
    r_multiple: Decimal | None
    exit_reason: str | None


class EventLogItem(ObservabilityModel):
    id: int
    ts: datetime
    level: str
    module: str
    type: str
    message: str
    data: dict[str, Any]


class DashboardSnapshot(ObservabilityModel):
    status: StatusSnapshot
    levels: SessionLevelSnapshot | None
    candles: tuple[CandlePoint, ...] = Field(default_factory=tuple)
    markers: tuple[ChartMarker, ...] = Field(default_factory=tuple)
    fvgs: tuple[FvgBox, ...] = Field(default_factory=tuple)
    signals: tuple[SignalMarker, ...] = Field(default_factory=tuple)
    trades: tuple[TradeMarker, ...] = Field(default_factory=tuple)
    events: tuple[EventLogItem, ...] = Field(default_factory=tuple)


class WebSocketEnvelope(ObservabilityModel):
    type: str
    sent_at: datetime
    payload: dict[str, Any]
