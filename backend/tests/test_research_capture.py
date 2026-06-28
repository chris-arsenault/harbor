from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.research.capture import _capture_trades, run_capture_scan
from harbor_bot.research.edge import EdgeEvent
from harbor_bot.strategy.models import (
    Bias,
    InstrumentRules,
    LevelName,
    strategy_config_from_defaults,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"


def test_capture_scan_reports_cost_aware_fixed_horizon_rows() -> None:
    rows = run_capture_scan(
        list(load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")),
        instrument="EUR_USD",
        config=strategy_config_from_defaults(load_default_config()),
        instrument_rules=_rules(),
        algorithm_ids=("generic_sweep_continuation",),
        horizons=(3,),
        spread_pips=Decimal("0.8"),
        slippage_pips=Decimal("0.1"),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.algorithm_id == "generic_sweep_continuation"
    assert row.hypothesis_id == "H007"
    assert row.horizon == 3
    assert row.event_count == 2
    assert row.stats.count == 1
    assert row.stats.average_mfe_pips >= 0
    assert row.stats.average_mae_pips >= 0


def test_capture_costs_reduce_net_pips_against_zero_cost_capture() -> None:
    candles = list(load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json"))
    kwargs = {
        "instrument": "EUR_USD",
        "config": strategy_config_from_defaults(load_default_config()),
        "instrument_rules": _rules(),
        "algorithm_ids": ("generic_sweep_continuation",),
        "horizons": (3,),
    }

    zero_cost = run_capture_scan(
        candles, **kwargs, spread_pips=Decimal("0"), slippage_pips=Decimal("0")
    )[0]
    with_cost = run_capture_scan(
        candles, **kwargs, spread_pips=Decimal("0.8"), slippage_pips=Decimal("0.1")
    )[0]

    assert with_cost.stats.mean_net_pips == zero_cost.stats.mean_net_pips - Decimal("1.0")


def test_long_capture_exact_math_uses_next_open_fixed_close_and_bid_ask_excursions() -> None:
    candles = (
        _test_candle(
            "2026-01-15T14:30:00+00:00", open_="1.1000", high="1.1000", low="1.1000", close="1.1000"
        ),
        _test_candle(
            "2026-01-15T14:31:00+00:00",
            open_="1.1000",
            high="1.1030",
            low="1.0990",
            close="1.1010",
            bid_h="1.1025",
            bid_l="1.0985",
        ),
        _test_candle(
            "2026-01-15T14:32:00+00:00", open_="1.1010", high="1.1025", low="1.0995", close="1.1020"
        ),
    )
    trades = _capture_trades(
        candles,
        events=[_event(Bias.BULLISH)],
        horizon=2,
        rules=_rules(),
        spread_pips=Decimal("0"),
        slippage_pips=Decimal("0"),
    )

    assert trades[0].gross_pips == Decimal("20")
    assert trades[0].net_pips == Decimal("20")
    assert trades[0].mfe_pips == Decimal("25")
    assert trades[0].mae_pips == Decimal("15")


def test_short_capture_exact_math_and_cost_formula() -> None:
    candles = (
        _test_candle(
            "2026-01-15T14:30:00+00:00", open_="1.1000", high="1.1000", low="1.1000", close="1.1000"
        ),
        _test_candle(
            "2026-01-15T14:31:00+00:00",
            open_="1.1000",
            high="1.1010",
            low="1.0970",
            close="1.0990",
            ask_h="1.1015",
            ask_l="1.0975",
        ),
        _test_candle(
            "2026-01-15T14:32:00+00:00", open_="1.0990", high="1.1010", low="1.0980", close="1.0980"
        ),
    )
    trades = _capture_trades(
        candles,
        events=[_event(Bias.BEARISH)],
        horizon=2,
        rules=_rules(),
        spread_pips=Decimal("1.2"),
        slippage_pips=Decimal("0.3"),
    )

    assert trades[0].gross_pips == Decimal("20")
    assert trades[0].net_pips == Decimal("18.2")
    assert trades[0].mfe_pips == Decimal("24.1")
    assert trades[0].mae_pips == Decimal("15.9")


def test_capture_skips_missing_forward_timestamp_and_rejects_nonpositive_horizon() -> None:
    candles = (
        _test_candle(
            "2026-01-15T14:30:00+00:00", open_="1.1000", high="1.1000", low="1.1000", close="1.1000"
        ),
        _test_candle(
            "2026-01-15T14:31:00+00:00", open_="1.1000", high="1.1000", low="1.1000", close="1.1000"
        ),
        _test_candle(
            "2026-01-15T15:00:00+00:00", open_="1.1500", high="1.1500", low="1.1500", close="1.1500"
        ),
    )

    assert (
        _capture_trades(
            candles,
            events=[_event(Bias.BULLISH)],
            horizon=2,
            rules=_rules(),
            spread_pips=Decimal("0"),
            slippage_pips=Decimal("0"),
        )
        == []
    )

    try:
        run_capture_scan(
            list(candles),
            instrument="EUR_USD",
            config=strategy_config_from_defaults(load_default_config()),
            instrument_rules=_rules(),
            algorithm_ids=("generic_sweep_continuation",),
            horizons=(0,),
        )
    except ValueError as exc:
        assert "horizons must be positive" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("zero horizon was accepted")


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )


def _event(bias: Bias) -> EdgeEvent:
    return EdgeEvent(
        index=0,
        trading_date=date(2026, 1, 15),
        level_name=LevelName.ASIA_LOW,
        bias=bias,
        atr_pips=Decimal("1"),
        pip_size=Decimal("0.0001"),
    )


def _test_candle(
    ts: str,
    *,
    open_: str,
    high: str,
    low: str,
    close: str,
    bid_h: str | None = None,
    bid_l: str | None = None,
    ask_h: str | None = None,
    ask_l: str | None = None,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal(open_),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=1,
        bid_h=None if bid_h is None else Decimal(bid_h),
        bid_low=None if bid_l is None else Decimal(bid_l),
        ask_h=None if ask_h is None else Decimal(ask_h),
        ask_low=None if ask_l is None else Decimal(ask_l),
    )
