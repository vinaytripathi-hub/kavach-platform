"""Substrate service: high-level operations the API and demos call.

This is composition glue, not a capability: it sequences capability calls
(policy evaluation, audit chaining via the bus, trust assessment) inside a
single transaction and returns the resulting events. Experiences read the
projections these operations maintain (ADR-0001, ADR-0009).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.audit import AuditExport, AuditExporter
from kavach.capabilities.mandate import MandateVerifier, VerifiedMandate
from kavach.capabilities.mandate._internal.ap2_adapter import AP2MandateVerifier, issue_ap2_mandate
from kavach.capabilities.mandate._internal.fake import issue_fake_mandate
from kavach.capabilities.mandate._internal.tokens import mandate_digest
from kavach.capabilities.policy import PolicyDecision, PolicyEngine, PolicyRuleSet
from kavach.capabilities.sdk_bridge import VerifiedAgent
from kavach.capabilities.storage import (
    AgentRegistrationRow,
    EventStore,
    MandateRevocationRow,
    MandateRow,
    WebhookSubscriptionRow,
    session_scope,
)
from kavach.composition.bus import EventBus
from kavach.events import new_event_id, utcnow
from kavach.events.schemas import (
    ActionExecuted,
    Mandate,
    MandateIssued,
    MandatePresented,
    MandateRevoked,
    StepUpResolved,
    TrustAssessment,
    TrustAssessmentEmitted,
    TrustDimension,
)
from kavach.events.schemas.monitor import AnomalyAcknowledged
from kavach.events.sufficiency_helpers import single_modality
from kavach.query.projections._tables import (
    AgentAnomalyCurrentRow,
    AgentTimelineRow,
    AgentTrustCurrentRow,
    StepUpQueueRow,
)


def _issue_ap2_stand_in(mandate: Mandate, key: bytes) -> str:
    """HS256 stand-in used when the AP2 SDK extra is not installed."""
    amount = 0
    for bound in mandate.constraints:
        if bound.path == "payment_amount.amount" and isinstance(bound.value, int):
            amount = bound.value
    return issue_ap2_mandate(
        {
            "mandate_id": mandate.mandate_id,
            "agent_id": mandate.agent_id,
            "originator_id": mandate.originator_id,
            "action_scope": list(mandate.action_scope),
            "payment_amount": {"currency": "INR", "amount": amount},
            "checkout_jwt": mandate.nonce,
            "constraints": [{"type": "amount_range", "max": amount}],
            "iat": int(mandate.issued_at.timestamp()),
            "exp": int(mandate.expires_at.timestamp()),
            "nonce": mandate.nonce,
        },
        key,
    )


def _credential_integrity_dimension(agent: VerifiedAgent) -> TrustDimension:
    """First trust dimension (ADR-0014): credential integrity, cold-start.

    Derives a value from the verification result. With no behavioural
    history yet, sufficiency is thin/cold and honestly labelled.
    """
    value = 0.85 if (agent.verified and agent.delegation_ok) else 0.1
    suff = single_modality(
        "credential_chain",
        band="thin",
        observations=1,
        reason="Single verified presentation; no behavioural history yet.",
    )
    return TrustDimension(
        name="credential_integrity",
        value=value,
        sufficiency=suff,
        contributors=["sdk_bridge:presentation"],
        reason=agent.reason or "Credential verification result.",
    )


class SubstrateService:
    """Transactional operations over the substrate."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        bus: EventBus,
        event_store: EventStore,
        audit_exporter: AuditExporter,
        policy_engines: dict[str, PolicyEngine],
        mandate_verifier: MandateVerifier | None = None,
        mandate_key: bytes = b"",
    ) -> None:
        self._session_factory = session_factory
        self._bus = bus
        self._event_store = event_store
        self._audit_exporter = audit_exporter
        self._policy_engines = policy_engines
        self._mandate_verifier = mandate_verifier
        self._mandate_key = mandate_key

    # -- writes -------------------------------------------------------------

    async def record_action(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        action_type: str,
        parameters: dict[str, Any],
        context: str | None = None,
    ) -> ActionExecuted:
        event = ActionExecuted(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            action_type=action_type,
            parameters=parameters,
            context=context,
        )
        async with session_scope(self._session_factory) as session:
            await self._bus.publish(session, event)
        return event

    async def decide(
        self,
        *,
        use_case: str,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        action_type: str,
        parameters: dict[str, Any],
        context: str | None = None,
        mandate_token: str | None = None,
    ) -> PolicyDecision:
        engine = self._policy_engines.get(use_case)
        if engine is None:
            raise KeyError(f"No policy engine for use case '{use_case}'.")
        severity = await self.current_anomaly_severity(tenant_id=tenant_id, agent_id=agent_id)
        verified = await self._verify_presented_mandate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            action_type=action_type,
            token=mandate_token,
        )
        decision = engine.evaluate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            action_type=action_type,
            parameters=parameters,
            context=context or use_case,
            verified_mandate=verified,
            anomaly_severity=severity,
        )
        async with session_scope(self._session_factory) as session:
            await self._bus.publish(session, decision.policy_evaluated_event)
            await self._bus.publish(session, decision.decision_event)
            if verified is not None and verified.mandate is not None:
                await self._bus.publish(
                    session,
                    MandatePresented(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        decision_id=decision.decision_id,
                        mandate_id=verified.mandate.mandate_id,
                        verified=verified.verified,
                        reason=verified.reason,
                    ),
                )
            if decision.step_up_event is not None:
                await self._bus.publish(session, decision.step_up_event)
        return decision

    async def issue_mandate(self, *, tenant_id: str, mandate: Mandate) -> MandateIssued:
        if self._mandate_verifier is None:
            raise RuntimeError("Mandate verifier is not configured.")
        if isinstance(self._mandate_verifier, AP2MandateVerifier):
            try:
                token = self._mandate_verifier.issue_chain(mandate)
            except ImportError:
                token = _issue_ap2_stand_in(mandate, self._mandate_key)
        else:
            token = issue_fake_mandate(mandate, self._mandate_key)
        event = MandateIssued(
            tenant_id=tenant_id,
            mandate_id=mandate.mandate_id,
            originator_id=mandate.originator_id,
            agent_id=mandate.agent_id,
            action_scope=list(mandate.action_scope),
            constraints=list(mandate.constraints),
            expires_at=mandate.expires_at,
            mandate_digest=mandate_digest(mandate),
            parent_mandate_id=mandate.parent_mandate_id,
        )
        async with session_scope(self._session_factory) as session:
            session.add(
                MandateRow(
                    tenant_id=tenant_id,
                    mandate_id=mandate.mandate_id,
                    agent_id=mandate.agent_id,
                    originator_id=mandate.originator_id,
                    token=token,
                    payload=mandate.model_dump(mode="json"),
                    parent_mandate_id=mandate.parent_mandate_id,
                    expires_at=mandate.expires_at,
                    created_at=utcnow(),
                )
            )
            await self._bus.publish(session, event)
        return event

    async def get_mandate(self, *, tenant_id: str, mandate_id: str) -> MandateRow | None:
        async with session_scope(self._session_factory) as session:
            return await session.get(MandateRow, (tenant_id, mandate_id))

    async def revoke_mandate(
        self,
        *,
        tenant_id: str,
        mandate_id: str,
        revoked_by: str,
        reason: str = "",
    ) -> MandateRevoked:
        async with session_scope(self._session_factory) as session:
            row = await session.get(MandateRow, (tenant_id, mandate_id))
            if row is None:
                raise KeyError(f"No mandate '{mandate_id}'.")
            existing = await session.get(MandateRevocationRow, (tenant_id, mandate_id))
            if existing is not None:
                raise ValueError(f"Mandate '{mandate_id}' already revoked.")
            session.add(
                MandateRevocationRow(
                    tenant_id=tenant_id,
                    mandate_id=mandate_id,
                    revoked_by=revoked_by,
                    reason=reason,
                    revoked_at=utcnow(),
                )
            )
            event = MandateRevoked(
                tenant_id=tenant_id,
                mandate_id=mandate_id,
                agent_id=row.agent_id,
                revoked_by=revoked_by,
                reason=reason,
            )
            await self._bus.publish(session, event)
        return event

    async def current_anomaly_severity(self, *, tenant_id: str, agent_id: str) -> str:
        async with session_scope(self._session_factory) as session:
            row = await session.get(AgentAnomalyCurrentRow, (tenant_id, agent_id))
        if row is None or row.status != "open":
            return "none"
        return row.severity

    async def acknowledge_anomaly(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        anomaly_id: str,
        resolution: str,
        operator_id: str,
        rationale: str = "",
    ) -> AnomalyAcknowledged:
        event = AnomalyAcknowledged(
            tenant_id=tenant_id,
            agent_id=agent_id,
            anomaly_id=anomaly_id,
            resolution=resolution,  # type: ignore[arg-type]
            operator_id=operator_id,
            rationale=rationale,
        )
        async with session_scope(self._session_factory) as session:
            await self._bus.publish(session, event)
        return event

    async def _verify_presented_mandate(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        action_type: str,
        token: str | None,
    ) -> VerifiedMandate | None:
        if token is None or self._mandate_verifier is None:
            return None
        revoked: set[str] = set()
        parent: Mandate | None = None
        async with session_scope(self._session_factory) as session:
            rows = (
                await session.execute(
                    select(MandateRevocationRow).where(MandateRevocationRow.tenant_id == tenant_id)
                )
            ).scalars()
            revoked = {row.mandate_id for row in rows}
        verified = self._mandate_verifier.verify(
            token,
            expected_agent_id=agent_id,
            expected_action=action_type,
            now=utcnow(),
            revoked_ids=frozenset(revoked),
            parent=parent,
        )
        if (
            verified.mandate is not None
            and verified.mandate.parent_mandate_id
            and not verified.chain_ok
        ):
            async with session_scope(self._session_factory) as session:
                parent_row = await session.get(
                    MandateRow, (tenant_id, verified.mandate.parent_mandate_id)
                )
            if parent_row is not None:
                parent = Mandate.model_validate(parent_row.payload)
                verified = self._mandate_verifier.verify(
                    token,
                    expected_agent_id=agent_id,
                    expected_action=action_type,
                    now=utcnow(),
                    revoked_ids=frozenset(revoked),
                    parent=parent,
                )
        return verified

    async def resolve_step_up(
        self,
        *,
        tenant_id: str,
        decision_id: str,
        resolution: str,
        operator_id: str,
        rationale: str = "",
    ) -> StepUpResolved:
        async with session_scope(self._session_factory) as session:
            row = await session.get(StepUpQueueRow, decision_id)
            if row is None:
                raise KeyError(f"No step-up found for decision '{decision_id}'.")
            if row.status != "pending":
                raise ValueError(f"Step-up '{decision_id}' already resolved.")
            final_outcome = "allow" if resolution == "approve" else "deny"
            event = StepUpResolved(
                tenant_id=tenant_id,
                agent_id=row.agent_id,
                decision_id=decision_id,
                resolution=resolution,  # type: ignore[arg-type]
                operator_id=operator_id,
                rationale=rationale,
                final_outcome=final_outcome,  # type: ignore[arg-type]
            )
            await self._bus.publish(session, event)
        return event

    async def assess_trust(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        context: str,
        agent: VerifiedAgent,
    ) -> TrustAssessmentEmitted:
        assessment = TrustAssessment(
            agent_id=agent_id,
            context=context,
            dimensions={
                "credential_integrity": _credential_integrity_dimension(agent),
            },
        )
        event = TrustAssessmentEmitted(
            tenant_id=tenant_id,
            agent_id=agent_id,
            context=context,
            assessment=assessment,
        )
        async with session_scope(self._session_factory) as session:
            await self._bus.publish(session, event)
        return event

    # -- reads --------------------------------------------------------------

    async def get_trust(
        self, *, tenant_id: str, agent_id: str, context: str
    ) -> AgentTrustCurrentRow | None:
        async with session_scope(self._session_factory) as session:
            return await session.get(AgentTrustCurrentRow, (tenant_id, agent_id, context))

    async def get_timeline(
        self, *, tenant_id: str, agent_id: str, limit: int = 50
    ) -> list[AgentTimelineRow]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(AgentTimelineRow)
                .where(
                    AgentTimelineRow.tenant_id == tenant_id,
                    AgentTimelineRow.agent_id == agent_id,
                )
                .order_by(AgentTimelineRow.seq.desc())
                .limit(limit)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def pending_step_ups(self, *, tenant_id: str) -> list[StepUpQueueRow]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(StepUpQueueRow)
                .where(
                    StepUpQueueRow.tenant_id == tenant_id,
                    StepUpQueueRow.status == "pending",
                )
                .order_by(StepUpQueueRow.requested_at)
            )
            return list((await session.execute(stmt)).scalars().all())

    async def export_audit(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        frm: datetime,
        to: datetime,
    ) -> AuditExport:
        async with session_scope(self._session_factory) as session:
            return await self._audit_exporter.export(
                session, tenant_id=tenant_id, agent_id=agent_id, frm=frm, to=to
            )

    def verify_export(self, export: AuditExport) -> bool:
        return self._audit_exporter.verify(export)

    # -- admin and webhooks -------------------------------------------------

    async def register_agent(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        display_name: str,
        use_case: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentRegistrationRow:
        async with session_scope(self._session_factory) as session:
            existing = await session.get(AgentRegistrationRow, (tenant_id, agent_id))
            if existing is not None:
                return existing
            row = AgentRegistrationRow(
                tenant_id=tenant_id,
                agent_id=agent_id,
                display_name=display_name,
                use_case=use_case,
                agent_metadata=metadata or {},
                registered_at=utcnow(),
            )
            session.add(row)
            await session.flush()
            return row

    def upload_policy(self, rule_set: PolicyRuleSet) -> int:
        """Install/replace a use case's rule set at runtime (ADR-0016)."""
        self._policy_engines[rule_set.use_case] = PolicyEngine(rule_set)
        return len(rule_set.rules)

    async def create_webhook_subscription(
        self,
        *,
        tenant_id: str,
        url: str,
        event_types: list[str],
        secret: str | None = None,
    ) -> WebhookSubscriptionRow:
        async with session_scope(self._session_factory) as session:
            row = WebhookSubscriptionRow(
                subscription_id=new_event_id(),
                tenant_id=tenant_id,
                url=url,
                event_types=event_types,
                secret=secret,
                active=True,
                created_at=utcnow(),
            )
            session.add(row)
            await session.flush()
            return row

    @property
    def now(self) -> datetime:
        return utcnow()
