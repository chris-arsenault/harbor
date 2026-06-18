from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import Bias, StrategyConfig, SweepState, require_closed_candle
from harbor_bot.strategy.sessions import is_in_ny_trade_window


@dataclass(frozen=True)
class FairValueGap:
    ts: datetime
    instrument: str
    fvg_type: Bias
    top: Decimal
    bottom: Decimal
    midpoint: Decimal
    sweep: SweepState


def detect_fvg(
    candles: list[ClosedCandle],
    *,
    active_sweep: SweepState,
    current_index: int,
    trading_date: date,
    config: StrategyConfig,
) -> FairValueGap | None:
    for candle in candles:
        require_closed_candle(candle)
    if len(candles) < 3:
        return None
    if current_index <= active_sweep.candle_index:
        return None
    if current_index > active_sweep.fvg_deadline_index:
        return None

    current = candles[-1]
    if not is_in_ny_trade_window(current, trading_date=trading_date, config=config):
        return None

    two_back = candles[-3]
    if active_sweep.bias == Bias.BULLISH and current.low > two_back.h:
        bottom = two_back.h
        top = current.low
        return _gap(
            current=current,
            fvg_type=Bias.BULLISH,
            top=top,
            bottom=bottom,
            active_sweep=active_sweep,
        )

    if active_sweep.bias == Bias.BEARISH and current.h < two_back.low:
        top = two_back.low
        bottom = current.h
        return _gap(
            current=current,
            fvg_type=Bias.BEARISH,
            top=top,
            bottom=bottom,
            active_sweep=active_sweep,
        )

    return None


def _gap(
    *,
    current: ClosedCandle,
    fvg_type: Bias,
    top: Decimal,
    bottom: Decimal,
    active_sweep: SweepState,
) -> FairValueGap:
    return FairValueGap(
        ts=current.ts,
        instrument=current.instrument,
        fvg_type=fvg_type,
        top=top,
        bottom=bottom,
        midpoint=(top + bottom) / Decimal("2"),
        sweep=active_sweep,
    )
