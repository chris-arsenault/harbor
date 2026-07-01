from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import exp

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.cross_instrument import (
    available_cross_algorithms,
    daily_closes,
    default_cross_algorithm_ids,
    run_cross_scan,
)


def test_daily_closes_uses_last_candle_per_utc_day() -> None:
    candles = [
        _candle("EUR_USD", 0, "1.1000", hour=1),
        _candle("EUR_USD", 0, "1.1200", hour=23),
        _candle("EUR_USD", 1, "1.1300", hour=1),
    ]

    closes = daily_closes(candles)

    assert [close.close for close in closes] == [1.12, 1.13]


def test_cross_scan_runs_factor_and_residual_algorithms() -> None:
    candles = _cross_fixture()

    rows = run_cross_scan(
        candles,
        algorithm_ids=(
            "cs_momentum_20d_5d",
            "cs_value_60d_5d",
            "tri_eur_gbp_residual_5d",
            "usd_dispersion_reversion_5d",
        ),
    )

    assert {row.algorithm_id for row in rows} == {
        "cs_momentum_20d_5d",
        "cs_value_60d_5d",
        "tri_eur_gbp_residual_5d",
        "usd_dispersion_reversion_5d",
    }
    assert all(row.observation_count >= 0 for row in rows)
    triangle = next(row for row in rows if row.algorithm_id == "tri_eur_gbp_residual_5d")
    assert triangle.stats.count > 0


def test_default_cross_scan_has_no_active_archived_cross_hypotheses() -> None:
    default_ids = set(default_cross_algorithm_ids())
    algorithms = {algorithm.algorithm_id: algorithm for algorithm in available_cross_algorithms()}

    assert default_ids == set()
    assert algorithms["tri_eur_gbp_residual_5d"].lifecycle == "archived"
    assert algorithms["cs_momentum_20d_5d"].lifecycle == "archived"
    assert algorithms["cs_value_60d_5d"].lifecycle == "archived"
    assert algorithms["usd_dispersion_reversion_5d"].lifecycle == "archived"


def test_cross_momentum_detects_persistent_relative_strength() -> None:
    rows = run_cross_scan(
        _cross_fixture(),
        algorithm_ids=("cs_momentum_20d_5d",),
    )

    row = rows[0]
    assert row.stats.count > 0
    assert row.stats.mean_return_bps > 0


def test_triangular_cross_missing_required_instrument_returns_zero_observations() -> None:
    rows = run_cross_scan(
        {"GBP_USD": _flat("GBP_USD"), "EUR_GBP": _flat("EUR_GBP")},
        algorithm_ids=("tri_eur_gbp_residual_5d",),
    )

    assert rows[0].stats.count == 0


def test_usd_dispersion_normalizes_broad_usd_move_to_no_residual_observations() -> None:
    rows = run_cross_scan(
        {
            "EUR_USD": _pct_trend("EUR_USD", 1.2, -0.001),
            "GBP_USD": _pct_trend("GBP_USD", 1.4, -0.001),
            "AUD_USD": _pct_trend("AUD_USD", 0.8, -0.001),
            "USD_JPY": _pct_trend("USD_JPY", 120.0, 0.001),
        },
        algorithm_ids=("usd_dispersion_reversion_5d",),
    )

    assert rows[0].stats.count == 0


def test_usd_dispersion_ranks_by_residual_not_instrument_name() -> None:
    data = {
        "AAA_USD": _two_phase("AAA_USD", start=1.0, recent_return=0.10, forward_return=-0.01),
        "BBB_USD": _two_phase("BBB_USD", start=1.0, recent_return=0.02, forward_return=0.00),
        "USD_CCC": _two_phase("USD_CCC", start=1.0, recent_return=-0.02, forward_return=0.00),
        "USD_ZZZ": _two_phase("USD_ZZZ", start=1.0, recent_return=0.10, forward_return=-0.01),
    }

    rows = run_cross_scan(data, algorithm_ids=("usd_dispersion_reversion_5d",))

    assert rows[0].stats.count > 0
    assert rows[0].stats.mean_return_bps > 0


def test_cross_research_rejects_incomplete_candles() -> None:
    candles = _flat("EUR_USD")
    candles[0] = _candle("EUR_USD", 0, "1.00000", complete=False)

    try:
        daily_closes(candles)
    except ValueError as exc:
        assert "closed candles only" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("incomplete candle was accepted")


def _cross_fixture() -> dict[str, list[ClosedCandle]]:
    days = 100
    data = {
        "EUR_USD": [],
        "GBP_USD": [],
        "AUD_USD": [],
        "USD_JPY": [],
        "EUR_GBP": [],
    }
    for day in range(days):
        data["EUR_USD"].append(_candle("EUR_USD", day, _price(1.10, 0.0008, day)))
        data["GBP_USD"].append(_candle("GBP_USD", day, _price(1.30, 0.0004, day)))
        data["AUD_USD"].append(_candle("AUD_USD", day, _price(0.70, -0.0002, day)))
        data["USD_JPY"].append(_candle("USD_JPY", day, _price(140.0, -0.02, day)))
        implied = float(data["EUR_USD"][-1].c) / float(data["GBP_USD"][-1].c)
        residual = 0.0
        if day == 70:
            residual = 0.02
        if 71 <= day <= 75:
            residual = 0.02 * (75 - day) / 5
        data["EUR_GBP"].append(_candle("EUR_GBP", day, f"{implied + residual:.5f}"))
    return data


def _flat(instrument: str, *, days: int = 100, price: str = "1.00000") -> list[ClosedCandle]:
    return [_candle(instrument, day, price) for day in range(days)]


def _trend(instrument: str, start: float, step: float, *, days: int = 100) -> list[ClosedCandle]:
    return [_candle(instrument, day, f"{start + step * day:.5f}") for day in range(days)]


def _pct_trend(instrument: str, start: float, daily_log_return: float, *, days: int = 100):
    return [
        _candle(instrument, day, f"{start * exp(daily_log_return * day):.10f}")
        for day in range(days)
    ]


def _two_phase(
    instrument: str,
    *,
    start: float,
    recent_return: float,
    forward_return: float,
    days: int = 80,
) -> list[ClosedCandle]:
    candles: list[ClosedCandle] = []
    for day in range(days):
        price = start
        if day >= 5:
            price *= 1 + recent_return
        if day >= 10:
            price *= 1 + forward_return
        candles.append(_candle(instrument, day, f"{price:.5f}"))
    return candles


def _price(start: float, step: float, day: int) -> str:
    return f"{start + step * day:.5f}"


def _candle(
    instrument: str, day: int, close: str, *, hour: int = 23, complete: bool = True
) -> ClosedCandle:
    ts = datetime(2026, 1, 1, hour, tzinfo=UTC) + timedelta(days=day)
    price = Decimal(close)
    return ClosedCandle(
        instrument=instrument,
        ts=ts,
        o=price,
        h=price,
        low=price,
        c=price,
        volume=1,
        complete=complete,
    )
