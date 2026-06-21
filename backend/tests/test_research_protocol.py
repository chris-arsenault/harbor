from datetime import UTC, datetime, timedelta
from decimal import Decimal

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.config import load_optimizer_config
from harbor_bot.optimizer.models import OptimizationStatus, TrialRecord, TrialScore
from harbor_bot.optimizer.research_protocol import (
    ResearchProtocolConfig,
    _rank_discovery_candidates,
    research_optimizer_config,
    research_readiness,
)
from harbor_bot.strategy.models import strategy_config_from_defaults


def test_research_readiness_rejects_short_datasets_with_concrete_requirements() -> None:
    readiness = research_readiness(
        _research_days("2026-01-05", day_count=4),
        strategy_config_from_defaults(load_default_config()),
        protocol_config=ResearchProtocolConfig(
            min_evaluable_days=6,
            min_discovery_days=4,
            holdout_days=2,
            train_window_days=2,
            oos_window_days=1,
            step_days=1,
        ),
    )

    assert readiness["status"] == "not_ready"
    assert readiness["evaluable_day_count"] == 4
    assert readiness["data_requirements"]["min_evaluable_days"] == 6
    assert readiness["message"] == "4 complete strategy days available; 6 required"


def test_research_readiness_rejects_session_gaps() -> None:
    candles = list(_research_days("2026-01-05", day_count=6))
    candles = tuple(
        candle for candle in candles if candle.ts != datetime(2026, 1, 7, 8, 15, tzinfo=UTC)
    )

    readiness = research_readiness(
        candles,
        strategy_config_from_defaults(load_default_config()),
        protocol_config=ResearchProtocolConfig(
            min_evaluable_days=6,
            min_discovery_days=4,
            holdout_days=2,
            max_session_gap_minutes=1,
            train_window_days=2,
            oos_window_days=1,
            step_days=1,
        ),
    )

    rejected_days = [day for day in readiness["evaluable_days"] if day["reason"] is not None]
    assert readiness["status"] == "not_ready"
    assert rejected_days == [
        {
            "trading_date": "2026-01-07",
            "candle_count": 539,
            "evaluable": False,
            "reason": "London window has a gap greater than 1 minutes",
        }
    ]


def test_research_optimizer_config_ignores_caller_knobs_for_fixed_protocol() -> None:
    configured = research_optimizer_config(
        load_optimizer_config(),
        protocol_config=ResearchProtocolConfig(
            trial_count=7,
            candidate_count=2,
            train_window_days=3,
            oos_window_days=2,
            step_days=1,
            min_in_sample_trades=4,
            min_oos_trades=3,
        ),
    )

    assert configured.trial_count == 7
    assert configured.candidate_count == 2
    assert configured.walk_forward.train_window_days == 3
    assert configured.walk_forward.oos_window_days == 2
    assert configured.min_in_sample_trades == 4
    assert configured.min_oos_trades == 3
    assert configured.robustness_neighbor_count == 0


def test_research_protocol_can_holdout_validate_broader_discovery_shortlist() -> None:
    candidates = _rank_discovery_candidates(
        (
            _trial(0, in_sample="1.0", out_of_sample="1.0", robustness="1.0"),
            _trial(1, in_sample="0.8", out_of_sample="0.8", robustness="0.8"),
            _trial(2, in_sample="0.6", out_of_sample="0.6", robustness="0.6"),
            _trial(3, in_sample="-1.0", out_of_sample="2.0", robustness="2.0"),
            _trial(4, in_sample="2.0", out_of_sample="-1.0", robustness="2.0"),
        ),
        candidate_count=3,
    )

    assert [candidate.source_trial_no for candidate in candidates] == [0, 1, 2]


def _research_days(start_day: str, *, day_count: int) -> tuple[ClosedCandle, ...]:
    start = datetime.fromisoformat(f"{start_day}T00:00:00+00:00")
    candles = []
    for day_index in range(day_count):
        trading_day = start + timedelta(days=day_index)
        candles.extend(_minute_window(trading_day - timedelta(days=1), 20, 0, 4 * 60))
        candles.extend(_minute_window(trading_day, 2, 0, 3 * 60))
        candles.extend(_minute_window(trading_day, 9, 30, 2 * 60))
    return tuple(candles)


def _trial(
    trial_no: int,
    *,
    in_sample: str,
    out_of_sample: str,
    robustness: str,
) -> TrialRecord:
    return TrialRecord(
        trial_no=trial_no,
        params={"fvg_window": trial_no + 1},
        score=TrialScore(
            in_sample_score=Decimal(in_sample),
            out_of_sample_score=Decimal(out_of_sample),
            robustness_score=Decimal(robustness),
        ),
        status=OptimizationStatus.COMPLETED,
    )


def _minute_window(
    local_day: datetime,
    hour: int,
    minute: int,
    count: int,
) -> list[ClosedCandle]:
    # January New York is UTC-5; these fixtures avoid DST boundaries.
    start = datetime(
        local_day.year,
        local_day.month,
        local_day.day,
        hour,
        minute,
        tzinfo=UTC,
    ) + timedelta(hours=5)
    return [_candle(start + timedelta(minutes=index)) for index in range(count)]


def _candle(ts: datetime) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=ts,
        o=Decimal("1.1000"),
        h=Decimal("1.1010"),
        low=Decimal("1.0990"),
        c=Decimal("1.1005"),
        volume=100,
    )
