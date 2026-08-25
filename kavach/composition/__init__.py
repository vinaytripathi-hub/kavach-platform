"""Composition layer — wires capabilities into a usable substrate (ADR-0007).

``build_substrate`` is the single place that instantiates capabilities and
connects them: the event store and audit chain writer feed the event bus;
projection handlers subscribe to the bus; use-case rule providers become
policy engines; the SDK-bridge verifier is selected by configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from kavach.capabilities.audit import AuditChainWriter, AuditExporter
from kavach.capabilities.policy import PolicyEngine, PolicyRuleProvider
from kavach.capabilities.sdk_bridge import CredentialVerifier, make_verifier
from kavach.capabilities.storage import (
    EventStore,
    IdempotencyStore,
    create_all,
    make_engine,
    make_session_factory,
)
from kavach.composition.bus import EventBus, ProjectionHandler
from kavach.composition.config import SubstrateConfig
from kavach.composition.service import SubstrateService
from kavach.query.projections.agent_timeline import AgentTimelineProjection
from kavach.query.projections.agent_trust_current import AgentTrustCurrentProjection
from kavach.query.projections.decision_log import DecisionLogProjection
from kavach.query.projections.step_up_queue import StepUpQueueProjection


@dataclass
class Substrate:
    """A fully-wired substrate instance."""

    config: SubstrateConfig
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    event_store: EventStore
    idempotency_store: IdempotencyStore
    bus: EventBus
    audit_exporter: AuditExporter
    verifier: CredentialVerifier
    service: SubstrateService
    policy_engines: dict[str, PolicyEngine]
    projections: list[ProjectionHandler] = field(default_factory=list)

    async def create_schema(self) -> None:
        """Create all tables (offline/demo/tests; on-prem uses Alembic)."""
        await create_all(self.engine)

    async def dispose(self) -> None:
        await self.engine.dispose()


def build_substrate(
    config: SubstrateConfig | None = None,
    rule_providers: list[PolicyRuleProvider] | None = None,
) -> Substrate:
    """Instantiate and wire the substrate from configuration."""
    config = config or SubstrateConfig()
    rule_providers = rule_providers or []

    engine = make_engine(config.database_url, echo=config.echo_sql)
    session_factory = make_session_factory(engine)

    event_store = EventStore()
    idempotency_store = IdempotencyStore()
    audit_writer = AuditChainWriter(config.audit_key_bytes)
    audit_exporter = AuditExporter(config.audit_key_bytes)

    projections: list[ProjectionHandler] = [
        AgentTimelineProjection(),
        AgentTrustCurrentProjection(),
        DecisionLogProjection(),
        StepUpQueueProjection(),
    ]
    handlers: list[ProjectionHandler] = [audit_writer, *projections]
    bus = EventBus(store=event_store, handlers=handlers)

    policy_engines = {
        provider.use_case: PolicyEngine(provider.rule_set()) for provider in rule_providers
    }

    verifier = make_verifier(config.sdk_bridge_mode)

    service = SubstrateService(
        session_factory=session_factory,
        bus=bus,
        event_store=event_store,
        audit_exporter=audit_exporter,
        policy_engines=policy_engines,
    )

    return Substrate(
        config=config,
        engine=engine,
        session_factory=session_factory,
        event_store=event_store,
        idempotency_store=idempotency_store,
        bus=bus,
        audit_exporter=audit_exporter,
        verifier=verifier,
        service=service,
        policy_engines=policy_engines,
        projections=projections,
    )


__all__ = [
    "EventBus",
    "ProjectionHandler",
    "Substrate",
    "SubstrateConfig",
    "SubstrateService",
    "build_substrate",
]
