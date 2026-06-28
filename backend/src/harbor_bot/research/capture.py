"""Cost-aware fixed-horizon event capture research (pure)."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.edge import EdgeEvent, get_edge_algorithm
from harbor_bot.strategy.models import Bias, InstrumentRules, StrategyConfig, require_closed_candle


@dataclass(frozen=True)
class CaptureStats:
    count: int
    hit_rate: Decimal
    mean_gross_pips: Decimal
    mean_net_pips: Decimal
    median_net_pips: Decimal
    total_net_pips: Decimal
    average_mfe_pips: Decimal
    average_mae_pips: Decimal

    def to_jsonable(self) -> dict[str, int | str]:
        return {
            "count": self.count,
            "hit_rate": str(self.hit_rate),
            "mean_gross_pips": str(self.mean_gross_pips),
            "mean_net_pips": str(self.mean_net_pips),
            "median_net_pips": str(self.median_net_pips),
            "total_net_pips": str(self.total_net_pips),
            "average_mfe_pips": str(self.average_mfe_pips),
            "average_mae_pips": str(self.average_mae_pips),
        }


@dataclass(frozen=True)
class CaptureRow:
    algorithm_id: str
    hypothesis_id: str
    algorithm_label: str
    instrument: str
    horizon: int
    event_count: int
    stats: CaptureStats
    spread_pips: Decimal
    slippage_pips: Decimal
    entry_model: str = "next_open"
    exit_model: str = "fixed_horizon_close"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "algorithm_id": self.algorithm_id,
            "hypothesis_id": self.hypothesis_id,
            "algorithm_label": self.algorithm_label,
            "instrument": self.instrument,
            "horizon": self.horizon,
            "event_count": self.event_count,
            "stats": self.stats.to_jsonable(),
            "spread_pips": str(self.spread_pips),
            "slippage_pips": str(self.slippage_pips),
            "entry_model": self.entry_model,
            "exit_model": self.exit_model,
        }


@dataclass(frozen=True)
class _CaptureTrade:
    gross_pips: Decimal
    net_pips: Decimal
    mfe_pips: Decimal
    mae_pips: Decimal


def run_capture_scan(
    candles: list[ClosedCandle],
    *,
    instrument: str,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    algorithm_ids: tuple[str, ...],
    horizons: tuple[int, ...],
    spread_pips: Decimal = Decimal("0.8"),
    slippage_pips: Decimal = Decimal("0.1"),
) -> list[CaptureRow]:
    _validate_horizons(horizons)
    ordered = tuple(
        sorted((require_closed_candle(candle) for candle in candles), key=lambda item: item.ts)
    )
    rows: list[CaptureRow] = []
    for algorithm_id in algorithm_ids:
        algorithm = get_edge_algorithm(algorithm_id)
        events = algorithm.event_builder(
            ordered,
            instrument=instrument,
            config=config,
            instrument_rules=instrument_rules,
            atr_window=14,
        )
        for horizon in horizons:
            trades = _capture_trades(
                ordered,
                events=events,
                horizon=horizon,
                rules=instrument_rules,
                spread_pips=spread_pips,
                slippage_pips=slippage_pips,
            )
            rows.append(
                CaptureRow(
                    algorithm_id=algorithm.algorithm_id,
                    hypothesis_id=algorithm.hypothesis_id,
                    algorithm_label=algorithm.label,
                    instrument=instrument,
                    horizon=horizon,
                    event_count=len(events),
                    stats=_capture_stats(trades),
                    spread_pips=spread_pips,
                    slippage_pips=slippage_pips,
                )
            )
    return rows


def _capture_trades(
    candles: tuple[ClosedCandle, ...],
    *,
    events: list[EdgeEvent],
    horizon: int,
    rules: InstrumentRules,
    spread_pips: Decimal,
    slippage_pips: Decimal,
) -> list[_CaptureTrade]:
    trades: list[_CaptureTrade] = []
    cost = rules.pips_to_price((spread_pips / Decimal("2")) + slippage_pips)
    by_ts = {candle.ts: index for index, candle in enumerate(candles)}
    for event in events:
        event_ts = candles[event.index].ts
        entry_index = by_ts.get(event_ts + timedelta(minutes=1))
        exit_index = by_ts.get(event_ts + timedelta(minutes=horizon))
        if entry_index is None or exit_index is None or exit_index < entry_index:
            continue
        entry_mid = candles[entry_index].o
        exit_mid = candles[exit_index].c
        side = "long" if event.bias == Bias.BULLISH else "short"
        entry = entry_mid + cost if side == "long" else entry_mid - cost
        exit_price = exit_mid - cost if side == "long" else exit_mid + cost
        gross = _pips(side, entry_mid, exit_mid, rules)
        net = _pips(side, entry, exit_price, rules)
        mfe, mae = _excursions(side, entry, candles[entry_index : exit_index + 1], rules)
        trades.append(_CaptureTrade(gross_pips=gross, net_pips=net, mfe_pips=mfe, mae_pips=mae))
    return trades


def _pips(side: str, entry: Decimal, exit_price: Decimal, rules: InstrumentRules) -> Decimal:
    move = exit_price - entry if side == "long" else entry - exit_price
    return move / rules.pip_size


def _excursions(
    side: str,
    entry_price: Decimal,
    window: tuple[ClosedCandle, ...],
    rules: InstrumentRules,
) -> tuple[Decimal, Decimal]:
    if not window:
        return Decimal("0"), Decimal("0")
    if side == "long":
        mfe = max(_bid_high(candle) - entry_price for candle in window) / rules.pip_size
        mae = max(entry_price - _bid_low(candle) for candle in window) / rules.pip_size
    else:
        mfe = max(entry_price - _ask_low(candle) for candle in window) / rules.pip_size
        mae = max(_ask_high(candle) - entry_price for candle in window) / rules.pip_size
    return max(mfe, Decimal("0")), max(mae, Decimal("0"))


def _bid_high(candle: ClosedCandle) -> Decimal:
    return candle.bid_h if candle.bid_h is not None else candle.h


def _bid_low(candle: ClosedCandle) -> Decimal:
    return candle.bid_low if candle.bid_low is not None else candle.low


def _ask_high(candle: ClosedCandle) -> Decimal:
    return candle.ask_h if candle.ask_h is not None else candle.h


def _ask_low(candle: ClosedCandle) -> Decimal:
    return candle.ask_low if candle.ask_low is not None else candle.low


def _validate_horizons(horizons: tuple[int, ...]) -> None:
    if not horizons or any(horizon <= 0 for horizon in horizons):
        msg = "horizons must be positive"
        raise ValueError(msg)


def _capture_stats(trades: list[_CaptureTrade]) -> CaptureStats:
    if not trades:
        return CaptureStats(
            count=0,
            hit_rate=Decimal("0"),
            mean_gross_pips=Decimal("0"),
            mean_net_pips=Decimal("0"),
            median_net_pips=Decimal("0"),
            total_net_pips=Decimal("0"),
            average_mfe_pips=Decimal("0"),
            average_mae_pips=Decimal("0"),
        )
    count = len(trades)
    gross = [trade.gross_pips for trade in trades]
    net = [trade.net_pips for trade in trades]
    mfe = [trade.mfe_pips for trade in trades]
    mae = [trade.mae_pips for trade in trades]
    return CaptureStats(
        count=count,
        hit_rate=Decimal(sum(1 for value in net if value > 0)) / Decimal(count),
        mean_gross_pips=sum(gross, Decimal("0")) / Decimal(count),
        mean_net_pips=sum(net, Decimal("0")) / Decimal(count),
        median_net_pips=_median(net),
        total_net_pips=sum(net, Decimal("0")),
        average_mfe_pips=sum(mfe, Decimal("0")) / Decimal(count),
        average_mae_pips=sum(mae, Decimal("0")) / Decimal(count),
    )


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        return Decimal("0")
    mid = size // 2
    if size % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")
