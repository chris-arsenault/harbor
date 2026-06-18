from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.paper_engine.models import (
    LabStudySnapshot,
    PaperVariant,
    VariantEquityPoint,
    VariantLeaderboardRow,
)

Jsonable = str | int | bool | None | list["Jsonable"] | dict[str, "Jsonable"]


@dataclass(frozen=True)
class CandidateScatterPoint:
    trial_id: int
    trial_no: int
    params: Mapping[str, Any]
    in_sample_score: Decimal
    out_of_sample_score: Decimal
    robustness_score: Decimal
    pruned: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params))
        object.__setattr__(self, "in_sample_score", Decimal(str(self.in_sample_score)))
        object.__setattr__(self, "out_of_sample_score", Decimal(str(self.out_of_sample_score)))
        object.__setattr__(self, "robustness_score", Decimal(str(self.robustness_score)))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "trial_id": self.trial_id,
            "trial_no": self.trial_no,
            "params": _json_safe(self.params),
            "in_sample_score": str(self.in_sample_score),
            "out_of_sample_score": str(self.out_of_sample_score),
            "robustness_score": str(self.robustness_score),
            "pruned": self.pruned,
        }


@dataclass(frozen=True)
class VariantEquityCurve:
    variant_id: int
    points: tuple[VariantEquityPoint, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "variant_id": self.variant_id,
            "points": [point.to_jsonable() for point in self.points],
        }


@dataclass(frozen=True)
class LabVariantOverview:
    variants: tuple[PaperVariant, ...] = field(default_factory=tuple)
    leaderboard: tuple[VariantLeaderboardRow, ...] = field(default_factory=tuple)
    equity_curves: tuple[VariantEquityCurve, ...] = field(default_factory=tuple)
    data_separation: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "variants", tuple(self.variants))
        object.__setattr__(self, "leaderboard", tuple(self.leaderboard))
        object.__setattr__(self, "equity_curves", tuple(self.equity_curves))
        object.__setattr__(self, "data_separation", dict(self.data_separation))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "variants": [variant.to_jsonable() for variant in self.variants],
            "leaderboard": [row.to_jsonable() for row in self.leaderboard],
            "equity_curves": [curve.to_jsonable() for curve in self.equity_curves],
            "data_separation": _json_safe(self.data_separation),
        }


@dataclass(frozen=True)
class LabSnapshot:
    study: LabStudySnapshot
    candidates: tuple[CandidateScatterPoint, ...] = field(default_factory=tuple)
    variants: LabVariantOverview = field(default_factory=LabVariantOverview)
    data_separation: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "data_separation", dict(self.data_separation))

    def to_jsonable(self) -> dict[str, Jsonable]:
        return {
            "study": self.study.to_jsonable(),
            "candidates": [candidate.to_jsonable() for candidate in self.candidates],
            "variants": self.variants.to_jsonable(),
            "data_separation": _json_safe(self.data_separation),
        }


@dataclass(frozen=True)
class LabActionResult:
    action: str
    variant_id: int
    status: str

    def to_jsonable(self) -> dict[str, str | int]:
        return {
            "action": self.action,
            "variant_id": self.variant_id,
            "status": self.status,
        }


def _json_safe(value: Any) -> Jsonable:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | bool):
        return value
    return str(value)
