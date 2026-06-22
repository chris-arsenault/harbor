from dataclasses import dataclass, replace
from decimal import Decimal

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.fvgs import detect_fvg
from harbor_bot.strategy.models import (
    DayState,
    InstrumentRules,
    SessionLevels,
    StrategyConfig,
    StrategyDecision,
    require_closed_candle,
)
from harbor_bot.strategy.risk import (
    check_daily_loss,
    check_one_position,
    check_one_trade_per_level,
    check_spread,
    check_trade_count,
    daily_loss_flatten_decision,
    ny_close_flatten_decision,
)
from harbor_bot.strategy.signals import build_market_entry_setup
from harbor_bot.strategy.structure import mss_confirmed
from harbor_bot.strategy.sweeps import detect_sweep, mark_level_taken, with_active_sweep


@dataclass(frozen=True)
class RiskContext:
    nav: Decimal
    day_start_nav: Decimal
    spread_pips: Decimal
    entry_price: Decimal


@dataclass(frozen=True)
class StrategyResult:
    state: DayState
    decisions: list[StrategyDecision]


def evaluate_closed_candle(
    day_state: DayState,
    candle: ClosedCandle,
    *,
    candle_history: list[ClosedCandle],
    candle_index: int,
    session_levels: SessionLevels | None,
    config: StrategyConfig,
    instrument_rules: InstrumentRules,
    risk_context: RiskContext,
) -> StrategyResult:
    candle = require_closed_candle(candle)

    flatten = ny_close_flatten_decision(
        candle,
        trading_date=day_state.trading_date,
        config=config,
        has_open_position=day_state.has_open_position,
    )
    if flatten is not None:
        return StrategyResult(
            state=replace(day_state, has_open_position=False, active_sweep=None),
            decisions=[
                StrategyDecision(
                    kind="flatten",
                    ts=flatten.ts,
                    payload={"reason": flatten.reason},
                )
            ],
        )

    daily_loss_flatten = daily_loss_flatten_decision(
        ts=candle.ts,
        day_start_nav=risk_context.day_start_nav,
        current_nav=risk_context.nav,
        config=config,
    )
    if daily_loss_flatten is not None:
        return StrategyResult(
            state=replace(
                day_state,
                has_open_position=False,
                active_sweep=None,
                trading_disabled=True,
            ),
            decisions=[
                StrategyDecision(
                    kind="flatten",
                    ts=daily_loss_flatten.ts,
                    payload={"reason": daily_loss_flatten.reason},
                )
            ],
        )

    if day_state.trading_disabled or session_levels is None:
        return StrategyResult(state=day_state, decisions=[])

    if day_state.active_sweep is None:
        sweep = detect_sweep(
            candle,
            levels=session_levels,
            config=config,
            instrument_rules=instrument_rules,
            day_state=day_state,
            candle_index=candle_index,
        )
        if sweep is None:
            return StrategyResult(state=day_state, decisions=[])
        return StrategyResult(
            state=with_active_sweep(day_state, sweep),
            decisions=[
                StrategyDecision(
                    kind="sweep",
                    ts=sweep.swept_ts,
                    payload={"level_name": sweep.level_name.value, "bias": sweep.bias.value},
                )
            ],
        )

    if candle_index > day_state.active_sweep.fvg_deadline_index:
        return StrategyResult(
            state=with_active_sweep(day_state, None),
            decisions=[
                StrategyDecision(
                    kind="sweep_expired",
                    ts=candle.ts,
                    payload={"level_name": day_state.active_sweep.level_name.value},
                )
            ],
        )

    fvg = detect_fvg(
        candle_history,
        active_sweep=day_state.active_sweep,
        current_index=candle_index,
        trading_date=day_state.trading_date,
        config=config,
    )
    if fvg is None:
        return StrategyResult(state=day_state, decisions=[])

    if config.require_mss and not mss_confirmed(
        candle_history, sweep=fvg.sweep, current_index=candle_index, config=config
    ):
        return StrategyResult(state=day_state, decisions=[])

    veto = _first_veto(day_state, fvg.sweep.level_name, config, risk_context)
    if veto is not None:
        return StrategyResult(
            state=day_state,
            decisions=[StrategyDecision(kind="veto", ts=candle.ts, payload={"reason": veto})],
        )

    setup = build_market_entry_setup(
        fvg=fvg,
        entry_price=risk_context.entry_price,
        nav=risk_context.nav,
        levels=session_levels,
        recent_candles=candle_history,
        config=config,
        instrument_rules=instrument_rules,
    )
    if setup is None:
        return StrategyResult(
            state=day_state,
            decisions=[StrategyDecision(kind="veto", ts=candle.ts, payload={"reason": "target"})],
        )

    next_state = mark_level_taken(day_state, fvg.sweep.level_name)
    next_state = replace(
        next_state,
        trades_taken=next_state.trades_taken + 1,
        has_open_position=True,
    )
    return StrategyResult(
        state=next_state,
        decisions=[StrategyDecision(kind="market_entry", ts=candle.ts, payload={"setup": setup})],
    )


def _first_veto(
    day_state: DayState,
    level_name,
    config: StrategyConfig,
    risk_context: RiskContext,
) -> str | None:
    checks = [
        check_spread(risk_context.spread_pips, config),
        check_daily_loss(
            day_start_nav=risk_context.day_start_nav,
            current_nav=risk_context.nav,
            config=config,
        ),
        check_trade_count(day_state, config),
        check_one_position(day_state),
        check_one_trade_per_level(day_state, level_name, config),
    ]
    for result in checks:
        if not result.allowed:
            return result.reason
    return None
