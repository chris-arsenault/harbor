from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any


class OptimizationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PRUNED = "pruned"


class SearchParameterType(StrEnum):
    INT = "int"
    DECIMAL = "decimal"
    CATEGORICAL = "categorical"


@dataclass(frozen=True)
class SearchParameter:
    name: str
    parameter_type: SearchParameterType
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    step: Decimal | None = None
    choices: tuple[str | int | Decimal, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameter_type", SearchParameterType(self.parameter_type))
        object.__setattr__(self, "choices", tuple(self.choices))
        if self.minimum is not None:
            object.__setattr__(self, "minimum", Decimal(str(self.minimum)))
        if self.maximum is not None:
            object.__setattr__(self, "maximum", Decimal(str(self.maximum)))
        if self.step is not None:
            object.__setattr__(self, "step", Decimal(str(self.step)))

        if self.parameter_type == SearchParameterType.CATEGORICAL:
            if not self.choices:
                msg = f"{self.name} categorical parameter must define choices"
                raise ValueError(msg)
            return

        if self.minimum is None or self.maximum is None:
            msg = f"{self.name} numeric parameter must define min and max"
            raise ValueError(msg)
        if self.minimum > self.maximum:
            msg = f"{self.name} minimum cannot exceed maximum"
            raise ValueError(msg)
        if self.step is not None and self.step <= 0:
            msg = f"{self.name} step must be positive"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.parameter_type.value}
        if self.parameter_type == SearchParameterType.CATEGORICAL:
            data["choices"] = [str(choice) for choice in self.choices]
            return data
        data["min"] = str(self.minimum)
        data["max"] = str(self.maximum)
        if self.step is not None:
            data["step"] = str(self.step)
        return data


@dataclass(frozen=True)
class SearchSpace:
    parameters: tuple[SearchParameter, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", tuple(self.parameters))
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            msg = "search parameter names must be unique"
            raise ValueError(msg)

    def by_name(self) -> dict[str, SearchParameter]:
        return {parameter.name: parameter for parameter in self.parameters}

    def to_jsonable(self) -> dict[str, Any]:
        return {parameter.name: parameter.to_jsonable() for parameter in self.parameters}


@dataclass(frozen=True)
class WalkForwardConfig:
    train_window_days: int
    oos_window_days: int
    step_days: int

    def __post_init__(self) -> None:
        if self.train_window_days <= 0:
            msg = "train_window_days must be positive"
            raise ValueError(msg)
        if self.oos_window_days <= 0:
            msg = "oos_window_days must be positive"
            raise ValueError(msg)
        if self.step_days <= 0:
            msg = "step_days must be positive"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, int]:
        return {
            "train_window_days": self.train_window_days,
            "oos_window_days": self.oos_window_days,
            "step_days": self.step_days,
        }


@dataclass(frozen=True)
class OptimizationConfig:
    search_space: SearchSpace
    walk_forward: WalkForwardConfig
    trial_count: int
    candidate_count: int
    tpe_seed: int
    min_in_sample_trades: int
    min_oos_trades: int
    drawdown_floor: Decimal
    robustness_neighbor_count: int
    robustness_step_scale: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "drawdown_floor", Decimal(str(self.drawdown_floor)))
        object.__setattr__(
            self,
            "robustness_step_scale",
            Decimal(str(self.robustness_step_scale)),
        )
        if self.trial_count <= 0:
            msg = "trial_count must be positive"
            raise ValueError(msg)
        if self.candidate_count <= 0:
            msg = "candidate_count must be positive"
            raise ValueError(msg)
        if self.min_in_sample_trades < 0 or self.min_oos_trades < 0:
            msg = "minimum trade counts cannot be negative"
            raise ValueError(msg)
        if self.drawdown_floor <= 0:
            msg = "drawdown_floor must be positive"
            raise ValueError(msg)
        if self.robustness_neighbor_count < 0:
            msg = "robustness_neighbor_count cannot be negative"
            raise ValueError(msg)
        if self.robustness_step_scale <= 0:
            msg = "robustness_step_scale must be positive"
            raise ValueError(msg)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "trial_count": self.trial_count,
            "candidate_count": self.candidate_count,
            "tpe_seed": self.tpe_seed,
            "drawdown_floor": str(self.drawdown_floor),
            "minimum_trade_count": {
                "in_sample": self.min_in_sample_trades,
                "out_of_sample": self.min_oos_trades,
            },
            "robustness": {
                "neighbor_count": self.robustness_neighbor_count,
                "step_scale": str(self.robustness_step_scale),
            },
            "walk_forward": self.walk_forward.to_jsonable(),
            "search_space": self.search_space.to_jsonable(),
        }


@dataclass(frozen=True)
class TrialScore:
    in_sample_score: Decimal
    out_of_sample_score: Decimal
    robustness_score: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "in_sample_score", Decimal(str(self.in_sample_score)))
        object.__setattr__(self, "out_of_sample_score", Decimal(str(self.out_of_sample_score)))
        object.__setattr__(self, "robustness_score", Decimal(str(self.robustness_score)))


@dataclass(frozen=True)
class TrialRecord:
    trial_no: int
    params: dict[str, Any]
    score: TrialScore
    pruned: bool = False
    status: OptimizationStatus = OptimizationStatus.COMPLETED

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params))
        object.__setattr__(self, "status", OptimizationStatus(self.status))


@dataclass(frozen=True)
class CandidateVariant:
    label: str
    params: dict[str, Any]
    source_trial_no: int
    status: str = "paper"

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", dict(self.params))
        if self.status != "paper":
            msg = "M6 candidate variants must be paper variants"
            raise ValueError(msg)
