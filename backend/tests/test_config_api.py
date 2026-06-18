from datetime import UTC, datetime

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.config.models import (
    ConfigSnapshot,
    ConfigUpdateRequest,
    ConfigUpdateResult,
)


def test_config_routes_read_update_and_audit_through_injected_service() -> None:
    service = FakeConfigService()
    client = TestClient(create_app(config_service=service))

    snapshot = client.get("/api/config")
    updated = client.put(
        "/api/config",
        json={
            "updates": {"risk_per_trade_pct": {"value": 0.7}},
            "confirmation": "APPLY_CONFIG",
        },
    )

    assert snapshot.status_code == 200
    assert snapshot.json()["values"][0]["key"] == "risk_per_trade_pct"
    assert updated.status_code == 200
    assert updated.json()["status"] == "updated"
    assert updated.json()["diff"][0]["key"] == "risk_per_trade_pct"
    assert service.requests == [
        ConfigUpdateRequest(
            updates={"risk_per_trade_pct": {"value": 0.7}},
            confirmation="APPLY_CONFIG",
        )
    ]


def test_config_update_rejects_bad_payloads() -> None:
    client = TestClient(create_app(config_service=FakeConfigService()))

    response = client.put("/api/config", json={"updates": {}})

    assert response.status_code == 400
    assert response.json() == {"detail": "updates and confirmation are required"}


class FakeConfigService:
    def __init__(self) -> None:
        self.requests: list[ConfigUpdateRequest] = []

    async def get_snapshot(self) -> ConfigSnapshot:
        return ConfigSnapshot(
            values=(
                {
                    "key": "risk_per_trade_pct",
                    "value": {"value": 0.5, "bounds": {"min": 0.1, "max": 1.0}},
                },
            )
        )

    async def update_config(self, request: ConfigUpdateRequest) -> ConfigUpdateResult:
        self.requests.append(request)
        return ConfigUpdateResult(
            status="updated",
            updated_ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
            values=(
                {
                    "key": "risk_per_trade_pct",
                    "value": {"value": 0.7, "bounds": {"min": 0.1, "max": 1.0}},
                },
            ),
            diff=(
                {
                    "key": "risk_per_trade_pct",
                    "before": {"value": 0.5, "bounds": {"min": 0.1, "max": 1.0}},
                    "after": {"value": 0.7, "bounds": {"min": 0.1, "max": 1.0}},
                },
            ),
        )
