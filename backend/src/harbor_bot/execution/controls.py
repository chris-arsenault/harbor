from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.execution.models import (
    FlattenResult,
    KillSwitchState,
    PracticeExecutionConfig,
    TradingControls,
)
from harbor_bot.notifier.models import NotificationEvent
from harbor_bot.persistence import execution_repository, variant_repository


class TradingControlService:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        variant_repository: Any = variant_repository,
        execution_repository: Any = execution_repository,
        oanda_client: Any,
        reconciler: Any,
        notifier: Any,
        websocket_hub: Any | None = None,
        execution_config: PracticeExecutionConfig,
        oanda_env: str,
    ) -> None:
        self._engine = engine
        self._variant_repository = variant_repository
        self._execution_repository = execution_repository
        self._oanda = oanda_client
        self._reconciler = reconciler
        self._notifier = notifier
        self._websocket_hub = websocket_hub
        self._config = execution_config
        self._oanda_env = oanda_env.lower()

    async def set_trading_enabled(
        self,
        *,
        enabled: bool,
        confirmation_token: str,
    ) -> TradingControls:
        self._require_practice_mode()
        self._require_confirmation(confirmation_token)
        async with self._engine.connect() as connection:
            current = await self._execution_repository.get_trading_controls(
                connection,
                confirmation_token=self._config.confirmation_token,
            )
            if enabled:
                if current.kill_switch_state is not KillSwitchState.CLEAR:
                    msg = "cannot enable trading while kill switch is tripped"
                    raise ValueError(msg)
                promoted = await self._variant_repository.get_promoted_variant(connection)
                if promoted is None:
                    msg = "cannot enable practice trading without one promoted variant"
                    raise ValueError(msg)
                open_trades = await self._execution_repository.list_open_bot_trades(connection)
                if open_trades:
                    msg = "cannot enable practice trading with unreconciled open broker trades"
                    raise ValueError(msg)

            controls = TradingControls(
                trading_enabled=enabled,
                confirmation_token=self._config.confirmation_token,
                kill_switch_state=current.kill_switch_state,
                kill_switch_reason=current.kill_switch_reason,
                updated_ts=_now(),
            )
            await self._execution_repository.set_trading_controls(connection, controls)
            await self._execution_repository.append_execution_event(
                connection,
                ts=controls.updated_ts or _now(),
                level="info",
                event_type="trading_enabled" if enabled else "trading_disabled",
                message="practice trading enabled" if enabled else "practice trading disabled",
                data=controls.to_jsonable(),
            )
        await self._broadcast({"type": "control", "payload": controls.to_jsonable()})
        return controls

    async def flatten_now(
        self,
        *,
        reason: str = "manual",
        confirmation_token: str | None = None,
    ) -> FlattenResult:
        self._require_practice_mode()
        if confirmation_token is not None:
            self._require_confirmation(confirmation_token)
        requested_ts = _now()
        open_trades = await self._oanda.list_open_trades()
        open_positions = await self._oanda.list_open_positions()
        closed_trade_ids: list[str] = []
        closed_position_instruments: list[str] = []

        for trade in open_trades:
            await self._oanda.close_trade(trade_id=trade.trade_id)
            closed_trade_ids.append(trade.trade_id)

        for position in open_positions:
            if position.long_units != 0:
                await self._oanda.close_position(
                    instrument=position.instrument,
                    long_units="ALL",
                )
                closed_position_instruments.append(position.instrument)
            elif position.short_units != 0:
                await self._oanda.close_position(
                    instrument=position.instrument,
                    short_units="ALL",
                )
                closed_position_instruments.append(position.instrument)

        reconciliation = await self._reconciler.reconcile_open_state()
        result = FlattenResult(
            requested_ts=requested_ts,
            reason=reason,
            closed_trade_ids=tuple(closed_trade_ids),
            closed_position_instruments=tuple(closed_position_instruments),
            reconciliation=reconciliation,
        )
        await self._notifier.notify(
            NotificationEvent(
                event_type="flatten",
                title="Harbor practice flatten",
                message=f"Flattened practice exposure: {reason}",
                ts=requested_ts,
                severity="warning",
                data=result.to_jsonable(),
            )
        )
        async with self._engine.connect() as connection:
            await self._execution_repository.append_execution_event(
                connection,
                ts=requested_ts,
                level="warning",
                event_type="flatten",
                message=f"practice exposure flattened: {reason}",
                data=result.to_jsonable(),
            )
        await self._broadcast({"type": "control", "payload": result.to_jsonable()})
        return result

    async def get_status_overlay(self) -> dict[str, Any]:
        async with self._engine.connect() as connection:
            controls = await self._execution_repository.get_trading_controls(
                connection,
                confirmation_token=self._config.confirmation_token,
            )
            promoted = await self._variant_repository.get_promoted_variant(connection)
            open_trades = await self._execution_repository.list_open_bot_trades(connection)
        return {
            "trading_enabled": controls.trading_enabled,
            "trading_controls_available": self._oanda_env == "practice",
            "kill_switch_state": controls.kill_switch_state.value,
            "promoted_variant": None
            if promoted is None
            else {"id": promoted["id"], "label": promoted["label"], "status": promoted["status"]},
            "open_positions": len(open_trades),
            "open_position": open_trades[0] if open_trades else None,
            "reconciliation_state": {"drift_detected": False},
            "notifier_state": {
                "ntfy_enabled": self._config.ntfy_enabled,
                "telegram_enabled": self._config.telegram_enabled,
            },
        }

    async def flatten_for_ny_close(self) -> FlattenResult:
        return await self.flatten_now(reason="ny_close")

    async def trip_daily_loss_if_needed(
        self,
        *,
        day_start_nav: Decimal,
        current_nav: Decimal,
    ) -> FlattenResult | None:
        day_start_nav = Decimal(str(day_start_nav))
        current_nav = Decimal(str(current_nav))
        loss_pct = (day_start_nav - current_nav) / day_start_nav * Decimal("100")
        if loss_pct < self._config.max_daily_loss_pct:
            return None

        async with self._engine.connect() as connection:
            controls = TradingControls(
                trading_enabled=False,
                confirmation_token=self._config.confirmation_token,
                kill_switch_state=KillSwitchState.TRIPPED,
                kill_switch_reason="daily_loss",
                updated_ts=_now(),
            )
            await self._execution_repository.set_trading_controls(connection, controls)
            await self._execution_repository.append_execution_event(
                connection,
                ts=controls.updated_ts or _now(),
                level="critical",
                event_type="kill_switch",
                message="daily loss kill switch tripped",
                data={"loss_pct": str(loss_pct), **controls.to_jsonable()},
            )
        await self._notifier.notify(
            NotificationEvent(
                event_type="kill_switch",
                title="Harbor daily loss kill switch",
                message="Daily loss limit reached; practice trading disabled",
                ts=_now(),
                severity="critical",
                data={"loss_pct": str(loss_pct)},
            )
        )
        return await self.flatten_now(reason="daily_loss")

    def _require_confirmation(self, confirmation_token: str) -> None:
        if confirmation_token != self._config.confirmation_token:
            msg = "invalid practice trading confirmation token"
            raise ValueError(msg)

    def _require_practice_mode(self) -> None:
        if self._oanda_env != "practice":
            msg = "M9 controls are practice mode only"
            raise ValueError(msg)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        if self._websocket_hub is not None:
            await self._websocket_hub.broadcast(message)


def _now() -> datetime:
    return datetime.now(UTC)
