from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from math import exp
from zoneinfo import ZoneInfo

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


def test_weekend_gap_reports_gap_and_drift_legs_separately() -> None:
    data = _fx_fixture()
    data["BTC_USD"] = _weekend_proxy()

    rows = run_direction_scan(data, algorithm_ids=("weekend_risk_gap_probe",))

    metrics = {row.metric for row in rows}
    assert "corr(weekend_proxy,reopen_gap)" in metrics
    assert "corr(weekend_proxy,post_reopen_drift)" in metrics
    drift = next(row for row in rows if row.metric == "corr(weekend_proxy,post_reopen_drift)")
    assert "tradable underreaction" in drift.details


def test_lead_lag_statuses_come_from_family_fdr_q_values() -> None:
    rows = run_direction_scan(_fx_fixture(), algorithm_ids=("lead_lag_network_probe",))

    assert rows
    assert all(row.hypothesis_id == "H112" for row in rows)
    assert all("BH-FDR q-value" in row.details for row in rows)
    # secondary carries the q-value; the deterministic fixture has no real
    # lead/lag structure, so nothing may pass the FDR gate.
    assert all(0.0 <= row.stats.secondary <= 1.0 for row in rows)
    assert all(row.status == "weak" for row in rows)


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


def test_range_forecast_uses_har_out_of_sample_forecast() -> None:
    candles = []
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for day in range(120):
        ts = base + timedelta(days=day)
        # Constant close, persistently trending high/low range: a HAR model must
        # track it out-of-sample. Close-to-close absolute return would be zero.
        width = Decimal("0.001") + Decimal(day) * Decimal("0.00001")
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
    assert rows[0].metric == "har_oos_corr(next_daily_range)"
    assert rows[0].stats.count > 30
    assert rows[0].stats.effect > 0.5  # expanding OOS forecast tracks the trend
    assert "HAR" in rows[0].details


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


def test_sweep_divergence_splits_confirmed_and_divergent_events() -> None:
    base = datetime(2024, 1, 2, 14, 0, tzinfo=UTC)
    candles = {
        "EUR_USD": [
            _minute_candle("EUR_USD", base, "1.0000"),
            _minute_candle("EUR_USD", base + timedelta(minutes=60), "1.0010"),
            _minute_candle("EUR_USD", base + timedelta(hours=5), "1.0000"),
            _minute_candle("EUR_USD", base + timedelta(hours=6), "1.0020"),
        ],
        "GBP_USD": [_minute_candle("GBP_USD", base, "1.3000")],
    }
    events = {
        "EUR_USD": [
            # Confirmed: GBP_USD (shared USD leg) sweeps at the same minute.
            SweepProbeEvent(
                instrument="EUR_USD",
                index=0,
                ts=base,
                bias=Bias.BULLISH,
                pip_size=Decimal("0.0001"),
            ),
            # Divergent: no sibling sweep within the window.
            SweepProbeEvent(
                instrument="EUR_USD",
                index=2,
                ts=base + timedelta(hours=5),
                bias=Bias.BULLISH,
                pip_size=Decimal("0.0001"),
            ),
        ],
        "GBP_USD": [
            SweepProbeEvent(
                instrument="GBP_USD",
                index=0,
                ts=base,
                bias=Bias.BULLISH,
                pip_size=Decimal("0.0001"),
            )
        ],
    }

    rows = run_direction_scan(
        candles,
        algorithm_ids=("sweep_divergence_probe",),
        sweep_events_by_instrument=events,
    )

    divergent = next(
        row
        for row in rows
        if row.metric == "divergent_sweep_60m_reversal" and row.subject == "EUR_USD"
    )
    confirmed = next(
        row
        for row in rows
        if row.metric == "confirmed_sweep_60m_continuation" and row.subject == "EUR_USD"
    )
    assert divergent.stats.count == 1
    assert divergent.stats.effect == 20  # 1.0000 → 1.0020 reversal-scored
    assert confirmed.stats.count == 1
    assert confirmed.stats.effect == -10  # +10 pip reversal scored as continuation


def test_month_end_fix_probe_scores_post_fix_retracement() -> None:
    london = ZoneInfo("Europe/London")
    # 2024-01-31 (Wednesday) is January's last business day; 2024-01-30 is not.
    fixture = {
        date(2024, 1, 30): ("1.1000", "1.1010", "1.1005"),
        date(2024, 1, 31): ("1.1000", "1.1020", "1.1005"),
    }
    candles = [
        _minute_candle(
            "EUR_USD",
            datetime.combine(day, time(hour, minute), tzinfo=london).astimezone(UTC),
            price,
        )
        for day, prices in fixture.items()
        for (hour, minute), price in zip(((15, 40), (16, 0), (16, 30)), prices, strict=True)
    ]

    rows = run_direction_scan({"EUR_USD": candles}, algorithm_ids=("month_end_fix_probe",))

    month_end = next(row for row in rows if row.subject == "EUR_USD month-end")
    normal = next(row for row in rows if row.subject == "EUR_USD normal")
    assert month_end.hypothesis_id == "H106"
    assert month_end.stats.count == 1
    assert month_end.stats.effect > 0  # drift up into the fix, retracement after
    assert normal.stats.count == 1


def test_underwater_long_fade_row_conditions_on_bucket_prices() -> None:
    base = datetime(2024, 1, 1, 14, 0, tzinfo=UTC)
    candles = [
        _minute_candle("EUR_USD", base, "1.0000"),
        _minute_candle("EUR_USD", base + timedelta(minutes=60), "0.9990"),
    ]
    events = [
        SweepProbeEvent(
            instrument="EUR_USD",
            index=0,
            ts=base,
            bias=Bias.BEARISH,
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
                # 75% of long mass sits above 1.0000: trapped underwater longs.
                "buckets_json": [
                    {"price": "1.0050", "long_pct": "0.30", "short_pct": "0.10"},
                    {"price": "0.9950", "long_pct": "0.10", "short_pct": "0.20"},
                ],
            }
        ],
        sweep_events_by_instrument={"EUR_USD": events},
    )

    underwater = next(row for row in rows if row.metric == "underwater_long_fade_60m_reversal")
    assert underwater.stats.count == 1
    assert underwater.stats.effect == 10  # bearish sweep, price fell 10 pips


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
