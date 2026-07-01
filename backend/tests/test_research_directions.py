from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import exp

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.directions import run_direction_scan


def test_direction_scan_surfaces_data_gates_and_available_probes() -> None:
    data = _fx_fixture()

    rows = run_direction_scan(data, book_coverage=[])
    by_h = {row.hypothesis_id: row for row in rows}

    assert by_h["H108"].status == "data_required"
    assert "crypto/index data" in by_h["H108"].details
    assert any(row.hypothesis_id == "H109" for row in rows)
    assert any(row.hypothesis_id == "H110" for row in rows)
    assert any(row.hypothesis_id == "H112" for row in rows)
    assert by_h["H111"].status == "collecting"


def test_book_readiness_marks_paired_snapshot_coverage_ready() -> None:
    rows = run_direction_scan(
        {},
        algorithm_ids=("book_conditioner_readiness",),
        book_coverage=[
            {"instrument": "EUR_USD", "book_type": "order", "snapshot_count": 600},
            {"instrument": "EUR_USD", "book_type": "position", "snapshot_count": 550},
        ],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.hypothesis_id == "H111"
    assert row.status == "ready"
    assert row.stats.effect == 550


def test_weekend_gap_uses_available_risk_proxy() -> None:
    data = _fx_fixture()
    data["BTC_USD"] = _weekend_proxy()

    rows = run_direction_scan(data, algorithm_ids=("weekend_risk_gap_probe",))

    assert rows
    assert {row.hypothesis_id for row in rows} == {"H108"}
    assert all("Proxy=BTC_USD" in row.details for row in rows)


def _fx_fixture() -> dict[str, list[ClosedCandle]]:
    instruments = {
        "EUR_USD": (1.10, 0.0008),
        "GBP_USD": (1.30, 0.0005),
        "AUD_USD": (0.70, -0.0002),
        "USD_JPY": (140.0, 0.0100),
        "EUR_GBP": (0.85, -0.0001),
    }
    return {
        instrument: [_candle(instrument, day, base * exp(slope * day)) for day in range(130)]
        for instrument, (base, slope) in instruments.items()
    }


def _weekend_proxy() -> list[ClosedCandle]:
    rows = []
    for day in range(130):
        # Add a deterministic Sunday bump so there are weekend proxy returns.
        weekend_bump = 0.015 if day % 7 == 6 else 0.0
        rows.append(_candle("BTC_USD", day, 50_000 * exp(0.001 * day + weekend_bump)))
    return rows


def _candle(instrument: str, day: int, close: float) -> ClosedCandle:
    ts = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day)
    value = Decimal(str(round(close, 8)))
    return ClosedCandle(
        instrument=instrument,
        ts=ts,
        o=value,
        h=value,
        low=value,
        c=value,
        volume=100,
    )
