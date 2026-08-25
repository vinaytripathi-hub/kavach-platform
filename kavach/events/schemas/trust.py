"""Multidimensional trust primitives (ADR-0014).

Trust is a tensor: a set of dimensions, each with its own value and data
sufficiency, plus an optional composition spec describing how to roll the
dimensions up into a scalar for a given consumer.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from kavach.events._base import utcnow
from kavach.events.schemas.data_sufficiency import DataSufficiency


class CompositionSpec(BaseModel):
    """How to compose dimensions into a scalar for a given consumer."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    method: Literal["weighted_average", "min", "max", "custom"]
    weights: dict[str, float] | None = None
    custom_function_id: str | None = None
    notes: str = ""


class TrustDimension(BaseModel):
    """One facet of trust."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    name: str
    value: float = Field(ge=0.0, le=1.0)
    sufficiency: DataSufficiency
    contributors: list[str] = Field(default_factory=list)
    reason: str = ""


class TrustAssessment(BaseModel):
    """Multidimensional trust assessment for an agent in a context."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    agent_id: str
    context: str
    dimensions: dict[str, TrustDimension]
    composition: CompositionSpec | None = None
    assessed_at: datetime = Field(default_factory=utcnow)

    def compose(self, spec: CompositionSpec | None = None) -> float | None:
        """Project the tensor into a scalar using ``spec`` (or the default).

        Returns None when no composition spec is available. ``custom``
        methods are not resolvable in-process without a function registry,
        so they return None here; consumers supplying a custom method are
        expected to compute the scalar themselves.
        """
        spec = spec or self.composition
        if spec is None or not self.dimensions:
            return None
        values = {name: dim.value for name, dim in self.dimensions.items()}
        if spec.method == "min":
            return min(values.values())
        if spec.method == "max":
            return max(values.values())
        if spec.method == "weighted_average":
            weights = spec.weights or {name: 1.0 for name in values}
            total_w = sum(weights.get(name, 0.0) for name in values)
            if total_w == 0:
                return None
            return sum(values[name] * weights.get(name, 0.0) for name in values) / total_w
        return None
