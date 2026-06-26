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
    bid_c: Decimal | None = None
    ask_h: Decimal | None = None
    ask_low: Decimal | None = None
    ask_c: Decimal | None = None


@dataclass
class _OpenCandle:
    instrument: str
    ts: datetime
    o: Decimal
    h: Decimal
    low: Decimal
    c: Decimal
    bid_h: Decimal
    bid_low: Decimal
    bid_c: Decimal
    ask_h: Decimal
    ask_low: Decimal
    ask_c: Decimal
    volume: int

    @classmethod
    def start(
        cls,
        *,
        frame: PriceFrame,
        midpoint: Decimal,
        bid: Decimal,
        ask: Decimal,
    ) -> "_OpenCandle":
        return cls(
            instrument=frame.instrument,
            ts=_minute_start(frame.time),
            o=midpoint,
            h=midpoint,
            low=midpoint,
            c=midpoint,
            bid_h=bid,
            bid_low=bid,
            bid_c=bid,
            ask_h=ask,
            ask_low=ask,
            ask_c=ask,
            volume=1,
        )

    def update(self, midpoint: Decimal, *, bid: Decimal, ask: Decimal) -> None:
        self.h = max(self.h, midpoint)
        self.low = min(self.low, midpoint)
        self.c = midpoint
        self.bid_h = max(self.bid_h, bid)
        self.bid_low = min(self.bid_low, bid)
        self.bid_c = bid
        self.ask_h = max(self.ask_h, ask)
        self.ask_low = min(self.ask_low, ask)
        self.ask_c = ask
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
            bid_h=self.bid_h,
            bid_low=self.bid_low,
            bid_c=self.bid_c,
            ask_h=self.ask_h,
            ask_low=self.ask_low,
            ask_c=self.ask_c,
        )


class CandleBuilder:
    def __init__(self) -> None:
        self._active: dict[str, _OpenCandle] = {}

    def add(self, frame: PricingFrame) -> ClosedCandle | None:
        if not isinstance(frame, PriceFrame):
            return None

        bid, ask = _bid_ask(frame)
        midpoint = (bid + ask) / Decimal("2")
        minute = _minute_start(frame.time)
        active = self._active.get(frame.instrument)
        if active is None:
            self._active[frame.instrument] = _OpenCandle.start(
                frame=frame,
                midpoint=midpoint,
                bid=bid,
                ask=ask,
            )
            return None

        if minute == active.ts:
            active.update(midpoint, bid=bid, ask=ask)
            return None

        if minute < active.ts:
            return None

        closed = active.close()
        self._active[frame.instrument] = _OpenCandle.start(
            frame=frame,
            midpoint=midpoint,
            bid=bid,
            ask=ask,
        )
        return closed


def _bid_ask(frame: PriceFrame) -> tuple[Decimal, Decimal]:
    if not frame.bids or not frame.asks:
        msg = "pricing frames must include at least one bid and one ask"
        raise ValueError(msg)
    return frame.bids[0].price, frame.asks[0].price


def _minute_start(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)
