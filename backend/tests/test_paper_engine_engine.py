from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.paper_engine.engine import ShadowPaperEngine
from harbor_bot.paper_engine.models import PaperEngineConfig, PaperVariant
from harbor_bot.strategy.core import StrategyResult
from harbor_bot.strategy.models import (
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    StrategyDecision,
    strategy_config_from_defaults,
)


def test_shadow_engine_runs_active_variants_independently_on_same_closed_stream() -> None:
    seen_fvg_windows: list[int] = []

    def evaluator(day_state, candle, *, config, candle_history, risk_context, **kwargs):
        assert candle_history[-1] == candle
        assert risk_context.spread_pips == Decimal("0.8")
        seen_fvg_windows.append(config.fvg_window)
        if candle.ts == datetime(2026, 1, 15, 14, 0, tzinfo=UTC):
            setup = MarketEntrySetup(
                ts=candle.ts,
                instrument="EUR_USD",
                side="long",
                level_name=LevelName.ASIA_LOW,
                entry_reference=candle.c,
                stop=Decimal("1.0990"),
                target=Decimal("1.1020"),
                risk=Decimal("0.0010"),
                units=Decimal("10000"),
            )
            return StrategyResult(
                state=replace(
                    day_state,
                    has_open_position=True,
                    trades_taken=day_state.trades_taken + 1,
                ),
                decisions=[
                    StrategyDecision(
                        kind="market_entry",
                        ts=candle.ts,
                        payload={"setup": setup},
                    )
                ],
            )
        return StrategyResult(state=day_state, decisions=[])

    engine = ShadowPaperEngine(
        variants=(
            PaperVariant(id=1, label="trial-1", params={"fvg_window": 7}, source_trial_id=1),
            PaperVariant(id=2, label="trial-2", params={"fvg_window": 11}, source_trial_id=2),
        ),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        paper_config=PaperEngineConfig(),
        strategy_evaluator=evaluator,
    )

    trades = engine.run(_trade_candles())

    assert {trade.variant_id for trade in trades} == {1, 2}
    assert {trade.exit_reason for trade in trades} == {"take_profit"}
    assert all(trade.entry_price == Decimal("1.10005") for trade in trades)
    assert all(trade.pnl == Decimal("19.50000") for trade in trades)
    assert 7 in seen_fvg_windows
    assert 11 in seen_fvg_windows


def test_shadow_engine_rejects_incomplete_candles() -> None:
    engine = ShadowPaperEngine(
        variants=(PaperVariant(id=1, label="trial-1", params={}, source_trial_id=1),),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        paper_config=PaperEngineConfig(),
    )

    with pytest.raises(ValueError, match="closed candles only"):
        engine.process_candle(_candle("2026-01-15T14:30:00+00:00", complete=False))


def test_shadow_engine_ignores_retired_variants() -> None:
    retired = PaperVariant(id=1, label="trial-1", params={}, source_trial_id=1)
    object.__setattr__(retired, "status", "retired")
    calls = 0

    def evaluator(day_state, candle, **kwargs):
        nonlocal calls
        calls += 1
        return StrategyResult(state=day_state, decisions=[])

    engine = ShadowPaperEngine(
        variants=(retired,),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        paper_config=PaperEngineConfig(),
        strategy_evaluator=evaluator,
    )

    assert engine.run(_trade_candles()) == ()
    assert calls == 0


def _trade_candles() -> tuple[ClosedCandle, ...]:
    return (
        _candle("2026-01-15T14:00:00+00:00", high="1.1005", low="1.0995", close="1.1000"),
        _candle("2026-01-15T14:01:00+00:00", high="1.1030", low="1.0995", close="1.1025"),
    )


def _candle(
    ts: str,
    *,
    high: str = "1.1010",
    low: str = "1.0990",
    close: str = "1.1005",
    complete: bool = True,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.1000"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=100,
        complete=complete,
    )


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
