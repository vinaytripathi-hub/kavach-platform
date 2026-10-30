"""Versioned event schemas and embedded primitives (ADR-0010).

This package is the public catalogue of the substrate's event vocabulary
and the embedded decision/trust/sufficiency primitives. Importing this
package registers every concrete event class for replay dispatch.
"""

from __future__ import annotations

from kavach.events.schemas.action import ActionExecuted
from kavach.events.schemas.audit import EvidenceRecorded
from kavach.events.schemas.data_sufficiency import (
    Band,
    DataSufficiency,
    ModalitySufficiency,
    compose_sufficiency,
    worst_band,
)
from kavach.events.schemas.decision_primitives import (
    Confidence,
    Evidence,
    EvidenceReference,
    ReasoningStep,
    ReasoningTrace,
    rule_deterministic,
)
from kavach.events.schemas.feedback import DecisionFeedbackRecorded, Feedback
from kavach.events.schemas.mandate import (
    Mandate,
    MandateConstraint,
    MandateIssued,
    MandatePresented,
    MandateRevoked,
)
from kavach.events.schemas.monitor import AgentMetricSnapshot, AnomalyAcknowledged, AnomalyDetected
from kavach.events.schemas.policy import DecisionEmitted, Outcome, PolicyEvaluated
from kavach.events.schemas.revocation import AgentRevoked, CredentialRevoked
from kavach.events.schemas.stepup import StepUpRequested, StepUpResolved
from kavach.events.schemas.trust import CompositionSpec, TrustAssessment, TrustDimension
from kavach.events.schemas.trust_events import TrustAssessmentEmitted

__all__ = [  # noqa: RUF022 (grouped by concern for readability)
    # Events
    "ActionExecuted",
    "AgentMetricSnapshot",
    "AgentRevoked",
    "AnomalyAcknowledged",
    "AnomalyDetected",
    "CredentialRevoked",
    "DecisionEmitted",
    "DecisionFeedbackRecorded",
    "EvidenceRecorded",
    "MandateIssued",
    "MandatePresented",
    "MandateRevoked",
    "PolicyEvaluated",
    "StepUpRequested",
    "StepUpResolved",
    "TrustAssessmentEmitted",
    # Decision primitives
    "Confidence",
    "Evidence",
    "EvidenceReference",
    "ReasoningStep",
    "ReasoningTrace",
    "rule_deterministic",
    # Data sufficiency
    "Band",
    "DataSufficiency",
    "ModalitySufficiency",
    "compose_sufficiency",
    "worst_band",
    # Trust
    "CompositionSpec",
    "TrustAssessment",
    "TrustDimension",
    # Literals
    "Feedback",
    "Outcome",
    # Mandates
    "Mandate",
    "MandateConstraint",
]
