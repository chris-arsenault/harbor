from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    InstrumentRules,
    MarketEntrySetup,
    StrategyConfig,
    StrategyDecision,
)


class FillPolicy(StrEnum):
    PESSIMISTIC = "pessimistic"
    OPTIMISTIC = "optimistic"


class BacktestStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class BacktestConfig:
    initial_nav: Decimal = Decimal("10000")
    spread_pips: Decimal = Decimal("0.8")
    slippage_pips: Decimal = Decimal("0.1")
    commission_per_unit: Decimal = Decimal("0")
    ambiguous_fill_policy: FillPolicy = FillPolicy.PESSIMISTIC
    force_ny_close: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_nav", Decimal(str(self.initial_nav)))
        object.__setattr__(self, "spread_pips", Decimal(str(self.spread_pips)))
        object.__setattr__(self, "slippage_pips", Decimal(str(self.slippage_pips)))
        object.__setattr__(self, "commission_per_unit", Decimal(str(self.commission_per_unit)))
        object.__setattr__(self, "ambiguous_fill_policy", FillPolicy(self.ambiguous_fill_policy))

        if self.initial_nav <= 0:
            msg = "initial_nav must be positive"
            raise ValueError(msg)
        if self.spread_pips < 0:
            msg = "spread_pips cannot be negative"
            raise ValueError(msg)
        if self.slippage_pips < 0:
            msg = "slippage_pips cannot be negative"
            raise ValueError(msg)
        if self.commission_per_unit < 0:
            msg = "commission_per_unit cannot be negative"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, str | bool]:
        return {
            "initial_nav": str(self.initial_nav),
            "spread_pips": str(self.spread_pips),
            "slippage_pips": str(self.slippage_pips),
            "commission_per_unit": str(self.commission_per_unit),
            "ambiguous_fill_policy": self.ambiguous_fill_policy.value,
            "force_ny_close": self.force_ny_close,
        }


@dataclass(frozen=True)
class BacktestInput:
    instrument: str
    candles: tuple[ClosedCandle, ...]
    strategy_config: StrategyConfig
    instrument_rules: InstrumentRules
    backtest_config: BacktestConfig = field(default_factory=BacktestConfig)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candles", tuple(self.candles))
        if self.instrument != self.strategy_config.instrument:
            msg = "backtest instrument must match strategy config"
            raise ValueError(msg)
        if self.instrument != self.instrument_rules.instrument:
            msg = "backtest instrument must match instrument rules"
            raise ValueError(msg)
        for candle in self.candles:
            if candle.instrument != self.instrument:
                msg = "all backtest candles must match the requested instrument"
                raise ValueError(msg)


@dataclass(frozen=True)
class BacktestTrade:
    instrument: str
    side: str
    units: Decimal
    entry_price: Decimal
    entry_ts: datetime
    stop: Decimal
    target: Decimal
    exit_price: Decimal
    exit_ts: datetime
    pnl: Decimal
    r_multiple: Decimal
    exit_reason: str
    source_signal_ts: datetime | None = None
    level_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "units", Decimal(str(self.units)))
        object.__setattr__(self, "entry_price", Decimal(str(self.entry_price)))
        object.__setattr__(self, "stop", Decimal(str(self.stop)))
        object.__setattr__(self, "target", Decimal(str(self.target)))
        object.__setattr__(self, "exit_price", Decimal(str(self.exit_price)))
        object.__setattr__(self, "pnl", Decimal(str(self.pnl)))
        object.__setattr__(self, "r_multiple", Decimal(str(self.r_multiple)))
        if self.side not in {"long", "short"}:
            msg = "backtest trade side must be long or short"
            raise ValueError(msg)
        if self.units <= 0:
            msg = "backtest trade units must be positive"
            raise ValueError(msg)

    @classmethod
    def from_entry_setup(
        cls,
        setup: MarketEntrySetup,
        *,
        entry_price: Decimal,
        entry_ts: datetime,
        exit_price: Decimal,
        exit_ts: datetime,
        pnl: Decimal,
        r_multiple: Decimal,
        exit_reason: str,
    ) -> "BacktestTrade":
        return cls(
            instrument=setup.instrument,
            side=setup.side,
            units=setup.units,
            entry_price=entry_price,
            entry_ts=entry_ts,
            stop=setup.stop,
            target=setup.target,
            exit_price=exit_price,
            exit_ts=exit_ts,
            pnl=pnl,
            r_multiple=r_multiple,
            exit_reason=exit_reason,
            source_signal_ts=setup.ts,
            level_name=setup.level_name.value,
        )

    def to_persistence_row(self) -> dict[str, Decimal | datetime | str]:
        return {
            "side": self.side,
            "units": self.units,
            "entry_price": self.entry_price,
            "entry_ts": self.entry_ts,
            "exit_price": self.exit_price,
            "exit_ts": self.exit_ts,
            "pnl": self.pnl,
            "r_multiple": self.r_multiple,
            "exit_reason": self.exit_reason,
        }

    def to_jsonable(self) -> dict[str, str]:
        return {
            "instrument": self.instrument,
            "side": self.side,
            "units": str(self.units),
            "entry_price": str(self.entry_price),
            "entry_ts": self.entry_ts.isoformat(),
            "stop": str(self.stop),
            "target": str(self.target),
            "exit_price": str(self.exit_price),
            "exit_ts": self.exit_ts.isoformat(),
            "pnl": str(self.pnl),
            "r_multiple": str(self.r_multiple),
            "exit_reason": self.exit_reason,
            "source_signal_ts": self.source_signal_ts.isoformat()
            if self.source_signal_ts is not None
            else "",
            "level_name": self.level_name or "",
        }


