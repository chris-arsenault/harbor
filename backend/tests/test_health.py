import json
import logging

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.main import JsonLogFormatter


def test_health_reports_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_injected_readiness_checker() -> None:
    client = TestClient(create_app(readiness_checker=FakeReadinessChecker()))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"config": "ok", "database": "ok"},
    }


def test_json_log_formatter_redacts_secret_values() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="harbor",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="db=postgresql://harbor:super-secret@db:5432/harbor token=abc123",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "harbor"
    assert "super-secret" not in payload["message"]
    assert "abc123" not in payload["message"]
    assert "***" in payload["message"]


class FakeReadinessChecker:
    async def check(self) -> dict[str, object]:
        return {"status": "ready", "checks": {"config": "ok", "database": "ok"}}
