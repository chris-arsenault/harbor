from decimal import Decimal

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.fvgs import FairValueGap
from harbor_bot.strategy.models import (
    Bias,
    InstrumentRules,
    MarketEntrySetup,
    SessionLevels,
    StrategyConfig,
    require_closed_candle,
)


def build_market_entry_setup(
    *,
    fvg: FairValueGap,
    entry_price: Decimal,
    nav: Decimal,
    levels: SessionLevels,
    recent_candles: list[ClosedCandle],
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> MarketEntrySetup | None:
    stop = calculate_stop(
        fvg=fvg,
        recent_candles=recent_candles,
        config=config,
        instrument_rules=instrument_rules,
    )
    risk = abs(entry_price - stop)
    if risk <= 0:
        return None

    target = choose_target(
        fvg=fvg,
        entry_price=entry_price,
        risk=risk,
        levels=levels,
        config=config,
    )
    if target is None:
        return None

    units = calculate_position_units(
        nav=nav,
        risk=risk,
        config=config,
        instrument_rules=instrument_rules,
    )
    return MarketEntrySetup(
        ts=fvg.ts,
        instrument=fvg.instrument,
        side=_side(fvg.fvg_type),
        level_name=fvg.sweep.level_name,
        entry_reference=entry_price,
        stop=stop,
        target=target,
        risk=risk,
        units=units,
    )


def calculate_stop(
    *,
    fvg: FairValueGap,
    recent_candles: list[ClosedCandle],
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> Decimal:
    for candle in recent_candles:
        require_closed_candle(candle)

    buffer = instrument_rules.pips_to_price(config.sweep_buffer_pips)
    swing_window = recent_candles[-config.swing_lookback :]
    if fvg.fvg_type == Bias.BULLISH:
        swing_extreme = min(
            (candle.low for candle in swing_window),
            default=fvg.sweep.sweep_extreme,
        )
        return min(fvg.sweep.sweep_extreme, swing_extreme) - buffer

    swing_extreme = max((candle.h for candle in swing_window), default=fvg.sweep.sweep_extreme)
    return max(fvg.sweep.sweep_extreme, swing_extreme) + buffer


def choose_target(
    *,
    fvg: FairValueGap,
    entry_price: Decimal,
    risk: Decimal,
    levels: SessionLevels,
    config: StrategyConfig,
) -> Decimal | None:
    rr_target = (
        entry_price + (risk * config.rr_floor)
        if fvg.fvg_type == Bias.BULLISH
        else entry_price - (risk * config.rr_floor)
    )
    if config.target_mode == "rr":
        return rr_target

    all_liquidity_targets = _opposite_liquidity_targets(
        bias=fvg.fvg_type,
        entry_price=entry_price,
        levels=levels,
    )
    if config.target_mode == "opposite_session":
        return _nearest_qualified_liquidity_target(
            all_liquidity_targets,
            entry_price=entry_price,
            risk=risk,
            config=config,
        )

    if config.target_mode != "rr_or_liquidity":
        msg = f"unsupported target_mode {config.target_mode!r}"
        raise ValueError(msg)

    nearest_liquidity = _nearest_liquidity_target(
        all_liquidity_targets,
        entry_price=entry_price,
    )
    if nearest_liquidity is None:
        return rr_target
    if _achieved_rr(nearest_liquidity, entry_price=entry_price, risk=risk) < (
        config.liquidity_rr_floor
    ):
        return None
    return min(
        (rr_target, nearest_liquidity),
        key=lambda value: abs(value - entry_price),
    )


def calculate_position_units(
    *,
    nav: Decimal,
    risk: Decimal,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
) -> Decimal:
    risk_amount = nav * (config.risk_per_trade_pct / Decimal("100"))
    raw_units = risk_amount / (risk * instrument_rules.quote_home_conversion)
    stepped = _floor_to_step(raw_units, instrument_rules.unit_step)
    above_minimum = max(stepped, instrument_rules.minimum_trade_size)
    return min(above_minimum, config.max_units)


def _opposite_liquidity_targets(
    *,
    bias: Bias,
    entry_price: Decimal,
    levels: SessionLevels,
) -> list[Decimal]:
    values = list(levels.opposite_levels(bias).values())
    if bias == Bias.BULLISH:
        return [value for value in values if value > entry_price]
    return [value for value in values if value < entry_price]


def _nearest_qualified_liquidity_target(
    targets: list[Decimal],
    *,
    entry_price: Decimal,
    risk: Decimal,
    config: StrategyConfig,
) -> Decimal | None:
    for target in sorted(targets, key=lambda value: abs(value - entry_price)):
        if _achieved_rr(target, entry_price=entry_price, risk=risk) >= config.liquidity_rr_floor:
            return target
    return None


def _nearest_liquidity_target(
    targets: list[Decimal],
    *,
    entry_price: Decimal,
) -> Decimal | None:
    if not targets:
        return None
    return min(targets, key=lambda value: abs(value - entry_price))


def _achieved_rr(target: Decimal, *, entry_price: Decimal, risk: Decimal) -> Decimal:
    return abs(target - entry_price) / risk


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value // step) * step


def _side(bias: Bias) -> str:
    return "long" if bias == Bias.BULLISH else "short"
