"""API request/response models (ADR-0016).

Bodies echo the substrate event/decision/trust primitives wherever a body
corresponds to substrate data, so there is one source of truth for shape.
Transport-only concerns (pagination, problem+json) are added here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kavach.capabilities.audit import AuditRecord, SignatureManifest
from kavach.capabilities.policy import PolicyRule
from kavach.events.schemas import (
    Confidence,
    DataSufficiency,
    Evidence,
    ReasoningTrace,
)

# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class HealthStatus(BaseModel):
    status: str = "ok"
    version: str


class Problem(BaseModel):
    """RFC 7807 problem detail."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    code: str


# ---------------------------------------------------------------------------
# Ingress + decisions
# ---------------------------------------------------------------------------


class ActionRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: str | None = None


class EventReceipt(BaseModel):
    event_id: str
    event_type: str
    schema_version: int
    recorded_at: datetime


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: str | None = None
    use_case: str = "customer_service"


class StepUpInfo(BaseModel):
    reason: str
    required_role: str


class DecisionResponse(BaseModel):
    decision_id: str
    outcome: str
    rule_id: str | None = None
    evidence: Evidence
    reasoning: ReasoningTrace
    confidence: Confidence
    decided_by: str
    data_sufficiency: DataSufficiency | None = None
    step_up: StepUpInfo | None = None


class StepUpResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: str
    operator_id: str
    rationale: str = ""


class StepUpQueueItem(BaseModel):
    decision_id: str
    agent_id: str
    action_type: str
    reason: str
    required_role: str
    status: str
    requested_at: datetime


class StepUpQueuePage(BaseModel):
    items: list[StepUpQueueItem]


# ---------------------------------------------------------------------------
# Trust + timeline
# ---------------------------------------------------------------------------


class TrustResponse(BaseModel):
    agent_id: str
    context: str
    dimensions: dict[str, Any]
    composed_scalar: float | None = None
    assessed_at: datetime


class TimelineEntry(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    summary: str
    outcome: str | None = None


class TimelinePage(BaseModel):
    items: list[TimelineEntry]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Audit export
# ---------------------------------------------------------------------------


class AuditExportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    agent_id: str
    frm: datetime = Field(alias="from")
    to: datetime


class AuditExportStatus(BaseModel):
    export_id: str
    status: str
    record_count: int
    chain_head: str | None = None
    signature_manifest: SignatureManifest | None = None
    records: list[AuditRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Webhooks + admin
# ---------------------------------------------------------------------------


class WebhookSubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    event_types: list[str]
    secret: str | None = None


class WebhookSubscription(BaseModel):
    subscription_id: str
    url: str
    event_types: list[str]
    active: bool
    created_at: datetime


class AgentRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str
    display_name: str
    use_case: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRegistration(BaseModel):
    agent_id: str
    display_name: str
    use_case: str | None = None
    registered_at: datetime


class PolicyUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    use_case: str
    version: str = "0"
    default_effect: str = "deny"
    default_step_up_role: str = "supervisor"
    rules: list[PolicyRule]


class PolicyUploadResult(BaseModel):
    use_case: str
    version: str
    rule_count: int
    accepted_at: datetime
