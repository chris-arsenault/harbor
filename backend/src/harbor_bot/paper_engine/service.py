import json
from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.instruments import default_instrument_rules
from harbor_bot.observability.websocket import WebSocketHub
from harbor_bot.paper_engine.engine import ShadowPaperEngine, StrategyEvaluator
from harbor_bot.paper_engine.models import PaperEngineConfig, VariantTrade
from harbor_bot.persistence import event_repository, variant_repository
from harbor_bot.strategy.models import InstrumentRules, StrategyConfig


class PaperForwardService:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        base_strategy_config: StrategyConfig,
        instrument_rules: InstrumentRules,
        paper_config: PaperEngineConfig,
        repository: Any = variant_repository,
        event_repository: Any = event_repository,
        websocket_hub: WebSocketHub | None = None,
        strategy_evaluator: StrategyEvaluator | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._engine = engine
        self._base_strategy_config = base_strategy_config
        self._instrument_rules = instrument_rules
        self._paper_config = paper_config
        self._repository = repository
        self._event_repository = event_repository
        self._websocket_hub = websocket_hub
        self._strategy_evaluator = strategy_evaluator
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._runtime_engines: dict[str, tuple[tuple[object, ...], ShadowPaperEngine]] = {}

    async def run_closed_candles(
        self,
        candles: Iterable[ClosedCandle],
    ) -> tuple[VariantTrade, ...]:
        candle_batch = tuple(candles)
        if not candle_batch:
            return ()

        async with self._engine.connect() as connection:
            variants = await self._repository.list_active_paper_variants(connection)
        if not variants:
            self._runtime_engines.clear()
            return ()

        emitted = tuple(
            trade
            for instrument, instrument_variants in _variants_by_instrument(
                variants,
                default_instrument=self._base_strategy_config.instrument,
            ).items()
            for trade in self._run_instrument_batch(
                instrument=instrument,
                variants=instrument_variants,
                candles=tuple(candle for candle in candle_batch if candle.instrument == instrument),
            )
        )
        if not emitted:
            return ()

        trade_ids = await self._repository.append_variant_trades(self._engine, emitted)
        persisted = tuple(
            _trade_with_id(trade, trade_id)
            for trade, trade_id in zip(emitted, trade_ids, strict=True)
        )
        await self._write_trade_events(persisted)
        await self._broadcast_trade_updates(persisted)
        return persisted

    async def _write_trade_events(self, trades: tuple[VariantTrade, ...]) -> None:
        async with self._engine.begin() as connection:
            for trade in trades:
                await self._event_repository.append_event(
                    connection,
                    ts=self._now_utc(),
                    level="info",
                    module="paper_forward",
                    event_type="variant_trade",
                    message=f"paper variant {trade.variant_id} closed simulated trade",
                    data=trade.to_jsonable(),
                )

    async def _broadcast_trade_updates(self, trades: tuple[VariantTrade, ...]) -> None:
        if self._websocket_hub is None:
            return

        for trade in trades:
            await self._websocket_hub.broadcast(
                self._websocket_hub.envelope("variant_trade", trade)
            )

        async with self._engine.connect() as connection:
            for variant_id in _ordered_variant_ids(trades):
                stored_trades = await self._repository.list_variant_trades(
                    connection,
                    variant_id=variant_id,
                    limit=self._paper_config.max_lab_rows,
                )
                equity = variant_repository.derive_equity_curve(
                    variant_id=variant_id,
                    trades=stored_trades,
                    initial_nav=self._paper_config.initial_nav,
                )
                if equity:
                    await self._websocket_hub.broadcast(
                        self._websocket_hub.envelope(
                            "variant_equity",
                            {
                                "variant_id": variant_id,
                                "points": [point.to_jsonable() for point in equity],
                            },
                        )
                    )

    def _now_utc(self) -> datetime:
        return self._clock().astimezone(UTC)

    def _run_instrument_batch(
        self,
        *,
        instrument: str,
        variants: tuple[Any, ...],
        candles: tuple[ClosedCandle, ...],
    ) -> tuple[VariantTrade, ...]:
        if not candles:
            return ()
        engine_kwargs: dict[str, Any] = {
            "variants": variants,
            "base_strategy_config": replace(self._base_strategy_config, instrument=instrument),
            "instrument_rules": _instrument_rules(instrument, self._instrument_rules),
            "paper_config": self._paper_config,
        }
        if self._strategy_evaluator is not None:
            engine_kwargs["strategy_evaluator"] = self._strategy_evaluator
        signature = _variant_signature(instrument, variants)
        cached = self._runtime_engines.get(instrument)
        if cached is None or cached[0] != signature:
            cached = (signature, ShadowPaperEngine(**engine_kwargs))
            self._runtime_engines[instrument] = cached
        return cached[1].run(candles)


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


def _ordered_variant_ids(trades: Iterable[VariantTrade]) -> tuple[int, ...]:
    variant_ids: list[int] = []
    for trade in trades:
        if trade.variant_id not in variant_ids:
            variant_ids.append(trade.variant_id)
    return tuple(variant_ids)


def _variant_signature(instrument: str, variants: tuple[Any, ...]) -> tuple[object, ...]:
    return (
        instrument,
        tuple(
            (
                int(variant.id),
                str(variant.status),
                str(getattr(variant, "label", "")),
                int(getattr(variant, "source_trial_id", 0)),
                json.dumps(dict(variant.params), sort_keys=True, default=str),
            )
            for variant in variants
        ),
    )


def _variants_by_instrument(
    variants: Iterable[Any],
    *,
    default_instrument: str,
) -> dict[str, tuple[Any, ...]]:
    grouped: dict[str, list[Any]] = {}
    for variant in variants:
        instrument = str(variant.params.get("instrument") or default_instrument).upper()
        grouped.setdefault(instrument, []).append(variant)
    return {instrument: tuple(items) for instrument, items in grouped.items()}


def _instrument_rules(instrument: str, fallback: InstrumentRules) -> InstrumentRules:
    if instrument == fallback.instrument:
        return fallback
    return default_instrument_rules(instrument)
