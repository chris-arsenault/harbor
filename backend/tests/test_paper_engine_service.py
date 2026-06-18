from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.paper_engine.models import PaperEngineConfig, PaperVariant, VariantTrade
from harbor_bot.paper_engine.service import PaperForwardService
from harbor_bot.strategy.core import StrategyResult
from harbor_bot.strategy.models import (
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    StrategyDecision,
    strategy_config_from_defaults,
)


def test_paper_forward_service_persists_events_and_broadcasts_from_injected_batch() -> None:
    repository = FakeVariantRepository(
        (
            PaperVariant(id=1, label="trial-1", params={"fvg_window": 7}, source_trial_id=1),
            PaperVariant(id=2, label="trial-2", params={"fvg_window": 11}, source_trial_id=2),
        )
    )
    event_repository = FakeEventRepository()
    hub = FakeHub()
    service = PaperForwardService(
        engine=FakeEngine(),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        paper_config=PaperEngineConfig(),
        repository=repository,
        event_repository=event_repository,
        websocket_hub=hub,
        strategy_evaluator=_entry_evaluator,
        clock=lambda: datetime(2026, 1, 15, 14, 45, tzinfo=UTC),
    )

    trades = run(service.run_closed_candles(_trade_candles()))

    assert {trade.variant_id for trade in trades} == {1, 2}
    assert {trade.id for trade in trades} == {101, 102}
    assert repository.persisted_variant_ids == [1, 2]
    assert [event["type"] for event in event_repository.events] == [
        "variant_trade",
        "variant_trade",
    ]
    assert event_repository.events[0]["module"] == "paper_forward"
    assert event_repository.events[0]["data"]["variant_id"] == 1
    assert [envelope["type"] for envelope in hub.broadcasts] == [
        "variant_trade",
        "variant_trade",
        "variant_equity",
        "variant_equity",
    ]
    assert hub.broadcasts[-1]["payload"]["points"][-1]["variant_id"] == 2


def test_paper_forward_service_returns_empty_without_active_variants() -> None:
    repository = FakeVariantRepository(())
    event_repository = FakeEventRepository()
    service = PaperForwardService(
        engine=FakeEngine(),
        base_strategy_config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        paper_config=PaperEngineConfig(),
        repository=repository,
        event_repository=event_repository,
        strategy_evaluator=_entry_evaluator,
    )

    assert run(service.run_closed_candles(_trade_candles())) == ()
    assert repository.persisted_variant_ids == []
    assert event_repository.events == []


def _entry_evaluator(day_state, candle, *, config, **kwargs):
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
                StrategyDecision(kind="market_entry", ts=candle.ts, payload={"setup": setup})
            ],
        )
    return StrategyResult(state=day_state, decisions=[])


def _trade_candles() -> tuple[ClosedCandle, ...]:
    return (
        _candle("2026-01-15T14:00:00+00:00", high="1.1005", low="1.0995", close="1.1000"),
        _candle("2026-01-15T14:01:00+00:00", high="1.1030", low="1.0995", close="1.1025"),
    )


def _candle(
    ts: str,
    *,
    high: str,
    low: str,
    close: str,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.1000"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=100,
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


def _trade_with_id(trade: VariantTrade, trade_id: int) -> VariantTrade:
    return VariantTrade(
        id=trade_id,
        variant_id=trade.variant_id,
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


def run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)


class FakeConnection:
    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()

    def begin(self) -> FakeConnection:
        return FakeConnection()


class FakeVariantRepository:
    def __init__(self, variants: tuple[PaperVariant, ...]) -> None:
        self.variants = variants
        self.persisted_variant_ids: list[int] = []
        self.trades: dict[int, list[VariantTrade]] = {}

    async def list_active_paper_variants(self, _connection: object):
        return self.variants

    async def append_variant_trades(
        self,
        _engine: object,
        trades: tuple[VariantTrade, ...],
    ) -> tuple[int, ...]:
        ids: list[int] = []
        for offset, trade in enumerate(trades, start=101):
            persisted = _trade_with_id(trade, offset)
            self.persisted_variant_ids.append(trade.variant_id)
            self.trades.setdefault(trade.variant_id, []).append(persisted)
            ids.append(offset)
        return tuple(ids)

    async def list_variant_trades(
        self,
        _connection: object,
        *,
        variant_id: int,
        limit: int,
    ) -> tuple[VariantTrade, ...]:
        return tuple(self.trades.get(variant_id, ())[-limit:])


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def append_event(
        self,
        _connection: object,
        *,
        ts: datetime,
        level: str,
        module: str,
        event_type: str,
        message: str,
        data: dict[str, Any],
    ) -> int:
        self.events.append(
            {
                "ts": ts,
                "level": level,
                "module": module,
                "type": event_type,
                "message": message,
                "data": data,
            }
        )
        return len(self.events)


class FakeHub:
    def __init__(self) -> None:
        self.broadcasts: list[dict[str, Any]] = []

    def envelope(self, event_type: str, payload: Any) -> dict[str, Any]:
        if hasattr(payload, "to_jsonable"):
            payload = payload.to_jsonable()
        return {"type": event_type, "payload": payload}

    async def broadcast(self, envelope: dict[str, Any]) -> None:
        self.broadcasts.append(envelope)
