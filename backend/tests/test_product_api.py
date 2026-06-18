from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app


def test_product_query_endpoints_read_full_product_surface() -> None:
    service = FakeProductQueryService()
    client = TestClient(create_app(product_query_service=service))

    trades = client.get("/api/trades?from=2026-01-15T14:00:00Z&to=2026-01-15T17:00:00Z&limit=25")
    backtests = client.get("/api/backtests?limit=10")
    studies = client.get("/api/optimize?limit=5")
    variant = client.get("/api/variants/7")

    assert trades.status_code == 200
    assert trades.json()["trades"][0]["broker_trade_id"] == "7001"
    assert backtests.status_code == 200
    assert backtests.json()["runs"][0]["run_id"] == 42
    assert studies.status_code == 200
    assert studies.json()["studies"][0]["study_id"] == 3
    assert variant.status_code == 200
    assert variant.json()["variant"]["id"] == 7
    assert service.calls == [
        (
            "trades",
            datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
            datetime(2026, 1, 15, 17, 0, tzinfo=UTC),
            25,
        ),
        ("backtests", 10),
        ("studies", 5),
        ("variant", 7),
    ]


def test_variant_detail_returns_404_for_unknown_variant() -> None:
    client = TestClient(create_app(product_query_service=FakeProductQueryService()))

    response = client.get("/api/variants/404")

    assert response.status_code == 404
    assert response.json() == {"detail": "variant not found"}


class FakeProductQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    async def list_trades(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> dict[str, Any]:
        self.calls.append(("trades", start, end, limit))
        return {
            "trades": [
                {
                    "id": 9,
                    "signal_id": 4,
                    "instrument": "EUR_USD",
                    "side": "long",
                    "units": "1000.0000",
                    "entry_price": "1.09020000",
                    "entry_ts": "2026-01-15T14:30:00+00:00",
                    "exit_price": "1.09200000",
                    "exit_ts": "2026-01-15T16:59:00+00:00",
                    "pnl": "18.00000000",
                    "r_multiple": "2.0000",
                    "exit_reason": "take_profit",
                    "broker_order_id": "9100",
                    "client_order_id": "harbor-practice:7:2026-01-15T14:30:00Z",
                    "broker_trade_id": "7001",
                    "open_transaction_id": "9101",
                    "close_transaction_id": "9201",
                }
            ]
        }

    async def list_backtest_runs(self, *, limit: int) -> dict[str, Any]:
        self.calls.append(("backtests", limit))
        return {"runs": [{"run_id": 42, "status": "completed", "trade_count": 1}]}

    async def list_optimizer_studies(self, *, limit: int) -> dict[str, Any]:
        self.calls.append(("studies", limit))
        return {"studies": [{"study_id": 3, "status": "completed", "trial_count": 2}]}

    async def get_variant_detail(self, *, variant_id: int) -> dict[str, Any] | None:
        self.calls.append(("variant", variant_id))
        if variant_id == 404:
            return None
        return {
            "variant": {"id": variant_id, "label": "paper-trial-1", "status": "paper"},
            "trades": [],
            "equity_curve": [],
        }
