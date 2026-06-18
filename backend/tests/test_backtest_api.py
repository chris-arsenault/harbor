from typing import Any

from fastapi.testclient import TestClient

from harbor_bot.api import create_app


class FakeBacktestService:
    def __init__(self) -> None:
        self.started_payloads: list[dict[str, Any]] = []
        self.results = {
            42: {
                "run_id": 42,
                "status": "completed",
                "stats": {"trade_count": 1},
                "trades": [{"side": "long"}],
            }
        }

    async def start_backtest(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.started_payloads.append(payload)
        return self.results[42]

    async def get_backtest(self, run_id: int) -> dict[str, Any] | None:
        return self.results.get(run_id)


def test_post_backtests_starts_backtest_through_injected_service() -> None:
    service = FakeBacktestService()
    client = TestClient(create_app(backtest_service=service))

    response = client.post("/api/backtests", json={"instrument": "EUR_USD", "candles": []})

    assert response.status_code == 200
    assert response.json() == service.results[42]
    assert service.started_payloads == [{"instrument": "EUR_USD", "candles": []}]


def test_get_backtest_reads_result_through_injected_service() -> None:
    client = TestClient(create_app(backtest_service=FakeBacktestService()))

    response = client.get("/api/backtests/42")

    assert response.status_code == 200
    assert response.json()["run_id"] == 42
    assert response.json()["trades"] == [{"side": "long"}]


def test_get_backtest_returns_404_for_unknown_run() -> None:
    client = TestClient(create_app(backtest_service=FakeBacktestService()))

    response = client.get("/api/backtests/404")

    assert response.status_code == 404
    assert response.json() == {"detail": "backtest not found"}
