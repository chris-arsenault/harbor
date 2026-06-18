from datetime import UTC, datetime

import pytest

from harbor_bot.config.models import ConfigUpdateRequest
from harbor_bot.config.service import ConfigService


def test_config_service_builds_snapshot_and_diff_from_known_config() -> None:
    service = ConfigService(
        engine=None,
        defaults={
            "risk_per_trade_pct": {"value": 0.5, "bounds": {"min": 0.1, "max": 1.0}},
            "instrument": {"value": "EUR_USD"},
        },
        clock=lambda: datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
    )

    snapshot = service.snapshot_from_values(
        [{"key": "risk_per_trade_pct", "value": {"value": 0.6}}]
    )
    result = service.preview_update(
        snapshot,
        ConfigUpdateRequest(
            updates={"risk_per_trade_pct": {"value": 0.7}},
            confirmation="APPLY_CONFIG",
        ),
    )

    assert snapshot.to_jsonable()["values"][0]["key"] == "instrument"
    assert snapshot.to_jsonable()["values"][1]["value"] == {
        "value": 0.6,
        "bounds": {"min": 0.1, "max": 1.0},
    }
    assert result.to_jsonable() == {
        "status": "preview",
        "updated_ts": "2026-01-15T14:30:00+00:00",
        "diff": [
            {
                "key": "risk_per_trade_pct",
                "before": {"value": 0.6, "bounds": {"min": 0.1, "max": 1.0}},
                "after": {"value": 0.7, "bounds": {"min": 0.1, "max": 1.0}},
            }
        ],
        "values": [
            {"key": "instrument", "value": {"value": "EUR_USD"}},
            {
                "key": "risk_per_trade_pct",
                "value": {"value": 0.7, "bounds": {"min": 0.1, "max": 1.0}},
            },
        ],
    }


def test_config_service_rejects_unconfirmed_unknown_or_out_of_bounds_updates() -> None:
    service = ConfigService(
        engine=None,
        defaults={"risk_per_trade_pct": {"value": 0.5, "bounds": {"min": 0.1, "max": 1.0}}},
    )
    snapshot = service.snapshot_from_values([])

    with pytest.raises(ValueError, match="confirmation"):
        service.preview_update(
            snapshot,
            ConfigUpdateRequest(
                updates={"risk_per_trade_pct": {"value": 0.7}},
                confirmation="",
            ),
        )
    with pytest.raises(ValueError, match="unknown config key"):
        service.preview_update(
            snapshot,
            ConfigUpdateRequest(updates={"unknown": {"value": 1}}, confirmation="APPLY_CONFIG"),
        )
    with pytest.raises(ValueError, match="outside configured bounds"):
        service.preview_update(
            snapshot,
            ConfigUpdateRequest(
                updates={"risk_per_trade_pct": {"value": 2.0}},
                confirmation="APPLY_CONFIG",
            ),
        )
