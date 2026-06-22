"""Market-structure-shift (MSS / break-of-structure) confirmation (pure).

After a sweep, require price to break the most-recent pre-sweep swing in the
reversal direction before an entry is allowed (ADR 0007). A bullish bias (low
sweep) needs a close above the prior swing high; a bearish bias (high sweep)
needs a close below the prior swing low. This filters sweeps that simply keep
running. Opt-in via ``StrategyConfig.require_mss``; decisions stay closed-candle.
"""

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import Bias, StrategyConfig, SweepState


def mss_confirmed(
    candle_history: list[ClosedCandle],
    *,
    sweep: SweepState,
    current_index: int,
    config: StrategyConfig,
) -> bool:
    sweep_index = sweep.candle_index
    window_start = max(0, sweep_index - config.swing_lookback + 1)
    pre_swing = candle_history[window_start : sweep_index + 1]
    after_sweep = candle_history[sweep_index + 1 : current_index + 1]
    if not pre_swing or not after_sweep:
        return False
    if sweep.bias == Bias.BULLISH:
        swing_high = max(candle.h for candle in pre_swing)
        return any(candle.c > swing_high for candle in after_sweep)
    swing_low = min(candle.low for candle in pre_swing)
    return any(candle.c < swing_low for candle in after_sweep)


def volume_spike(
    candle_history: list[ClosedCandle],
    *,
    current_index: int,
    config: StrategyConfig,
) -> bool:
    """Displacement filter: the sweep candle traded on above-average tick volume.

    True when the current candle's volume exceeds the mean volume of the prior
    ``swing_lookback`` candles. With no prior baseline this is False, so an
    enabled filter conservatively rejects early-window sweeps.
    """
    window_start = max(0, current_index - config.swing_lookback)
    prior = candle_history[window_start:current_index]
    if not prior:
        return False
    average = sum(candle.volume for candle in prior) / len(prior)
    return candle_history[current_index].volume > average
