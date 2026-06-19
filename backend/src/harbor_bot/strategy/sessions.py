from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import SessionLevels, StrategyConfig, require_closed_candle


@dataclass(frozen=True)
class SessionWindow:
    start: datetime
    end: datetime

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts.astimezone(UTC) < self.end


@dataclass(frozen=True)
class TradingSessionWindows:
    asia: SessionWindow
    london: SessionWindow
    ny_trade: SessionWindow


def session_windows_for_date(trading_date: date, config: StrategyConfig) -> TradingSessionWindows:
    zone = ZoneInfo(config.timezone)
    return TradingSessionWindows(
        asia=_window_for(
            trading_date=trading_date,
            zone=zone,
            start_name="asia",
            end_name="asia",
            config=config,
            starts_previous_day=True,
        ),
        london=_window_for(
            trading_date=trading_date,
            zone=zone,
            start_name="london",
            end_name="london",
            config=config,
        ),
        ny_trade=_window_for(
            trading_date=trading_date,
            zone=zone,
            start_name="ny_trade",
            end_name="ny_trade",
            config=config,
        ),
    )


def is_in_ny_trade_window(
    candle: ClosedCandle,
    *,
    trading_date: date,
    config: StrategyConfig,
) -> bool:
    candle = require_closed_candle(candle)
    return session_windows_for_date(trading_date, config).ny_trade.contains(candle.ts)


def trading_date_for_candle(candle: ClosedCandle, config: StrategyConfig) -> date:
    candle = require_closed_candle(candle)
    zone = ZoneInfo(config.timezone)
    local_ts = candle.ts.astimezone(zone)
    asia_start = _parse_time(config.sessions["asia"]["start"])
    if local_ts.timetz().replace(tzinfo=None) >= asia_start:
        return local_ts.date() + timedelta(days=1)
    return local_ts.date()


def compute_session_levels(
    candles: list[ClosedCandle],
    *,
    trading_date: date,
    instrument: str,
    config: StrategyConfig,
) -> SessionLevels:
    for candle in candles:
        require_closed_candle(candle)

    windows = session_windows_for_date(trading_date, config)
    asia = _candles_in_window(candles, windows.asia)
    london = _candles_in_window(candles, windows.london)
    if not asia:
        msg = "cannot compute Asia levels without closed session candles"
        raise ValueError(msg)
    if not london:
        msg = "cannot compute London levels without closed session candles"
        raise ValueError(msg)

    return SessionLevels(
        trading_date=trading_date,
        instrument=instrument,
        asia_high=max(candle.h for candle in asia),
        asia_low=min(candle.low for candle in asia),
        london_high=max(candle.h for candle in london),
        london_low=min(candle.low for candle in london),
    )


def _candles_in_window(candles: list[ClosedCandle], window: SessionWindow) -> list[ClosedCandle]:
    return [candle for candle in candles if window.contains(candle.ts)]


def _window_for(
    *,
    trading_date: date,
    zone: ZoneInfo,
    start_name: str,
    end_name: str,
    config: StrategyConfig,
    starts_previous_day: bool = False,
) -> SessionWindow:
    start_date = trading_date - timedelta(days=1) if starts_previous_day else trading_date
    start = _local_datetime(start_date, _parse_time(config.sessions[start_name]["start"]), zone)
    end = _local_datetime(trading_date, _parse_time(config.sessions[end_name]["end"]), zone)
    if end <= start:
        end = end + timedelta(days=1)
    return SessionWindow(start=start.astimezone(UTC), end=end.astimezone(UTC))


def _parse_time(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(hour=int(hour), minute=int(minute))


def _local_datetime(value_date: date, value_time: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(value_date, value_time, tzinfo=zone)
