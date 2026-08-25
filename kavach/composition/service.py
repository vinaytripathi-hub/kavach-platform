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
from kavach.capabilities.policy import PolicyDecision, PolicyEngine, PolicyRuleSet
from kavach.capabilities.sdk_bridge import VerifiedAgent
from kavach.capabilities.storage import (
    AgentRegistrationRow,
    EventStore,
    WebhookSubscriptionRow,
    session_scope,
)
from kavach.composition.bus import EventBus
from kavach.events import new_event_id, utcnow
from kavach.events.schemas import (
    ActionExecuted,
    StepUpResolved,
    TrustAssessment,
    TrustAssessmentEmitted,
    TrustDimension,
)
from kavach.events.sufficiency_helpers import single_modality
from kavach.query.projections._tables import (
    AgentTimelineRow,
    AgentTrustCurrentRow,
    StepUpQueueRow,
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
    ) -> None:
        self._session_factory = session_factory
        self._bus = bus
        self._event_store = event_store
        self._audit_exporter = audit_exporter
        self._policy_engines = policy_engines

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
    ) -> PolicyDecision:
        engine = self._policy_engines.get(use_case)
        if engine is None:
            raise KeyError(f"No policy engine for use case '{use_case}'.")
        decision = engine.evaluate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            action_type=action_type,
            parameters=parameters,
            context=context or use_case,
        )
        async with session_scope(self._session_factory) as session:
            await self._bus.publish(session, decision.policy_evaluated_event)
            await self._bus.publish(session, decision.decision_event)
            if decision.step_up_event is not None:
                await self._bus.publish(session, decision.step_up_event)
        return decision

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
