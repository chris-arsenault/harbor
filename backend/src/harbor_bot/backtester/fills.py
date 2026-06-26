from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from harbor_bot.backtester.models import BacktestConfig, BacktestTrade, FillPolicy
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import InstrumentRules, MarketEntrySetup, StrategyConfig

ATR_WINDOW = 14


@dataclass(frozen=True)
class OpenBacktestPosition:
    setup: MarketEntrySetup
    entry_price: Decimal
    entry_ts: datetime
    trailing_stop: Decimal | None = None
    extreme: Decimal | None = None
    partial_realized: Decimal | None = None
    remaining_units: Decimal | None = None

    @property
    def side(self) -> str:
        return self.setup.side

    @property
    def units(self) -> Decimal:
        return self.setup.units

    @property
    def stop(self) -> Decimal:
        return self.setup.stop

    @property
    def effective_stop(self) -> Decimal:
        return self.trailing_stop if self.trailing_stop is not None else self.setup.stop

    @property
    def target(self) -> Decimal:
        return self.setup.target


def simulate_market_entry(
    setup: MarketEntrySetup,
    *,
    entry_candle: ClosedCandle,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> OpenBacktestPosition:
    return OpenBacktestPosition(
        setup=setup,
        entry_price=market_entry_price(
            side=setup.side,
            midpoint_open=entry_candle.o,
            config=config,
            instrument_rules=instrument_rules,
        ),
        entry_ts=entry_candle.ts,
    )


def market_entry_price(
    *,
    side: str,
    midpoint_open: Decimal,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> Decimal:
    adjustment = instrument_rules.pips_to_price(
        (config.spread_pips / Decimal("2")) + config.slippage_pips
    )
    if side == "long":
        return midpoint_open + adjustment
    if side == "short":
        return midpoint_open - adjustment
    msg = "market entry side must be long or short"
    raise ValueError(msg)


def simulate_bracket_exit(
    position: OpenBacktestPosition,
    *,
    candle: ClosedCandle,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> BacktestTrade | None:
    stop_touched = _stop_touched(position, candle)
    target_touched = _target_touched(position, candle)
    if not stop_touched and not target_touched:
        return None

    reason = _exit_reason(
        stop_touched=stop_touched,
        target_touched=target_touched,
        config=config,
    )
    exit_price = _bracket_exit_price(
        side=position.side,
        level=position.effective_stop if reason == "stop_loss" else position.target,
        reason=reason,
        config=config,
        instrument_rules=instrument_rules,
    )
    return _closed_trade(
        position,
        exit_price=exit_price,
        exit_ts=candle.ts,
        exit_reason=reason,
        config=config,
    )


def simulate_exit(
    position: OpenBacktestPosition,
    *,
    candle: ClosedCandle,
    strategy_config: StrategyConfig,
    backtest_config: BacktestConfig,
    instrument_rules: InstrumentRules,
    recent_candles: list[ClosedCandle],
) -> tuple[OpenBacktestPosition, BacktestTrade | None]:
    """Resolve the exit for the configured mode, returning the (possibly
    trail-advanced) position so the engine carries trailing state forward.

    ``bracket`` is the unchanged stop/target path; ``atr_trail`` ratchets a
    trailing stop before the bracket check; ``time_stop`` force-closes after a
    fixed duration when no bracket level was hit; ``partial_runner`` scales out
    at 1R and runs the remainder from breakeven (ADR 0007).
    """
    if strategy_config.exit_mode == "partial_runner":
        return _partial_runner_exit(
            position,
            candle=candle,
            strategy_config=strategy_config,
            config=backtest_config,
            instrument_rules=instrument_rules,
        )
    if strategy_config.exit_mode == "atr_trail":
        position = _advance_trailing(
            position,
            recent_candles=recent_candles,
            mult=strategy_config.atr_trail_mult,
            instrument_rules=instrument_rules,
        )
    trade = simulate_bracket_exit(
        position, candle=candle, config=backtest_config, instrument_rules=instrument_rules
    )
    if trade is None and strategy_config.exit_mode == "time_stop":
        trade = _time_exit(
            position,
            candle=candle,
            config=backtest_config,
            minutes=strategy_config.time_stop_minutes,
            instrument_rules=instrument_rules,
        )
    return position, trade


def _partial_runner_exit(
    position: OpenBacktestPosition,
    *,
    candle: ClosedCandle,
    strategy_config: StrategyConfig,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> tuple[OpenBacktestPosition, BacktestTrade | None]:
    """Scale out a fraction at +partial_at_r, run the rest from breakeven.

    One signal stays one trade: the partial leg's realised P&L is banked on the
    position and combined with the runner's P&L at close, so trade_count and
    win-rate are not distorted by the scale-out.
    """
    setup = position.setup
    risk = abs(position.entry_price - setup.stop)
    one_r = _partial_target(
        position.side, position.entry_price, risk, strategy_config, setup.target
    )

    if position.partial_realized is None:
        if _stop_touched(position, candle):
            return position, _runner_close(
                position,
                candle=candle,
                level=setup.stop,
                reason="stop_loss",
                units=setup.units,
                banked=Decimal("0"),
                config=config,
                instrument_rules=instrument_rules,
            )
        if not _one_r_touched(position.side, candle, one_r):
            return position, None
        position = _bank_partial(
            position,
            one_r=one_r,
            fraction=strategy_config.partial_fraction,
            config=config,
            rules=instrument_rules,
        )

    if _stop_touched(position, candle):
        return position, _runner_close(
            position,
            candle=candle,
            level=position.entry_price,
            reason="runner_breakeven",
            units=_remaining(position),
            banked=position.partial_realized or Decimal("0"),
            config=config,
            instrument_rules=instrument_rules,
        )
    if _target_touched(position, candle):
        return position, _runner_close(
            position,
            candle=candle,
            level=setup.target,
            reason="runner_target",
            units=_remaining(position),
            banked=position.partial_realized or Decimal("0"),
            config=config,
            instrument_rules=instrument_rules,
        )
    return position, None


def _partial_target(
    side: str, entry: Decimal, risk: Decimal, strategy_config: StrategyConfig, target: Decimal
) -> Decimal:
    distance = strategy_config.partial_at_r * risk
    if side == "long":
        return min(entry + distance, target)
    return max(entry - distance, target)


def _bank_partial(
    position: OpenBacktestPosition,
    *,
    one_r: Decimal,
    fraction: Decimal,
    config: BacktestConfig,
    rules: InstrumentRules,
) -> OpenBacktestPosition:
    partial_units = position.setup.units * fraction
    exit_price = _slip_adjust(one_r, position.side, config, rules)
    banked = _leg_pnl(position.side, partial_units, position.entry_price, exit_price)
    return replace(
        position,
        partial_realized=banked,
        remaining_units=position.setup.units - partial_units,
        trailing_stop=position.entry_price,
    )


def _runner_close(
    position: OpenBacktestPosition,
    *,
    candle: ClosedCandle,
    level: Decimal,
    reason: str,
    units: Decimal,
    banked: Decimal,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> BacktestTrade:
    exit_price = _slip_adjust(level, position.side, config, instrument_rules)
    leg = _leg_pnl(position.side, units, position.entry_price, exit_price)
    commission = position.setup.units * config.commission_per_unit * Decimal("2")
    total = banked + leg - commission
    risk_amount = abs(position.entry_price - position.setup.stop) * position.setup.units
    r_multiple = total / risk_amount if risk_amount else Decimal("0")
    return BacktestTrade.from_entry_setup(
        position.setup,
        entry_price=position.entry_price,
        entry_ts=position.entry_ts,
        exit_price=exit_price,
        exit_ts=candle.ts,
        pnl=total,
        r_multiple=r_multiple,
        exit_reason=reason,
    )


def _remaining(position: OpenBacktestPosition) -> Decimal:
    return (
        position.remaining_units if position.remaining_units is not None else position.setup.units
    )


def _one_r_touched(side: str, candle: ClosedCandle, one_r: Decimal) -> bool:
    if side == "long":
        return _exit_high(candle, "long") >= one_r
    return _exit_low(candle, "short") <= one_r


def _slip_adjust(
    level: Decimal, side: str, config: BacktestConfig, instrument_rules: InstrumentRules
) -> Decimal:
    adjustment = instrument_rules.pips_to_price(config.slippage_pips)
    return level - adjustment if side == "long" else level + adjustment


def _leg_pnl(side: str, units: Decimal, entry_price: Decimal, exit_price: Decimal) -> Decimal:
    if side == "long":
        return (exit_price - entry_price) * units
    return (entry_price - exit_price) * units


def _advance_trailing(
    position: OpenBacktestPosition,
    *,
    recent_candles: list[ClosedCandle],
    mult: Decimal,
    instrument_rules: InstrumentRules,
) -> OpenBacktestPosition:
    atr = _average_true_range(recent_candles)
    if atr <= 0 or mult <= 0:
        return position
    distance = atr * mult
    candle = recent_candles[-1]
    if position.side == "long":
        extreme = candle.h if position.extreme is None else max(position.extreme, candle.h)
        candidate = max(extreme - distance, position.setup.stop)
        trail = (
            candidate if position.trailing_stop is None else max(position.trailing_stop, candidate)
        )
        return replace(position, extreme=extreme, trailing_stop=trail)
    extreme = candle.low if position.extreme is None else min(position.extreme, candle.low)
    candidate = min(extreme + distance, position.setup.stop)
    trail = candidate if position.trailing_stop is None else min(position.trailing_stop, candidate)
    return replace(position, extreme=extreme, trailing_stop=trail)


def _time_exit(
    position: OpenBacktestPosition,
    *,
    candle: ClosedCandle,
    config: BacktestConfig,
    minutes: int,
    instrument_rules: InstrumentRules,
) -> BacktestTrade | None:
    if minutes <= 0 or candle.ts - position.entry_ts < timedelta(minutes=minutes):
        return None
    adjustment = instrument_rules.pips_to_price(config.slippage_pips)
    exit_price = candle.c - adjustment if position.side == "long" else candle.c + adjustment
    return _closed_trade(
        position,
        exit_price=exit_price,
        exit_ts=candle.ts,
        exit_reason="time_stop",
        config=config,
    )


def _average_true_range(candles: list[ClosedCandle]) -> Decimal:
    window = candles[-ATR_WINDOW:]
    if len(window) < 2:
        return Decimal("0")
    ranges = [
        max(
            current.h - current.low,
            abs(current.h - previous.c),
            abs(current.low - previous.c),
        )
        for previous, current in zip(window, window[1:], strict=False)
    ]
    return sum(ranges, Decimal("0")) / Decimal(len(ranges))


def force_close_position(
    position: OpenBacktestPosition,
    *,
    candle: ClosedCandle,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> BacktestTrade:
    adjustment = instrument_rules.pips_to_price(config.slippage_pips)
    exit_price = candle.c - adjustment if position.side == "long" else candle.c + adjustment
    return _closed_trade(
        position,
        exit_price=exit_price,
        exit_ts=candle.ts,
        exit_reason="ny_close",
        config=config,
    )


def _exit_reason(
    *,
    stop_touched: bool,
    target_touched: bool,
    config: BacktestConfig,
) -> str:
    if stop_touched and target_touched:
        return (
            "take_profit" if config.ambiguous_fill_policy == FillPolicy.OPTIMISTIC else "stop_loss"
        )
    if stop_touched:
        return "stop_loss"
    return "take_profit"


def _bracket_exit_price(
    *,
    side: str,
    level: Decimal,
    reason: str,
    config: BacktestConfig,
    instrument_rules: InstrumentRules,
) -> Decimal:
    adjustment = instrument_rules.pips_to_price(config.slippage_pips)
    return level - adjustment if side == "long" else level + adjustment


def _closed_trade(
    position: OpenBacktestPosition,
    *,
    exit_price: Decimal,
    exit_ts: datetime,
    exit_reason: str,
    config: BacktestConfig,
) -> BacktestTrade:
    gross_pnl = _pnl(
        side=position.side,
        units=position.units,
        entry_price=position.entry_price,
        exit_price=exit_price,
    )
    pnl = gross_pnl - (position.units * config.commission_per_unit * Decimal("2"))
    risk_amount = abs(position.entry_price - position.stop) * position.units
    r_multiple = pnl / risk_amount if risk_amount else Decimal("0")
    return BacktestTrade.from_entry_setup(
        position.setup,
        entry_price=position.entry_price,
        entry_ts=position.entry_ts,
        exit_price=exit_price,
        exit_ts=exit_ts,
        pnl=pnl,
        r_multiple=r_multiple,
        exit_reason=exit_reason,
    )


def _pnl(
    *,
    side: str,
    units: Decimal,
    entry_price: Decimal,
    exit_price: Decimal,
) -> Decimal:
    if side == "long":
        return (exit_price - entry_price) * units
    return (entry_price - exit_price) * units


def _exit_low(candle: ClosedCandle, side: str) -> Decimal:
    """Low the position is filled against on the downside (ADR 0006).

    A long exits by selling at the bid; a short exits by buying at the ask.
    Falls back to the midpoint low when bid/ask extremes are absent.
    """
    if side == "long":
        return candle.bid_low if candle.bid_low is not None else candle.low
    return candle.ask_low if candle.ask_low is not None else candle.low


def _exit_high(candle: ClosedCandle, side: str) -> Decimal:
    if side == "long":
        return candle.bid_h if candle.bid_h is not None else candle.h
    return candle.ask_h if candle.ask_h is not None else candle.h


def _stop_touched(position: OpenBacktestPosition, candle: ClosedCandle) -> bool:
    if position.side == "long":
        return _exit_low(candle, "long") <= position.effective_stop
    return _exit_high(candle, "short") >= position.effective_stop


def _target_touched(position: OpenBacktestPosition, candle: ClosedCandle) -> bool:
    if position.side == "long":
        return _exit_high(candle, "long") >= position.target
    return _exit_low(candle, "short") <= position.target
