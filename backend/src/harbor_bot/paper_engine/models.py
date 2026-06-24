from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.backtester.models import BacktestConfig, FillPolicy

Jsonable = str | int | bool | None | list["Jsonable"] | dict[str, "Jsonable"]


@dataclass(frozen=True)
class PaperEngineConfig:
    initial_nav: Decimal = Decimal("10000")
    spread_pips: Decimal = Decimal("0.8")
    slippage_pips: Decimal = Decimal("0.1")
    commission_per_unit: Decimal = Decimal("0")
    ambiguous_fill_policy: FillPolicy = FillPolicy.PESSIMISTIC
    force_ny_close: bool = True
    live_forward_drawdown_floor: Decimal = Decimal("1")
    leaderboard_min_trades: int = 0
    max_lab_rows: int = 200

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_nav", Decimal(str(self.initial_nav)))
        object.__setattr__(self, "spread_pips", Decimal(str(self.spread_pips)))
        object.__setattr__(self, "slippage_pips", Decimal(str(self.slippage_pips)))
        object.__setattr__(self, "commission_per_unit", Decimal(str(self.commission_per_unit)))
        object.__setattr__(self, "ambiguous_fill_policy", FillPolicy(self.ambiguous_fill_policy))
        object.__setattr__(
            self,
            "live_forward_drawdown_floor",
            Decimal(str(self.live_forward_drawdown_floor)),
        )
        if self.initial_nav <= 0:
            msg = "initial_nav must be positive"
            raise ValueError(msg)
        if self.spread_pips < 0:
            msg = "spread_pips cannot be negative"
            raise ValueError(msg)
        if self.slippage_pips < 0:
            msg = "slippage_pips cannot be negative"
            raise ValueError(msg)
        if self.commission_per_unit < 0:
            msg = "commission_per_unit cannot be negative"
            raise ValueError(msg)
        if self.live_forward_drawdown_floor <= 0:
            msg = "live-forward drawdown floor must be positive"
            raise ValueError(msg)
        if self.leaderboard_min_trades < 0:
            msg = "leaderboard_min_trades cannot be negative"
            raise ValueError(msg)
        if self.max_lab_rows <= 0:
            msg = "max_lab_rows must be positive"
            raise ValueError(msg)

    def to_backtest_config(self) -> BacktestConfig:
        return BacktestConfig(
            initial_nav=self.initial_nav,
            spread_pips=self.spread_pips,
            slippage_pips=self.slippage_pips,
            commission_per_unit=self.commission_per_unit,
            ambiguous_fill_policy=self.ambiguous_fill_policy,
            force_ny_close=self.force_ny_close,
        )

    def to_jsonable(self) -> dict[str, str | int | bool]:
        return {
            "initial_nav": str(self.initial_nav),
            "spread_pips": str(self.spread_pips),
            "slippage_pips": str(self.slippage_pips),
            "commission_per_unit": str(self.commission_per_unit),
            "ambiguous_fill_policy": self.ambiguous_fill_policy.value,
            "force_ny_close": self.force_ny_close,
            "live_forward_drawdown_floor": str(self.live_forward_drawdown_floor),
            "leaderboard_min_trades": self.leaderboard_min_trades,
            "max_lab_rows": self.max_lab_rows,
        }


@dataclass(frozen=True)
class PaperVariant:
    id: int
    label: str
    params: Mapping[str, Any]
    source_trial_id: int
    status: str = "paper"
    created_ts: datetime | None = None
    trial_scores: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params))
        object.__setattr__(self, "trial_scores", dict(self.trial_scores))
        if self.status != "paper":
            msg = "paper engine variants must have paper status"
            raise ValueError(msg)
        if self.id <= 0:
            msg = "paper variant id must be positive"
            raise ValueError(msg)
        if self.source_trial_id <= 0:
            msg = "paper variant source_trial_id must be positive"
            raise ValueError(msg)
        if self.created_ts is not None:
            object.__setattr__(self, "created_ts", _utc(self.created_ts))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "id": self.id,
            "label": self.label,
            "params": _json_safe(self.params),
            "source_trial_id": self.source_trial_id,
            "status": self.status,
            "created_ts": _json_safe(self.created_ts),
            "trial_scores": _json_safe(self.trial_scores),
        }


@dataclass(frozen=True)
class VariantTrade:
    variant_id: int
    side: str
    units: Decimal
    entry_price: Decimal
    entry_ts: datetime
    exit_price: Decimal
    exit_ts: datetime
    pnl: Decimal
    r_multiple: Decimal
    exit_reason: str
    id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "units", Decimal(str(self.units)))
        object.__setattr__(self, "entry_price", Decimal(str(self.entry_price)))
        object.__setattr__(self, "entry_ts", _utc(self.entry_ts))
        object.__setattr__(self, "exit_price", Decimal(str(self.exit_price)))
        object.__setattr__(self, "exit_ts", _utc(self.exit_ts))
        object.__setattr__(self, "pnl", Decimal(str(self.pnl)))
        object.__setattr__(self, "r_multiple", Decimal(str(self.r_multiple)))
        if self.variant_id <= 0:
            msg = "variant_id must be positive"
            raise ValueError(msg)
        if self.id is not None and self.id <= 0:
            msg = "variant trade id must be positive"
            raise ValueError(msg)
        if self.side not in {"long", "short"}:
            msg = "variant trade side must be long or short"
            raise ValueError(msg)
        if self.units <= 0:
            msg = "variant trade units must be positive"
            raise ValueError(msg)

    def to_persistence_row(self) -> dict[str, Decimal | datetime | str | int]:
        return {
            "variant_id": self.variant_id,
            "side": self.side,
            "units": self.units,
            "entry_price": self.entry_price,
            "entry_ts": self.entry_ts,
            "exit_price": self.exit_price,
            "exit_ts": self.exit_ts,
            "pnl": self.pnl,
            "r_multiple": self.r_multiple,
            "exit_reason": self.exit_reason,
        }

    def to_jsonable(self) -> dict[str, Jsonable]:
        data: dict[str, Jsonable] = {
            "variant_id": self.variant_id,
            "side": self.side,
            "units": str(self.units),
            "entry_price": str(self.entry_price),
            "entry_ts": self.entry_ts.isoformat(),
            "exit_price": str(self.exit_price),
            "exit_ts": self.exit_ts.isoformat(),
            "pnl": str(self.pnl),
            "r_multiple": str(self.r_multiple),
            "exit_reason": self.exit_reason,
        }
        if self.id is not None:
            data["id"] = self.id
        return data


