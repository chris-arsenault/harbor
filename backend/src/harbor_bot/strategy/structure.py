"""Market-structure-shift (MSS / break-of-structure) confirmation (pure).

After a sweep, require price to break the most-recent pre-sweep **swing pivot**
in the reversal direction before an entry is allowed (ADR 0007). A swing pivot is
a fractal: a high (or low) strictly greater (or lower) than ``swing_pivot_width``
candles on each side — not merely the extreme of a lookback window. A bullish
bias (low sweep) needs a close above the prior swing high; a bearish bias needs
a close below the prior swing low. Opt-in via ``StrategyConfig.require_mss``;
decisions stay closed-candle.
"""

from decimal import Decimal

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import Bias, StrategyConfig, SweepState


def mss_confirmed(
    candle_history: list[ClosedCandle],
    *,
    sweep: SweepState,
    current_index: int,
    config: StrategyConfig,
) -> bool:
    width = config.swing_pivot_width
    after_sweep = candle_history[sweep.candle_index + 1 : current_index + 1]
    if not after_sweep:
        return False
    if sweep.bias == Bias.BULLISH:
        pivot = recent_swing(
            candle_history, before_index=sweep.candle_index, width=width, high=True
        )
        return pivot is not None and any(candle.c > pivot for candle in after_sweep)
    pivot = recent_swing(candle_history, before_index=sweep.candle_index, width=width, high=False)
    return pivot is not None and any(candle.c < pivot for candle in after_sweep)


def recent_swing(
    candles: list[ClosedCandle], *, before_index: int, width: int, high: bool
) -> Decimal | None:
    """Most recent confirmed fractal swing high/low at or before ``before_index``.

    A pivot at index ``i`` is only confirmed once ``width`` candles exist on each
    side, so candidates run from ``before_index - width`` down to ``width``.
    """
    for index in range(before_index - width, width - 1, -1):
        if _is_pivot(candles, index, width, high=high):
            return candles[index].h if high else candles[index].low
    return None


def _is_pivot(candles: list[ClosedCandle], index: int, width: int, *, high: bool) -> bool:
    if index - width < 0 or index + width >= len(candles):
        return False
    pivot = candles[index].h if high else candles[index].low
    for offset in range(1, width + 1):
        left = candles[index - offset]
        right = candles[index + offset]
        if high and (left.h >= pivot or right.h >= pivot):
            return False
        if not high and (left.low <= pivot or right.low <= pivot):
            return False
    return True


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
