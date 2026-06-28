from datetime import UTC, datetime, timedelta
from decimal import Decimal

from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.triangular_capture import _capture_returns, run_triangular_capture


def test_triangular_capture_reports_direct_and_synthetic_rows() -> None:
    rows = run_triangular_capture(
        _triangle_fixture(),
        thresholds=(1.0, 1.5),
        horizons=(1, 3),
        cost_bps_per_leg=0.5,
    )

    assert {row.construction for row in rows} == {"direct_eur_gbp", "synthetic_triangle"}
    assert {row.threshold for row in rows} == {1.0, 1.5}
    assert {row.horizon for row in rows} == {1, 3}
    assert all(row.hypothesis_id == "H101" for row in rows)


def test_triangular_capture_costs_reduce_net_vs_gross_by_leg_count() -> None:
    rows = run_triangular_capture(
        _triangle_fixture(),
        thresholds=(1.0,),
        horizons=(1,),
        cost_bps_per_leg=0.5,
    )
    direct = next(row for row in rows if row.construction == "direct_eur_gbp")
    synthetic = next(row for row in rows if row.construction == "synthetic_triangle")

    assert direct.stats.count > 0
    assert direct.stats.mean_net_bps == direct.stats.mean_gross_bps - 0.5
    assert synthetic.stats.mean_net_bps == synthetic.stats.mean_gross_bps - 1.5


def test_triangular_capture_rejects_invalid_parameters() -> None:
    kwargs = {"candles_by_instrument": _triangle_fixture()}
    cases = [
        {"horizons": (0,)},
        {"horizons": (-1,)},
        {"thresholds": (0.0,)},
        {"thresholds": (-1.0,)},
        {"lookback": 1},
        {"cost_bps_per_leg": -0.1},
    ]

    for params in cases:
        try:
            run_triangular_capture(**kwargs, **params)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"invalid params accepted: {params}")


def test_triangular_capture_missing_required_instrument_returns_empty() -> None:
    fixture = _triangle_fixture()
    fixture.pop("EUR_GBP")

    assert run_triangular_capture(fixture) == []


def test_triangular_direct_positive_residual_convergence_is_positive() -> None:
    returns = _capture_returns(
        days=list(range(5)),
        eur_gbp_log=[0.0, 0.001, -0.001, 0.002, 0.0005],
        residual=[0.0, 0.001, -0.001, 0.002, 0.0005],
        construction="direct_eur_gbp",
        threshold=2.0,
        horizon=1,
        lookback=3,
    )

    assert returns == [15.0]


def test_triangular_direct_residual_widening_is_negative() -> None:
    returns = _capture_returns(
        days=list(range(5)),
        eur_gbp_log=[0.0, 0.001, -0.001, 0.002, 0.003],
        residual=[0.0, 0.001, -0.001, 0.002, 0.003],
        construction="direct_eur_gbp",
        threshold=2.0,
        horizon=1,
        lookback=3,
    )

    assert returns == [-10.0]


def test_triangular_threshold_equality_is_included() -> None:
    kwargs = {
        "days": list(range(5)),
        "eur_gbp_log": [0.0, 0.001, -0.001, 0.002, 0.0005],
        "residual": [0.0, 0.001, -0.001, 0.002, 0.0005],
        "construction": "direct_eur_gbp",
        "horizon": 1,
        "lookback": 3,
    }

    assert _capture_returns(**kwargs, threshold=2.0) == [15.0]
    assert _capture_returns(**kwargs, threshold=2.0001) == []


def _triangle_fixture(*, converges: bool = True) -> dict[str, list[ClosedCandle]]:
    data = {"EUR_USD": [], "GBP_USD": [], "EUR_GBP": []}
    for day in range(100):
        eur_usd = 1.10 + day * 0.0001
        gbp_usd = 1.30 + day * 0.00005
        implied = eur_usd / gbp_usd
        residual = 0.0
        if day in (70, 80):
            residual = 0.02
        if day in (71, 81):
            residual = 0.005 if converges else 0.03
        data["EUR_USD"].append(_candle("EUR_USD", day, eur_usd))
        data["GBP_USD"].append(_candle("GBP_USD", day, gbp_usd))
        data["EUR_GBP"].append(_candle("EUR_GBP", day, implied + residual))
    return data


def _candle(instrument: str, day: int, price: float) -> ClosedCandle:
    ts = datetime(2026, 1, 1, 23, tzinfo=UTC) + timedelta(days=day)
    value = Decimal(f"{price:.6f}")
    return ClosedCandle(
        instrument=instrument,
        ts=ts,
        o=value,
        h=value,
        low=value,
        c=value,
        volume=1,
    )