@dataclass(frozen=True)
class VariantEquityPoint:
    variant_id: int
    ts: datetime
    nav: Decimal
    drawdown: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "ts", _utc(self.ts))
        object.__setattr__(self, "nav", Decimal(str(self.nav)))
        object.__setattr__(self, "drawdown", Decimal(str(self.drawdown)))
        if self.variant_id <= 0:
            msg = "variant_id must be positive"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, str | int]:
        return {
            "variant_id": self.variant_id,
            "ts": self.ts.isoformat(),
            "nav": str(self.nav),
            "drawdown": str(self.drawdown),
        }


@dataclass(frozen=True)
class VariantStats:
    variant_id: int
    trade_count: int
    win_rate: Decimal
    net_pnl: Decimal
    expectancy: Decimal
    average_r: Decimal
    max_drawdown: Decimal
    ending_nav: Decimal
    live_forward_score: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "win_rate", Decimal(str(self.win_rate)))
        object.__setattr__(self, "net_pnl", Decimal(str(self.net_pnl)))
        object.__setattr__(self, "expectancy", Decimal(str(self.expectancy)))
        object.__setattr__(self, "average_r", Decimal(str(self.average_r)))
        object.__setattr__(self, "max_drawdown", Decimal(str(self.max_drawdown)))
        object.__setattr__(self, "ending_nav", Decimal(str(self.ending_nav)))
        object.__setattr__(self, "live_forward_score", Decimal(str(self.live_forward_score)))
        if self.variant_id <= 0:
            msg = "variant_id must be positive"
            raise ValueError(msg)
        if self.trade_count < 0:
            msg = "trade_count cannot be negative"
            raise ValueError(msg)

    @classmethod
    def empty(cls, *, variant_id: int, initial_nav: Decimal) -> "VariantStats":
        return cls(
            variant_id=variant_id,
            trade_count=0,
            win_rate=Decimal("0"),
            net_pnl=Decimal("0"),
            expectancy=Decimal("0"),
            average_r=Decimal("0"),
            max_drawdown=Decimal("0"),
            ending_nav=initial_nav,
            live_forward_score=Decimal("0"),
        )

    def to_jsonable(self) -> dict[str, int | str]:
        return {
            "variant_id": self.variant_id,
            "trade_count": self.trade_count,
            "win_rate": str(self.win_rate),
            "net_pnl": str(self.net_pnl),
            "expectancy": str(self.expectancy),
            "average_r": str(self.average_r),
            "max_drawdown": str(self.max_drawdown),
            "ending_nav": str(self.ending_nav),
            "live_forward_score": str(self.live_forward_score),
        }


@dataclass(frozen=True)
class VariantLeaderboardRow:
    rank: int
    variant: PaperVariant
    stats: VariantStats
    out_of_sample_score: Decimal
    robustness_score: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "out_of_sample_score", Decimal(str(self.out_of_sample_score)))
        object.__setattr__(self, "robustness_score", Decimal(str(self.robustness_score)))
        if self.rank <= 0:
            msg = "leaderboard rank must be positive"
            raise ValueError(msg)
        if self.variant.id != self.stats.variant_id:
            msg = "leaderboard variant and stats must refer to the same variant"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "rank": self.rank,
            "variant": self.variant.to_jsonable(),
            "stats": self.stats.to_jsonable(),
            "out_of_sample_score": str(self.out_of_sample_score),
            "robustness_score": str(self.robustness_score),
        }


@dataclass(frozen=True)
class LabStudySnapshot:
    study_id: int
    status: str
    trial_count: int
    total_trial_count: int
    candidate_count: int
    paper_variant_count: int
    created_ts: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_ts", _utc(self.created_ts))
        if self.study_id <= 0:
            msg = "study_id must be positive"
            raise ValueError(msg)
        if self.trial_count < 0:
            msg = "trial_count cannot be negative"
            raise ValueError(msg)
        if self.candidate_count < 0:
            msg = "candidate_count cannot be negative"
            raise ValueError(msg)
        if self.paper_variant_count < 0:
            msg = "paper_variant_count cannot be negative"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, int | str]:
        return {
            "study_id": self.study_id,
            "status": self.status,
            "trial_count": self.trial_count,
            "candidate_count": self.candidate_count,
            "paper_variant_count": self.paper_variant_count,
            "created_ts": self.created_ts.isoformat(),
        }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "paper engine datetimes must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _json_safe(value: Any) -> Jsonable:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | bool):
        return value
    return str(value)
