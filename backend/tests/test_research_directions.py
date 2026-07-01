from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import exp

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.directions import SweepProbeEvent, run_direction_scan
from harbor_bot.strategy.models import Bias


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


def test_range_forecast_uses_daily_high_low_and_correlation_t_stat() -> None:
    candles = []
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for day in range(40):
        ts = base + timedelta(days=day)
        # Constant close, varying high/low range. Close-to-close absolute return would be zero.
        width = Decimal("0.001") + Decimal(day % 5) * Decimal("0.0002")
        candles.append(
            ClosedCandle(
                instrument="EUR_USD",
                ts=ts,
                o=Decimal("1.0000"),
                h=Decimal("1.0000") + width,
                low=Decimal("1.0000") - width,
                c=Decimal("1.0000"),
                volume=100,
            )
        )

    rows = run_direction_scan(
        {"EUR_USD": candles},
        algorithm_ids=("range_forecast_probe",),
    )

    assert rows[0].hypothesis_id == "H110"
    assert rows[0].metric == "corr(prev_daily_range,next_daily_range)"
    assert rows[0].stats.count == 39
    assert rows[0].stats.t_stat != 0
    assert "top-tercile range hit-rate" in rows[0].details


def test_book_conditioned_sweep_interaction_scores_trapped_crowd() -> None:
    base = datetime(2024, 1, 1, 14, 0, tzinfo=UTC)
    candles = [
        _minute_candle("EUR_USD", base, "1.0000"),
        _minute_candle("EUR_USD", base + timedelta(minutes=60), "1.0010"),
    ]
    events = [
        SweepProbeEvent(
            instrument="EUR_USD",
            index=0,
            ts=base,
            bias=Bias.BULLISH,
            pip_size=Decimal("0.0001"),
        )
    ]
    rows = run_direction_scan(
        {"EUR_USD": candles},
        algorithm_ids=("book_conditioner_readiness",),
        book_coverage=[
            {"instrument": "EUR_USD", "book_type": "order", "snapshot_count": 600},
            {"instrument": "EUR_USD", "book_type": "position", "snapshot_count": 600},
        ],
        book_snapshots=[
            {
                "book_type": "position",
                "instrument": "EUR_USD",
                "snapshot_time": base - timedelta(minutes=5),
                "buckets_json": [{"long_pct": "0.20", "short_pct": "0.40"}],
            }
        ],
        sweep_events_by_instrument={"EUR_USD": events},
    )

    interaction = next(row for row in rows if row.metric == "trapped_crowd_sweep_60m_reversal")
    assert interaction.stats.count == 1
    assert interaction.stats.effect == 10
    assert interaction.stats.secondary == 10


def _minute_candle(instrument: str, ts: datetime, close: str) -> ClosedCandle:
    value = Decimal(close)
    return ClosedCandle(
        instrument=instrument,
        ts=ts,
        o=value,
        h=value,
        low=value,
        c=value,
        volume=100,
    )
