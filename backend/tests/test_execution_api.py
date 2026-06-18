from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.execution.models import FlattenResult, ReconciliationSummary, TradingControls
from harbor_bot.lab.models import LabActionResult
from harbor_bot.observability.models import StatusSnapshot


def test_promote_variant_endpoint_uses_lab_service_practice_promotion() -> None:
    lab = FakeLabService()
    client = TestClient(create_app(lab_service=lab, control_service=FakeControlService()))

    response = client.post("/api/variants/7/promote")

    assert response.status_code == 200
    assert response.json() == {
        "action": "promote_practice_variant",
        "variant_id": 7,
        "status": "promoted",
    }
    assert lab.promoted == [7]


def test_trading_control_endpoint_requires_confirmation_and_returns_controls() -> None:
    controls = FakeControlService()
    client = TestClient(create_app(control_service=controls))

    response = client.post(
        "/api/control/trading",
        json={"enabled": True, "confirmation_token": "OANDA_PRACTICE"},
    )

    assert response.status_code == 200
    assert response.json()["trading_enabled"] is True
    assert response.json()["kill_switch_state"] == "clear"
    assert controls.trading_requests == [(True, "OANDA_PRACTICE")]


def test_flatten_endpoint_requires_confirmation_and_returns_result() -> None:
    controls = FakeControlService()
    client = TestClient(create_app(control_service=controls))

    response = client.post(
        "/api/control/flatten",
        json={"confirmation_token": "OANDA_PRACTICE", "reason": "manual"},
    )

    assert response.status_code == 200
    assert response.json()["reason"] == "manual"
    assert response.json()["closed_trade_ids"] == ["7001"]
    assert controls.flatten_requests == [("manual", "OANDA_PRACTICE")]


def test_control_guard_failures_return_400() -> None:
    controls = FakeControlService(raise_on_enable=True)
    client = TestClient(create_app(control_service=controls))

    response = client.post(
        "/api/control/trading",
        json={"enabled": True, "confirmation_token": "bad"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid practice trading confirmation token"}


def test_status_endpoint_serializes_m9_execution_fields() -> None:
    client = TestClient(create_app(observability_service=FakeObservabilityService()))

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["trading_controls_available"] is True
    assert response.json()["promoted_variant"] == {"id": 7, "label": "promoted"}
    assert response.json()["reconciliation_state"]["drift_detected"] is False
    assert response.json()["open_position"]["instrument"] == "EUR_USD"


class FakeLabService:
    def __init__(self) -> None:
        self.promoted: list[int] = []

    async def promote_variant_for_practice(
        self,
        *,
        variant_id: int,
        trading_enabled: bool = False,
        open_broker_trade_count: int = 0,
    ) -> LabActionResult:
        self.promoted.append(variant_id)
        assert trading_enabled is False
        assert open_broker_trade_count == 0
        return LabActionResult(
            action="promote_practice_variant",
            variant_id=variant_id,
            status="promoted",
        )


class FakeControlService:
    def __init__(self, *, raise_on_enable: bool = False) -> None:
        self.raise_on_enable = raise_on_enable
        self.trading_requests: list[tuple[bool, str]] = []
        self.flatten_requests: list[tuple[str, str]] = []

    async def set_trading_enabled(self, *, enabled: bool, confirmation_token: str):
        self.trading_requests.append((enabled, confirmation_token))
        if self.raise_on_enable:
            raise ValueError("invalid practice trading confirmation token")
        return TradingControls(
            trading_enabled=enabled,
            confirmation_token=confirmation_token,
            updated_ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        )

    async def flatten_now(self, *, reason: str, confirmation_token: str):
        self.flatten_requests.append((reason, confirmation_token))
        return FlattenResult(
            requested_ts=datetime(2026, 1, 15, 16, 59, tzinfo=UTC),
            reason=reason,
            closed_trade_ids=("7001",),
            closed_position_instruments=("EUR_USD",),
            reconciliation=ReconciliationSummary(
                checked_ts=datetime(2026, 1, 15, 17, 0, tzinfo=UTC),
                transaction_count=0,
                bot_open_trade_count=0,
                broker_open_trade_count=0,
                broker_open_position_count=0,
                drift_detected=False,
                checkpoint_transaction_id="9201",
            ),
        )


class FakeObservabilityService:
    async def get_status(self) -> StatusSnapshot:
        return StatusSnapshot(
            bot_state="IDLE",
            session_phase="ny_trade",
            connection_health="ok",
            mode="practice",
            trading_enabled=True,
            trading_controls_available=True,
            kill_switch_state="clear",
            day_pnl=Decimal("18.0"),
            trades_today=1,
            max_trades_per_day=1,
            account_nav=Decimal("10018.0"),
            open_positions=1,
            unrealized_pnl=Decimal("0"),
            last_heartbeat=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
            promoted_variant={"id": 7, "label": "promoted"},
            reconciliation_state={"drift_detected": False},
            open_position={"instrument": "EUR_USD"},
        )
