from dataclasses import dataclass
from datetime import UTC, date, timedelta

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.models import WalkForwardConfig


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_candles: tuple[ClosedCandle, ...]
    oos_candles: tuple[ClosedCandle, ...]

    @property
    def train_dates(self) -> tuple[date, ...]:
        return _dates_for(self.train_candles)

    @property
    def oos_dates(self) -> tuple[date, ...]:
        return _dates_for(self.oos_candles)


def build_walk_forward_windows(
    candles: tuple[ClosedCandle, ...] | list[ClosedCandle],
    config: WalkForwardConfig,
) -> tuple[WalkForwardWindow, ...]:
    ordered = tuple(candles)
    _validate_candles(ordered)

    by_date: dict[date, list[ClosedCandle]] = {}
    for candle in ordered:
        by_date.setdefault(candle.ts.date(), []).append(candle)

    dates = sorted(by_date)
    windows: list[WalkForwardWindow] = []
    start_index = 0
    while True:
        train_start = dates[start_index] if start_index < len(dates) else None
        if train_start is None:
            break
        train_end = train_start + timedelta(days=config.train_window_days)
        oos_end = train_end + timedelta(days=config.oos_window_days)
        train_dates = [value for value in dates if train_start <= value < train_end]
        oos_dates = [value for value in dates if train_end <= value < oos_end]
        if len(train_dates) < config.train_window_days or len(oos_dates) < config.oos_window_days:
            break
        windows.append(
            WalkForwardWindow(
                index=len(windows),
                train_candles=tuple(candle for value in train_dates for candle in by_date[value]),
                oos_candles=tuple(candle for value in oos_dates for candle in by_date[value]),
            )
        )
        next_start = train_start + timedelta(days=config.step_days)
        try:
            start_index = dates.index(next_start)
        except ValueError:
            break

    if not windows:
        msg = "dataset is too small for configured walk-forward windows"
        raise ValueError(msg)
    return tuple(windows)


def _validate_candles(candles: tuple[ClosedCandle, ...]) -> None:
    if not candles:
        msg = "walk-forward candles cannot be empty"
        raise ValueError(msg)
    instruments = {candle.instrument for candle in candles}
    if len(instruments) != 1:
        msg = "walk-forward candles must contain exactly one instrument"
        raise ValueError(msg)
    previous = None
    for candle in candles:
        if not candle.complete:
            msg = "walk-forward candles must be complete closed candles"
            raise ValueError(msg)
        if candle.ts.tzinfo is None or candle.ts.utcoffset() != timedelta(0):
            msg = "walk-forward candle timestamps must be timezone-aware UTC"
            raise ValueError(msg)
        if previous is not None and candle.ts < previous:
            msg = "walk-forward candles must be sorted by timestamp"
            raise ValueError(msg)
        previous = candle.ts.astimezone(UTC)


def _dates_for(candles: tuple[ClosedCandle, ...]) -> tuple[date, ...]:
    return tuple(dict.fromkeys(candle.ts.date() for candle in candles))
