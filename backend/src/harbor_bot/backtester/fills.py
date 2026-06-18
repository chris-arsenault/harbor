from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from harbor_bot.backtester.models import BacktestConfig, BacktestTrade, FillPolicy
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import InstrumentRules, MarketEntrySetup


@dataclass(frozen=True)
class OpenBacktestPosition:
    setup: MarketEntrySetup
    entry_price: Decimal
    entry_ts: datetime

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
        level=position.stop if reason == "stop_loss" else position.target,
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
    if reason == "take_profit":
        return level - adjustment if side == "long" else level + adjustment
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


def _stop_touched(position: OpenBacktestPosition, candle: ClosedCandle) -> bool:
    if position.side == "long":
        return candle.low <= position.stop
    return candle.h >= position.stop


def _target_touched(position: OpenBacktestPosition, candle: ClosedCandle) -> bool:
    if position.side == "long":
        return candle.h >= position.target
    return candle.low <= position.target
