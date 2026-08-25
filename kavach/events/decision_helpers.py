"""Builders for decision-grade events (ADR-0012).

Every decision-emitting capability must construct the four embedded
fields correctly. These helpers reduce the chance of a decision being
emitted with an empty reasoning trace or a missing confidence.
"""

from __future__ import annotations

from typing import Any

from kavach.events.schemas.decision_primitives import (
    Confidence,
    Evidence,
    EvidenceReference,
    ReasoningTrace,
    rule_deterministic,
)

__all__ = [
    "human_confidence",
    "human_reasoning",
    "make_evidence",
    "rule_deterministic",
    "rule_reasoning",
]


def make_evidence(
    attributes: dict[str, Any] | None = None,
    references: list[EvidenceReference] | None = None,
) -> Evidence:
    """Build an Evidence object from inline attributes and references."""
    return Evidence(
        attributes=attributes or {},
        references=references or [],
    )


def rule_reasoning(rule_id: str, decision_path: str) -> ReasoningTrace:
    """Build a rule-based reasoning trace."""
    return ReasoningTrace(kind="rule", rule_id=rule_id, decision_path=decision_path)


def human_reasoning(decision_path: str) -> ReasoningTrace:
    """Build a human-judged reasoning trace."""
    return ReasoningTrace(kind="human", decision_path=decision_path)


def human_confidence(score: float | None = None) -> Confidence:
    """Build a human-judged confidence indicator."""
    return Confidence(kind="human_judged", score=score)
