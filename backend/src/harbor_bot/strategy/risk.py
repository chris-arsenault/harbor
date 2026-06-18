from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    DayState,
    FlattenDecision,
    LevelName,
    StrategyConfig,
    require_closed_candle,
)
from harbor_bot.strategy.sessions import session_windows_for_date


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str | None = None


ALLOW = GateResult(allowed=True)


def check_spread(spread_pips: Decimal, config: StrategyConfig) -> GateResult:
    if spread_pips > config.max_spread_pips:
        return GateResult(allowed=False, reason="spread")
    return ALLOW


def check_daily_loss(
    *,
    day_start_nav: Decimal,
    current_nav: Decimal,
    config: StrategyConfig,
) -> GateResult:
    if day_start_nav <= 0:
        return ALLOW
    loss_pct = ((day_start_nav - current_nav) / day_start_nav) * Decimal("100")
    if loss_pct >= config.max_daily_loss_pct:
        return GateResult(allowed=False, reason="daily_loss")
    return ALLOW


def check_trade_count(day_state: DayState, config: StrategyConfig) -> GateResult:
    if day_state.trades_taken >= config.max_trades_per_day:
        return GateResult(allowed=False, reason="max_trades_per_day")
    return ALLOW


def check_one_position(day_state: DayState) -> GateResult:
    if day_state.has_open_position:
        return GateResult(allowed=False, reason="one_position")
    return ALLOW


def check_one_trade_per_level(
    day_state: DayState,
    level_name: LevelName,
    config: StrategyConfig,
) -> GateResult:
    if config.one_trade_per_level and level_name in day_state.taken_levels:
        return GateResult(allowed=False, reason="one_trade_per_level")
    return ALLOW


def ny_close_flatten_decision(
    candle: ClosedCandle,
    *,
    trading_date: date,
    config: StrategyConfig,
    has_open_position: bool,
) -> FlattenDecision | None:
    candle = require_closed_candle(candle)
    if not has_open_position:
        return None
    ny_window = session_windows_for_date(trading_date, config).ny_trade
    if candle.ts >= ny_window.end:
        return FlattenDecision(ts=candle.ts, reason="ny_close")
    return None


def daily_loss_flatten_decision(
    *,
    ts: datetime,
    day_start_nav: Decimal,
    current_nav: Decimal,
    config: StrategyConfig,
) -> FlattenDecision | None:
    result = check_daily_loss(
        day_start_nav=day_start_nav,
        current_nav=current_nav,
        config=config,
    )
    if result.allowed:
        return None
    return FlattenDecision(ts=ts, reason="daily_loss")
