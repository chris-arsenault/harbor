from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from harbor_bot.backtester.models import FillPolicy
from harbor_bot.paper_engine.config import load_paper_engine_config
from harbor_bot.paper_engine.models import (
    LabStudySnapshot,
    PaperEngineConfig,
    PaperVariant,
    VariantEquityPoint,
    VariantLeaderboardRow,
    VariantStats,
    VariantTrade,
)


def test_paper_engine_defaults_are_configured_and_jsonable() -> None:
    config = load_paper_engine_config()

    assert config.initial_nav == Decimal("10000")
    assert config.spread_pips == Decimal("0.8")
    assert config.slippage_pips == Decimal("0.1")
    assert config.commission_per_unit == Decimal("0")
    assert config.ambiguous_fill_policy == FillPolicy.PESSIMISTIC
    assert config.live_forward_drawdown_floor == Decimal("1")
    assert config.leaderboard_min_trades == 0
    assert config.max_lab_rows == 200
    assert config.to_jsonable() == {
        "initial_nav": "10000",
        "spread_pips": "0.8",
        "slippage_pips": "0.1",
        "commission_per_unit": "0",
        "ambiguous_fill_policy": "pessimistic",
        "force_ny_close": True,
        "live_forward_drawdown_floor": "1",
        "leaderboard_min_trades": 0,
        "max_lab_rows": 200,
    }


def test_paper_engine_config_rejects_invalid_runtime_assumptions() -> None:
    with pytest.raises(ValueError, match="initial_nav"):
        PaperEngineConfig(initial_nav=Decimal("0"))
    with pytest.raises(ValueError, match="spread_pips"):
        PaperEngineConfig(spread_pips=Decimal("-0.1"))
    with pytest.raises(ValueError, match="slippage_pips"):
        PaperEngineConfig(slippage_pips=Decimal("-0.1"))
    with pytest.raises(ValueError, match="commission_per_unit"):
        PaperEngineConfig(commission_per_unit=Decimal("-0.1"))
    with pytest.raises(ValueError, match="drawdown"):
        PaperEngineConfig(live_forward_drawdown_floor=Decimal("0"))
    with pytest.raises(ValueError, match="leaderboard_min_trades"):
        PaperEngineConfig(leaderboard_min_trades=-1)
    with pytest.raises(ValueError, match="max_lab_rows"):
        PaperEngineConfig(max_lab_rows=0)


def test_paper_variant_is_immutable_paper_contract_with_json_safe_params() -> None:
    created_ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    variant = PaperVariant(
        id=7,
        label="study-1-trial-2",
        params={"rr_floor": Decimal("2.5")},
        source_trial_id=2,
        status="paper",
        created_ts=created_ts,
        trial_scores={
            "in_sample_score": Decimal("1.1"),
            "out_of_sample_score": Decimal("0.9"),
            "robustness_score": Decimal("0.8"),
        },
    )

    assert variant.params == {"rr_floor": Decimal("2.5")}
    assert variant.to_jsonable() == {
        "id": 7,
        "label": "study-1-trial-2",
        "params": {"rr_floor": "2.5"},
        "source_trial_id": 2,
        "status": "paper",
        "created_ts": "2026-01-15T14:30:00+00:00",
        "trial_scores": {
            "in_sample_score": "1.1",
            "out_of_sample_score": "0.9",
            "robustness_score": "0.8",
        },
    }
    with pytest.raises(FrozenInstanceError):
        variant.label = "mutated"
    with pytest.raises(ValueError, match="paper"):
        PaperVariant(id=8, label="retired", params={}, source_trial_id=2, status="retired")


def test_variant_trade_equity_stats_leaderboard_and_snapshot_are_jsonable() -> None:
    entry_ts = datetime(2026, 1, 15, 14, 36, tzinfo=UTC)
    exit_ts = datetime(2026, 1, 15, 14, 42, tzinfo=UTC)
    trade = VariantTrade(
        variant_id=7,
        side="long",
        units=Decimal("10000"),
        entry_price=Decimal("1.1010"),
        entry_ts=entry_ts,
        exit_price=Decimal("1.1070"),
        exit_ts=exit_ts,
        pnl=Decimal("60"),
        r_multiple=Decimal("2"),
        exit_reason="take_profit",
        id=11,
    )
    equity = VariantEquityPoint(
        variant_id=7,
        ts=exit_ts,
        nav=Decimal("10060"),
        drawdown=Decimal("0"),
    )
    stats = VariantStats(
        variant_id=7,
        trade_count=1,
        win_rate=Decimal("1"),
        net_pnl=Decimal("60"),
        expectancy=Decimal("60"),
        average_r=Decimal("2"),
        max_drawdown=Decimal("0"),
        ending_nav=Decimal("10060"),
        live_forward_score=Decimal("60"),
    )
    row = VariantLeaderboardRow(
        rank=1,
        variant=PaperVariant(id=7, label="study-1-trial-2", params={}, source_trial_id=2),
        stats=stats,
        out_of_sample_score=Decimal("0.9"),
        robustness_score=Decimal("0.8"),
    )
    snapshot = LabStudySnapshot(
        study_id=1,
        status="completed",
        trial_count=4,
        total_trial_count=96,
        candidate_count=1,
        paper_variant_count=1,
        created_ts=datetime(2026, 1, 15, 13, 0, tzinfo=UTC),
    )

    assert trade.to_persistence_row() == {
        "variant_id": 7,
        "side": "long",
        "units": Decimal("10000"),
        "entry_price": Decimal("1.1010"),
        "entry_ts": entry_ts,
        "exit_price": Decimal("1.1070"),
        "exit_ts": exit_ts,
        "pnl": Decimal("60"),
        "r_multiple": Decimal("2"),
        "exit_reason": "take_profit",
    }
    assert trade.to_jsonable()["exit_ts"] == "2026-01-15T14:42:00+00:00"
    assert equity.to_jsonable()["nav"] == "10060"
    assert stats.to_jsonable()["live_forward_score"] == "60"
    assert row.to_jsonable()["variant"]["id"] == 7
    assert snapshot.to_jsonable() == {
        "study_id": 1,
        "status": "completed",
        "trial_count": 4,
        "candidate_count": 1,
        "paper_variant_count": 1,
        "created_ts": "2026-01-15T13:00:00+00:00",
    }


def test_variant_trade_rejects_invalid_closed_trade_shape() -> None:
    with pytest.raises(ValueError, match="side"):
        VariantTrade(
            variant_id=7,
            side="flat",
            units=Decimal("10000"),
            entry_price=Decimal("1.1010"),
            entry_ts=datetime(2026, 1, 15, 14, 36, tzinfo=UTC),
            exit_price=Decimal("1.1070"),
            exit_ts=datetime(2026, 1, 15, 14, 42, tzinfo=UTC),
            pnl=Decimal("60"),
            r_multiple=Decimal("2"),
            exit_reason="take_profit",
        )
