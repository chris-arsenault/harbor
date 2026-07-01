from dataclasses import replace

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    Bias,
    DayState,
    InstrumentRules,
    LevelName,
    SessionLevels,
    StrategyConfig,
    SweepState,
    require_closed_candle,
)

_HIGH_LEVELS = (
    LevelName.ASIA_HIGH,
    LevelName.LONDON_HIGH,
    LevelName.PREV_DAY_HIGH,
)
_LOW_LEVELS = (
    LevelName.ASIA_LOW,
    LevelName.LONDON_LOW,
    LevelName.PREV_DAY_LOW,
)


def detect_sweep(
    candle: ClosedCandle,
    *,
    levels: SessionLevels,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    day_state: DayState,
    candle_index: int,
) -> SweepState | None:
    candle = require_closed_candle(candle)
    buffer = instrument_rules.pips_to_price(config.sweep_buffer_pips)

    swept_highs = [
        (level_name, level_price)
        for level_name in _HIGH_LEVELS
        if not (config.one_trade_per_level and _level_already_actionable(day_state, level_name))
        and (level_price := levels.price_for(level_name)) is not None
        and candle.h > level_price + buffer
        and candle.c < level_price
    ]
    if swept_highs:
        # One candle can clear several stacked levels; the outermost one is the
        # deepest liquidity taken and the economically meaningful sweep.
        level_name, level_price = max(swept_highs, key=lambda item: item[1])
        return SweepState(
            level_name=level_name,
            level_price=level_price,
            bias=Bias.BEARISH,
            sweep_extreme=candle.h,
            swept_ts=candle.ts,
            candle_index=candle_index,
            fvg_deadline_index=candle_index + config.fvg_window,
        )

    swept_lows = [
        (level_name, level_price)
        for level_name in _LOW_LEVELS
        if not (config.one_trade_per_level and _level_already_actionable(day_state, level_name))
        and (level_price := levels.price_for(level_name)) is not None
        and candle.low < level_price - buffer
        and candle.c > level_price
    ]
    if swept_lows:
        level_name, level_price = min(swept_lows, key=lambda item: item[1])
        return SweepState(
            level_name=level_name,
            level_price=level_price,
            bias=Bias.BULLISH,
            sweep_extreme=candle.low,
            swept_ts=candle.ts,
            candle_index=candle_index,
            fvg_deadline_index=candle_index + config.fvg_window,
        )
    return None


def with_active_sweep(day_state: DayState, sweep: SweepState | None) -> DayState:
    return replace(day_state, active_sweep=sweep)


def mark_level_taken(day_state: DayState, level_name: LevelName) -> DayState:
    return replace(
        day_state,
        taken_levels=day_state.taken_levels | frozenset({level_name}),
        swept_levels=day_state.swept_levels | frozenset({level_name}),
        active_sweep=None,
    )


def mark_level_swept(day_state: DayState, level_name: LevelName) -> DayState:
    return replace(
        day_state,
        swept_levels=day_state.swept_levels | frozenset({level_name}),
    )


def _level_already_actionable(day_state: DayState, level_name: LevelName) -> bool:
    return level_name in day_state.taken_levels or level_name in day_state.swept_levels
