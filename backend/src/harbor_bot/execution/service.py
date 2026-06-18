from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.execution.models import BrokerOrder, ExecutionSignal, PracticeExecutionConfig
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.notifier.models import NotificationEvent
from harbor_bot.oanda.types import ClientExtensions, MarketOrderRequest, OrderCreateResult
from harbor_bot.optimizer.config import apply_params_to_strategy_config
from harbor_bot.persistence import execution_repository, variant_repository
from harbor_bot.strategy.core import RiskContext, StrategyResult, evaluate_closed_candle
from harbor_bot.strategy.models import (
    DayState,
    InstrumentRules,
    MarketEntrySetup,
    SessionLevels,
    StrategyConfig,
    require_closed_candle,
)

StrategyEvaluator = Callable[..., StrategyResult]


@dataclass(frozen=True)
class PracticeExecutionResult:
    orders_placed: int = 0
    skipped_reason: str | None = None
    flatten_requested: bool = False


class PracticeExecutionService:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        variant_repository: Any = variant_repository,
        execution_repository: Any = execution_repository,
        oanda_client: Any,
        notifier: Any,
        websocket_hub: Any | None,
        control_service: Any | None = None,
        execution_config: PracticeExecutionConfig,
        base_strategy_config: StrategyConfig,
        instrument_rules: InstrumentRules,
        strategy_evaluator: StrategyEvaluator | None = None,
    ) -> None:
        self._engine = engine
        self._variant_repository = variant_repository
        self._execution_repository = execution_repository
        self._oanda = oanda_client
        self._notifier = notifier
        self._websocket_hub = websocket_hub
        self._control_service = control_service
        self._execution_config = execution_config
        self._base_strategy_config = base_strategy_config
        self._instrument_rules = instrument_rules
        self._strategy_evaluator = strategy_evaluator or self._default_strategy_evaluator

    async def process_closed_candle(
        self,
        candle: ClosedCandle,
        *,
        day_state: DayState | None = None,
        candle_history: list[ClosedCandle] | None = None,
        candle_index: int = 0,
        session_levels: SessionLevels | None = None,
        risk_context: RiskContext | None = None,
    ) -> PracticeExecutionResult:
        candle = require_closed_candle(candle)

        async with self._engine.connect() as connection:
            promoted = await self._variant_repository.get_promoted_variant(connection)
            if promoted is None:
                return PracticeExecutionResult(skipped_reason="no_promoted_variant")

            controls = await self._execution_repository.get_trading_controls(
                connection,
                confirmation_token=self._execution_config.confirmation_token,
            )
            if not controls.trading_enabled:
                return PracticeExecutionResult(skipped_reason="trading_disabled")
            if controls.kill_switch_state.value != "clear":
                return PracticeExecutionResult(skipped_reason="kill_switch")

            open_trades = await self._execution_repository.list_open_bot_trades(connection)
            if len(open_trades) >= self._execution_config.max_open_positions:
                return PracticeExecutionResult(skipped_reason="open_position")

            config = apply_params_to_strategy_config(
                self._base_strategy_config,
                dict(promoted["params"]),
            )
            result = self._strategy_evaluator(
                day_state=day_state or DayState(trading_date=candle.ts.date()),
                candle=candle,
                candle_history=candle_history or [candle],
                candle_index=candle_index,
                session_levels=session_levels,
                config=config,
                instrument_rules=self._instrument_rules,
                risk_context=risk_context or _default_risk_context(candle),
            )

            for decision in result.decisions:
                if decision.kind == "flatten":
                    if self._control_service is not None:
                        await self._control_service.flatten_now(
                            reason=str(decision.payload.get("reason", "strategy_flatten"))
                        )
                    return PracticeExecutionResult(flatten_requested=True)
                if decision.kind != "market_entry":
                    continue

                setup = decision.payload.get("setup")
                if not isinstance(setup, MarketEntrySetup):
                    continue
                signal = _execution_signal(
                    namespace=self._execution_config.signal_id_namespace,
                    variant_id=int(promoted["id"]),
                    setup=setup,
                )
                reservation = await self._execution_repository.reserve_signal(connection, signal)
                if not reservation.reserved:
                    return PracticeExecutionResult(skipped_reason="duplicate_signal")

                broker_order = await self._place_order(setup=setup, signal=signal)
                signal_id = await self._execution_repository.get_signal_id_by_key(
                    connection,
                    signal.signal_key,
                )
                if signal_id is None:
                    msg = f"reserved signal {signal.signal_key} was not found"
                    raise RuntimeError(msg)
                await self._execution_repository.create_or_update_trade_from_order(
                    connection,
                    signal_id=signal_id,
                    signal=signal,
                    order=broker_order,
                )
                await self._execution_repository.append_execution_event(
                    connection,
                    ts=setup.ts,
                    level="info",
                    event_type="trade_filled",
                    message="practice order filled",
                    data=broker_order.to_jsonable(),
                )
                await self._notify_fill(setup=setup, broker_order=broker_order)
                await self._broadcast(
                    {
                        "type": "trade",
                        "payload": broker_order.to_jsonable(),
                    }
                )
                return PracticeExecutionResult(orders_placed=1)

        return PracticeExecutionResult(skipped_reason="no_action")

    def _default_strategy_evaluator(self, **kwargs: Any) -> StrategyResult:
        return evaluate_closed_candle(**kwargs)

    async def _place_order(
        self,
        *,
        setup: MarketEntrySetup,
        signal: ExecutionSignal,
    ) -> BrokerOrder:
        signed_units = _signed_units(setup)
        result: OrderCreateResult = await self._oanda.create_market_order_with_bracket(
            MarketOrderRequest(
                instrument=setup.instrument,
                units=signed_units,
                stop_loss_price=setup.stop,
                take_profit_price=setup.target,
                client_extensions=ClientExtensions(
                    client_id=signal.signal_key,
                    tag=self._execution_config.signal_id_namespace,
                    comment="Harbor promoted variant practice execution",
                ),
            )
        )
        return BrokerOrder(
            client_order_id=signal.signal_key,
            broker_order_id=result.order_id,
            broker_trade_id=result.trade_id,
            fill_transaction_id=result.fill_transaction_id,
            instrument=result.instrument,
            units=result.units,
            price=result.price,
            stop_loss_price=setup.stop,
            take_profit_price=setup.target,
            ts=setup.ts,
        )

    async def _notify_fill(
        self,
        *,
        setup: MarketEntrySetup,
        broker_order: BrokerOrder,
    ) -> None:
        await self._notifier.notify(
            NotificationEvent(
                event_type="fill",
                title="Harbor practice fill",
                message=f"{setup.side} {setup.instrument} {broker_order.units}",
                ts=setup.ts,
                severity="info",
                data=broker_order.to_jsonable(),
            )
        )

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if self._websocket_hub is not None:
            await self._websocket_hub.broadcast(message)


def _execution_signal(
    *,
    namespace: str,
    variant_id: int,
    setup: MarketEntrySetup,
) -> ExecutionSignal:
    signal_key = f"{namespace}:{variant_id}:{setup.instrument}:{setup.ts.isoformat()}"
    return ExecutionSignal(
        signal_key=signal_key,
        variant_id=variant_id,
        instrument=setup.instrument,
        direction=setup.side,
        entry_price=setup.entry_reference,
        stop_loss_price=setup.stop,
        take_profit_price=setup.target,
        units=abs(setup.units),
        ts=setup.ts,
    )


def _signed_units(setup: MarketEntrySetup) -> int:
    magnitude = int(abs(Decimal(str(setup.units))))
    return magnitude if setup.side == "long" else -magnitude


def _default_risk_context(candle: ClosedCandle) -> RiskContext:
    return RiskContext(
        nav=Decimal("10000"),
        day_start_nav=Decimal("10000"),
        spread_pips=Decimal("0"),
        entry_price=candle.c,
    )
