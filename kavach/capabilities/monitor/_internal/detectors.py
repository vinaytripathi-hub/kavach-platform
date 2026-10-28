"""First-cut anomaly detectors (ADR-0019).

Each detector emits a severity label. ``signal_score`` is advisory and
is never read by policy.
"""

from __future__ import annotations

from collections.abc import Sequence

from kavach.events._base import DomainEvent, new_event_id
from kavach.events.schemas.monitor import AnomalyDetected
from kavach.events.schemas.policy import DecisionEmitted


def _signal(
    event: DomainEvent,
    *,
    detector_id: str,
    severity: str,
    description: str,
    score: float | None = None,
) -> AnomalyDetected:
    agent_id = event.aggregate_id() or "unknown"
    return AnomalyDetected(
        tenant_id=event.tenant_id,
        agent_id=agent_id,
        anomaly_id=new_event_id(),
        detector_id=detector_id,
        severity=severity,  # type: ignore[arg-type]
        signal_score=score,
        description=description,
        triggering_event_ids=[event.event_id],
        decided_by=f"monitor:{detector_id}",
    )


class FakeDetector:
    """Baseline detector that never fires. Used to prove the wiring."""

    detector_id = "fake"

    def observe(self, event: DomainEvent, history: Sequence[DomainEvent]) -> list[AnomalyDetected]:
        del event, history
        return []


class RateDetector:
    """Warn at 3 decisions in the window, critical at 5. Suppress when thin."""

    detector_id = "rate"

    def __init__(self, *, warn_at: int = 3, critical_at: int = 5, min_history: int = 3) -> None:
        self._warn_at = warn_at
        self._critical_at = critical_at
        self._min_history = min_history

    def observe(self, event: DomainEvent, history: Sequence[DomainEvent]) -> list[AnomalyDetected]:
        if not isinstance(event, DecisionEmitted):
            return []
        decisions = [item for item in history if isinstance(item, DecisionEmitted)]
        if len(decisions) < self._min_history:
            return []
        count = len(decisions)
        if count >= self._critical_at:
            return [
                _signal(
                    event,
                    detector_id=self.detector_id,
                    severity="critical",
                    description=f"{count} decisions in window",
                    score=float(count),
                )
            ]
        if count >= self._warn_at:
            return [
                _signal(
                    event,
                    detector_id=self.detector_id,
                    severity="warn",
                    description=f"{count} decisions in window",
                    score=float(count),
                )
            ]
        return []


class OutcomeDriftDetector:
    """Fires when the deny rate more than doubles versus the prior half-window."""

    detector_id = "outcome_drift"

    def observe(self, event: DomainEvent, history: Sequence[DomainEvent]) -> list[AnomalyDetected]:
        if not isinstance(event, DecisionEmitted):
            return []
        decisions = [item for item in history if isinstance(item, DecisionEmitted)]
        min_window = 4
        if len(decisions) < min_window:
            return []
        mid = len(decisions) // 2
        earlier = decisions[:mid]
        later = decisions[mid:]

        def deny_rate(items: list[DecisionEmitted]) -> float:
            if not items:
                return 0.0
            return sum(1 for item in items if item.outcome == "deny") / len(items)

        before = deny_rate(earlier)
        after = deny_rate(later)
        if before > 0 and after > before * 2:
            return [
                _signal(
                    event,
                    detector_id=self.detector_id,
                    severity="warn",
                    description="Deny rate shifted more than 2x.",
                    score=after,
                )
            ]
        return []


class ScopeExpansionDetector:
    """Fires when an agent uses an action type not seen before."""

    detector_id = "scope_expansion"

    def observe(self, event: DomainEvent, history: Sequence[DomainEvent]) -> list[AnomalyDetected]:
        if not isinstance(event, DecisionEmitted):
            return []
        prior = [
            item.action_type
            for item in history
            if isinstance(item, DecisionEmitted) and item.event_id != event.event_id
        ]
        if prior and event.action_type not in prior:
            return [
                _signal(
                    event,
                    detector_id=self.detector_id,
                    severity="warn",
                    description=f"New action type {event.action_type}.",
                )
            ]
        return []


class ConfidenceDropDetector:
    """Fires when a probabilistic decision's confidence falls below 0.5."""

    detector_id = "confidence_drop"

    def observe(self, event: DomainEvent, history: Sequence[DomainEvent]) -> list[AnomalyDetected]:
        del history
        if not isinstance(event, DecisionEmitted):
            return []
        score = event.confidence.score
        low_confidence = 0.5
        if score is not None and score < low_confidence:
            return [
                _signal(
                    event,
                    detector_id=self.detector_id,
                    severity="critical",
                    description="Decision confidence dropped below 0.5.",
                    score=score,
                )
            ]
        return []