@dataclass(frozen=True)
class EquityPoint:
    ts: datetime
    nav: Decimal
    drawdown: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "nav", Decimal(str(self.nav)))
        object.__setattr__(self, "drawdown", Decimal(str(self.drawdown)))

    def to_jsonable(self) -> dict[str, str]:
        return {
            "ts": self.ts.isoformat(),
            "nav": str(self.nav),
            "drawdown": str(self.drawdown),
        }


@dataclass(frozen=True)
class BacktestStats:
    trade_count: int
    win_rate: Decimal
    net_pnl: Decimal
    expectancy: Decimal
    average_r: Decimal
    max_drawdown: Decimal
    ending_nav: Decimal
    lookahead_sanity_passed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "win_rate", Decimal(str(self.win_rate)))
        object.__setattr__(self, "net_pnl", Decimal(str(self.net_pnl)))
        object.__setattr__(self, "expectancy", Decimal(str(self.expectancy)))
        object.__setattr__(self, "average_r", Decimal(str(self.average_r)))
        object.__setattr__(self, "max_drawdown", Decimal(str(self.max_drawdown)))
        object.__setattr__(self, "ending_nav", Decimal(str(self.ending_nav)))

    @classmethod
    def empty(cls, *, initial_nav: Decimal) -> "BacktestStats":
        return cls(
            trade_count=0,
            win_rate=Decimal("0"),
            net_pnl=Decimal("0"),
            expectancy=Decimal("0"),
            average_r=Decimal("0"),
            max_drawdown=Decimal("0"),
            ending_nav=initial_nav,
            lookahead_sanity_passed=True,
        )

    def to_jsonable(self) -> dict[str, int | str | bool]:
        return {
            "trade_count": self.trade_count,
            "win_rate": str(self.win_rate),
            "net_pnl": str(self.net_pnl),
            "expectancy": str(self.expectancy),
            "average_r": str(self.average_r),
            "max_drawdown": str(self.max_drawdown),
            "ending_nav": str(self.ending_nav),
            "lookahead_sanity_passed": self.lookahead_sanity_passed,
        }


@dataclass(frozen=True)
class BacktestRunResult:
    status: BacktestStatus
    stats: BacktestStats
    trades: tuple[BacktestTrade, ...] = ()
    equity_curve: tuple[EquityPoint, ...] = ()
    run_id: int | None = None
    error: str | None = None
    params_json: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", BacktestStatus(self.status))
        object.__setattr__(self, "trades", tuple(self.trades))
        object.__setattr__(self, "equity_curve", tuple(self.equity_curve))


def entry_setup_from_decision(decision: StrategyDecision) -> MarketEntrySetup:
    if decision.kind != "market_entry":
        msg = "strategy decision is not a market entry"
        raise ValueError(msg)
    setup = decision.payload.get("setup")
    if not isinstance(setup, MarketEntrySetup):
        msg = "market entry decision payload must contain a MarketEntrySetup"
        raise TypeError(msg)
    return setup


def candle_to_record(candle: ClosedCandle) -> dict[str, str | int | bool]:
    return {
        "instrument": candle.instrument,
        "ts": candle.ts.isoformat(),
        "o": str(candle.o),
        "h": str(candle.h),
        "low": str(candle.low),
        "c": str(candle.c),
        "volume": candle.volume,
        "complete": candle.complete,
    }
