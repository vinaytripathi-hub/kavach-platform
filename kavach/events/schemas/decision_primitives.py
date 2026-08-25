"""Embedded decision primitives (ADR-0012).

Every decision event carries four mandatory embedded fields: Evidence,
ReasoningTrace, Confidence, and a ``decided_by`` identifier. These types
are versioned per ADR-0010 and are not themselves domain events; they
are embedded inside decision events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from kavach.events._base import utcnow


class EvidenceReference(BaseModel):
    """By-reference pointer to a large or sensitive underlying record.

    Sensitive attributes (PII, credit scores) are referenced by id, not
    inlined, per the data-minimisation rule in ADR-0012.
    """

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    kind: str
    ref_id: str
    digest: str | None = None


class Evidence(BaseModel):
    """Structured evidence basis for a decision."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    references: list[EvidenceReference] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=utcnow)


class ReasoningStep(BaseModel):
    """One intermediate step in a reasoning trace."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    name: str
    detail: str


class ReasoningTrace(BaseModel):
    """Structured reasoning from evidence to decision."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    kind: Literal["rule", "model", "composite", "human"]
    rule_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    features_evaluated: list[str] | None = None
    intermediate_steps: list[ReasoningStep] | None = None
    decision_path: str


class Confidence(BaseModel):
    """Confidence indicator for a decision."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    kind: Literal["rule_deterministic", "probabilistic", "human_judged"]
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration: str | None = None


def rule_deterministic() -> Confidence:
    """Confidence for a rule-based, deterministic decision (effectively 1.0)."""
    return Confidence(kind="rule_deterministic", score=1.0)
