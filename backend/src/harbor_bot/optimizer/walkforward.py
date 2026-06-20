from dataclasses import dataclass
from datetime import UTC, date, timedelta

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.models import WalkForwardConfig
from harbor_bot.strategy.models import StrategyConfig
from harbor_bot.strategy.sessions import (
    compute_session_levels,
    session_windows_for_date,
    trading_date_for_candle,
)


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


@dataclass(frozen=True)
class StrategyDayStatus:
    trading_date: date
    candle_count: int
    evaluable: bool
    reason: str | None = None


def build_walk_forward_windows(
    candles: tuple[ClosedCandle, ...] | list[ClosedCandle],
    config: WalkForwardConfig,
    *,
    strategy_config: StrategyConfig | None = None,
) -> tuple[WalkForwardWindow, ...]:
    ordered = tuple(candles)
    _validate_candles(ordered)

    if strategy_config is not None:
        return _build_strategy_date_windows(ordered, config, strategy_config)

    return _build_utc_date_windows(ordered, config)


def _build_utc_date_windows(
    ordered: tuple[ClosedCandle, ...],
    config: WalkForwardConfig,
) -> tuple[WalkForwardWindow, ...]:
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


def _build_strategy_date_windows(
    ordered: tuple[ClosedCandle, ...],
    config: WalkForwardConfig,
    strategy_config: StrategyConfig,
) -> tuple[WalkForwardWindow, ...]:
    by_date = _strategy_day_groups(ordered, strategy_config)
    day_statuses = _strategy_day_statuses(
        by_date, strategy_config, instrument=ordered[0].instrument
    )
    by_complete_date = {
        status.trading_date: by_date[status.trading_date]
        for status in day_statuses
        if status.evaluable
    }
    dates = sorted(by_complete_date)
    required_dates = config.train_window_days + config.oos_window_days
    windows: list[WalkForwardWindow] = []
    start_index = 0
    while start_index + required_dates <= len(dates):
        train_dates = dates[start_index : start_index + config.train_window_days]
        oos_start_index = start_index + config.train_window_days
        oos_dates = dates[oos_start_index : oos_start_index + config.oos_window_days]
        windows.append(
            WalkForwardWindow(
                index=len(windows),
                train_candles=tuple(
                    candle for value in train_dates for candle in by_complete_date[value]
                ),
                oos_candles=tuple(
                    candle for value in oos_dates for candle in by_complete_date[value]
                ),
            )
        )
        start_index += config.step_days

    if not windows:
        msg = "dataset is too small for configured walk-forward windows"
        raise ValueError(msg)
    return tuple(windows)


def summarize_strategy_days(
    candles: tuple[ClosedCandle, ...] | list[ClosedCandle],
    strategy_config: StrategyConfig,
) -> tuple[StrategyDayStatus, ...]:
    ordered = tuple(candles)
    _validate_candles(ordered)
    return _strategy_day_statuses(
        _strategy_day_groups(ordered, strategy_config),
        strategy_config,
        instrument=ordered[0].instrument,
    )


def _strategy_day_groups(
    ordered: tuple[ClosedCandle, ...],
    strategy_config: StrategyConfig,
) -> dict[date, list[ClosedCandle]]:
    by_date: dict[date, list[ClosedCandle]] = {}
    for candle in ordered:
        trading_date = trading_date_for_candle(candle, strategy_config)
        by_date.setdefault(trading_date, []).append(candle)
    return by_date


def _strategy_day_statuses(
    by_date: dict[date, list[ClosedCandle]],
    strategy_config: StrategyConfig,
    *,
    instrument: str,
) -> tuple[StrategyDayStatus, ...]:
    return tuple(
        _strategy_day_status(
            trading_date,
            by_date[trading_date],
            strategy_config=strategy_config,
            instrument=instrument,
        )
        for trading_date in sorted(by_date)
    )


def _strategy_day_status(
    trading_date: date,
    day_candles: list[ClosedCandle],
    *,
    strategy_config: StrategyConfig,
    instrument: str,
) -> StrategyDayStatus:
    windows = session_windows_for_date(trading_date, strategy_config)
    if max(candle.ts for candle in day_candles) < windows.ny_trade.end:
        return StrategyDayStatus(
            trading_date=trading_date,
            candle_count=len(day_candles),
            evaluable=False,
            reason="day ends before the NY trade window closes",
        )
    if not any(windows.ny_trade.contains(candle.ts) for candle in day_candles):
        return StrategyDayStatus(
            trading_date=trading_date,
            candle_count=len(day_candles),
            evaluable=False,
            reason="no candles inside the NY trade window",
        )
    try:
        compute_session_levels(
            list(day_candles),
            trading_date=trading_date,
            instrument=instrument,
            config=strategy_config,
        )
    except ValueError as exc:
        return StrategyDayStatus(
            trading_date=trading_date,
            candle_count=len(day_candles),
            evaluable=False,
            reason=str(exc),
        )
    return StrategyDayStatus(
        trading_date=trading_date,
        candle_count=len(day_candles),
        evaluable=True,
    )


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
