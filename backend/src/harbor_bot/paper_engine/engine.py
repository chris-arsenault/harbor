from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from harbor_bot.backtester.fills import (
    OpenBacktestPosition,
    force_close_position,
    simulate_bracket_exit,
    simulate_market_entry,
)
from harbor_bot.backtester.models import BacktestTrade, entry_setup_from_decision
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.config import apply_params_to_strategy_config
from harbor_bot.paper_engine.models import PaperEngineConfig, PaperVariant, VariantTrade
from harbor_bot.strategy.core import RiskContext, StrategyResult, evaluate_closed_candle
from harbor_bot.strategy.models import (
    DayState,
    InstrumentRules,
    MarketEntrySetup,
    SessionLevels,
    StrategyConfig,
)
from harbor_bot.strategy.sessions import compute_session_levels, session_windows_for_date

StrategyEvaluator = Callable[..., StrategyResult]


class ShadowPaperEngine:
    def __init__(
        self,
        *,
        variants: Iterable[PaperVariant],
        base_strategy_config: StrategyConfig,
        instrument_rules: InstrumentRules,
        paper_config: PaperEngineConfig,
        strategy_evaluator: StrategyEvaluator = evaluate_closed_candle,
    ) -> None:
        if base_strategy_config.instrument != instrument_rules.instrument:
            msg = "paper engine strategy config and instrument rules must match"
            raise ValueError(msg)
        self._base_strategy_config = base_strategy_config
        self._instrument_rules = instrument_rules
        self._paper_config = paper_config
        self._fill_config = paper_config.to_backtest_config()
        self._strategy_evaluator = strategy_evaluator
        self._states = {
            variant.id: _VariantRuntime(
                variant=variant,
                strategy_config=apply_params_to_strategy_config(
                    base_strategy_config,
                    dict(variant.params),
                ),
                nav=paper_config.initial_nav,
                day_start_nav=paper_config.initial_nav,
            )
            for variant in variants
            if variant.status == "paper"
        }

    def run(self, candles: Iterable[ClosedCandle]) -> tuple[VariantTrade, ...]:
        emitted: list[VariantTrade] = []
        for candle in sorted(candles, key=lambda item: item.ts):
            emitted.extend(self.process_candle(candle))
        return tuple(emitted)

    def process_candle(self, candle: ClosedCandle) -> tuple[VariantTrade, ...]:
        if not candle.complete:
            msg = "paper engine accepts closed candles only"
            raise ValueError(msg)
        if candle.instrument != self._base_strategy_config.instrument:
            msg = "paper engine candle instrument must match strategy config"
            raise ValueError(msg)

        emitted: list[VariantTrade] = []
        for runtime in self._states.values():
            emitted.extend(self._process_variant(runtime, candle))
        return tuple(emitted)

    def _process_variant(
        self,
        runtime: "_VariantRuntime",
        candle: ClosedCandle,
    ) -> tuple[VariantTrade, ...]:
        next_trading_date = _trading_date_for(candle, runtime.strategy_config)
        if next_trading_date != runtime.trading_date:
            runtime.reset_for_day(next_trading_date)

        runtime.candle_index += 1
        runtime.day_history.append(candle)
        if runtime.session_levels is None and _is_at_or_after_ny_window(
            candle,
            runtime.trading_date,
            runtime.strategy_config,
        ):
            runtime.session_levels = compute_session_levels(
                runtime.day_history,
                trading_date=runtime.trading_date,
                instrument=runtime.strategy_config.instrument,
                config=runtime.strategy_config,
            )

        emitted: list[VariantTrade] = []
        if runtime.pending_entry is not None:
            runtime.position = simulate_market_entry(
                runtime.pending_entry,
                entry_candle=candle,
                config=self._fill_config,
                instrument_rules=self._instrument_rules,
            )
            runtime.pending_entry = None

        if runtime.position is not None:
            trade = simulate_bracket_exit(
                runtime.position,
                candle=candle,
                config=self._fill_config,
                instrument_rules=self._instrument_rules,
            )
            if trade is not None:
                emitted.append(_variant_trade(runtime.variant.id, trade))
                runtime.nav += trade.pnl
                runtime.position = None
                runtime.day_state = replace(runtime.day_state, has_open_position=False)

        result = self._strategy_evaluator(
            runtime.day_state,
            candle,
            candle_history=list(runtime.day_history),
            candle_index=runtime.candle_index,
            session_levels=runtime.session_levels,
            config=runtime.strategy_config,
            instrument_rules=self._instrument_rules,
            risk_context=RiskContext(
                nav=runtime.nav,
                day_start_nav=runtime.day_start_nav,
                spread_pips=self._paper_config.spread_pips,
                entry_price=candle.c,
            ),
        )
        runtime.day_state = result.state

        for decision in result.decisions:
            if (
                decision.kind == "market_entry"
                and runtime.position is None
                and runtime.pending_entry is None
            ):
                runtime.pending_entry = entry_setup_from_decision(decision)
            elif decision.kind == "flatten":
                runtime.pending_entry = None
                if runtime.position is not None and self._paper_config.force_ny_close:
                    trade = force_close_position(
                        runtime.position,
                        candle=candle,
                        config=self._fill_config,
                        instrument_rules=self._instrument_rules,
                    )
                    emitted.append(_variant_trade(runtime.variant.id, trade))
                    runtime.nav += trade.pnl
                    runtime.position = None
                    runtime.day_state = replace(runtime.day_state, has_open_position=False)

        return tuple(emitted)


@dataclass
class _VariantRuntime:
    variant: PaperVariant
    strategy_config: StrategyConfig
    nav: Decimal
    day_start_nav: Decimal
    trading_date: date | None = None
    candle_index: int = -1
    day_state: DayState | None = None
    session_levels: SessionLevels | None = None
    day_history: list[ClosedCandle] = field(default_factory=list)
    pending_entry: MarketEntrySetup | None = None
    position: OpenBacktestPosition | None = None

    def reset_for_day(self, trading_date: date) -> None:
        self.trading_date = trading_date
        self.candle_index = -1
        self.day_start_nav = self.nav
        self.day_state = DayState(trading_date=trading_date)
        self.session_levels = None
        self.day_history = []
        self.pending_entry = None
        self.position = None


def _variant_trade(variant_id: int, trade: BacktestTrade) -> VariantTrade:
    return VariantTrade(
        variant_id=variant_id,
        side=trade.side,
        units=trade.units,
        entry_price=trade.entry_price,
        entry_ts=trade.entry_ts,
        exit_price=trade.exit_price,
        exit_ts=trade.exit_ts,
        pnl=trade.pnl,
        r_multiple=trade.r_multiple,
        exit_reason=trade.exit_reason,
    )


def _trading_date_for(candle: ClosedCandle, config: StrategyConfig) -> date:
    local_ts = candle.ts.astimezone(ZoneInfo(config.timezone))
    asia_start = _parse_time(config.sessions["asia"]["start"])
    if local_ts.timetz().replace(tzinfo=None) >= asia_start:
        return local_ts.date() + timedelta(days=1)
    return local_ts.date()


def _is_at_or_after_ny_window(
    candle: ClosedCandle,
    trading_date: date,
    config: StrategyConfig,
) -> bool:
    windows = session_windows_for_date(trading_date, config)
    return candle.ts.astimezone(UTC) >= windows.ny_trade.start


def _parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time()
