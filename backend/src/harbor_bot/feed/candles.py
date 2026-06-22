from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from harbor_bot.oanda.types import PriceFrame, PricingFrame


@dataclass(frozen=True)
class ClosedCandle:
    instrument: str
    ts: datetime
    o: Decimal
    h: Decimal
    low: Decimal
    c: Decimal
    volume: int
    complete: bool = True
    # Optional bid/ask extremes for honest fill detection (ADR 0006). When absent,
    # the backtester falls back to midpoint OHLC. Longs exit on the bid, shorts on the ask.
    bid_h: Decimal | None = None
    bid_low: Decimal | None = None
    ask_h: Decimal | None = None
    ask_low: Decimal | None = None


@dataclass
class _OpenCandle:
    instrument: str
    ts: datetime
    o: Decimal
    h: Decimal
    low: Decimal
    c: Decimal
    volume: int

    @classmethod
    def start(cls, *, frame: PriceFrame, midpoint: Decimal) -> "_OpenCandle":
        return cls(
            instrument=frame.instrument,
            ts=_minute_start(frame.time),
            o=midpoint,
            h=midpoint,
            low=midpoint,
            c=midpoint,
            volume=1,
        )

    def update(self, midpoint: Decimal) -> None:
        self.h = max(self.h, midpoint)
        self.low = min(self.low, midpoint)
        self.c = midpoint
        self.volume += 1

    def close(self) -> ClosedCandle:
        return ClosedCandle(
            instrument=self.instrument,
            ts=self.ts,
            o=self.o,
            h=self.h,
            low=self.low,
            c=self.c,
            volume=self.volume,
        )


class CandleBuilder:
    def __init__(self) -> None:
        self._active: dict[str, _OpenCandle] = {}

    def add(self, frame: PricingFrame) -> ClosedCandle | None:
        if not isinstance(frame, PriceFrame):
            return None

        midpoint = _midpoint(frame)
        minute = _minute_start(frame.time)
        active = self._active.get(frame.instrument)
        if active is None:
            self._active[frame.instrument] = _OpenCandle.start(frame=frame, midpoint=midpoint)
            return None

        if minute == active.ts:
            active.update(midpoint)
            return None

        if minute < active.ts:
            return None

        closed = active.close()
        self._active[frame.instrument] = _OpenCandle.start(frame=frame, midpoint=midpoint)
        return closed


def _midpoint(frame: PriceFrame) -> Decimal:
    if not frame.bids or not frame.asks:
        msg = "pricing frames must include at least one bid and one ask"
        raise ValueError(msg)
    return (frame.bids[0].price + frame.asks[0].price) / Decimal("2")


def _minute_start(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)
