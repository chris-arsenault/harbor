from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from harbor_bot.backtester.data import candles_from_records, load_candle_fixture

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


def test_load_candle_fixture_parses_complete_utc_closed_candles() -> None:
    candles = load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")

    assert candles[0].instrument == "EUR_USD"
    assert candles[0].ts == datetime(2026, 1, 15, 1, 0, tzinfo=UTC)
    assert candles[0].o == Decimal("1.0950")
    assert candles[0].h == Decimal("1.1000")
    assert candles[0].low == Decimal("1.0900")
    assert candles[0].c == Decimal("1.0960")
    assert candles[0].complete is True
    assert len(candles) == 11


def test_loader_sorts_by_timestamp() -> None:
    candles = candles_from_records(
        [
            _record("2026-01-15T14:31:00+00:00"),
            _record("2026-01-15T14:30:00+00:00"),
        ],
        default_instrument="EUR_USD",
    )

    assert [candle.ts.minute for candle in candles] == [30, 31]


def test_loader_rejects_non_utc_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        candles_from_records([_record("2026-01-15T14:30:00")], default_instrument="EUR_USD")
    with pytest.raises(ValueError, match="UTC"):
        candles_from_records([_record("2026-01-15T14:30:00+01:00")], default_instrument="EUR_USD")


def test_loader_rejects_incomplete_candles() -> None:
    record = _record("2026-01-15T14:30:00+00:00")
    record["complete"] = False

    with pytest.raises(ValueError, match="complete candles only"):
        candles_from_records([record], default_instrument="EUR_USD")


def test_loader_rejects_duplicate_instrument_timestamp_rows() -> None:
    with pytest.raises(ValueError, match="duplicate candle"):
        candles_from_records(
            [
                _record("2026-01-15T14:30:00+00:00"),
                _record("2026-01-15T14:30:00+00:00"),
            ],
            default_instrument="EUR_USD",
        )


def test_recorded_fixtures_include_clean_signal_and_no_trade_days() -> None:
    clean_day = load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")
    no_trade_day = load_candle_fixture(FIXTURE_DIR / "no_trade_day.json")

    assert clean_day[0].ts.date().isoformat() == "2026-01-15"
    assert no_trade_day[0].ts.date().isoformat() == "2026-01-16"
    assert {candle.instrument for candle in clean_day + no_trade_day} == {"EUR_USD"}


def _record(ts: str) -> dict[str, object]:
    return {
        "ts": ts,
        "o": "1.1000",
        "h": "1.1010",
        "low": "1.0990",
        "c": "1.1005",
        "volume": 100,
        "complete": True,
    }
