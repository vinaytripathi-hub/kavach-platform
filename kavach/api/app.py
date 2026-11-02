"""FastAPI application factory (ADR-0016).

``create_app`` builds the application around a pre-wired ``Substrate``.
The caller is responsible for creating the schema (Alembic on-prem,
``create_schema`` for tests/demos) before serving traffic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import kavach
from kavach.api import models as m
from kavach.api.security import (
    AgentPrincipal,
    OperatorPrincipal,
    ProblemError,
    _bearer,
    get_substrate,
    require_admin,
    require_agent,
    require_auditor,
    require_operator,
)
from kavach.capabilities.storage import session_scope
from kavach.composition import Substrate
from kavach.events import new_event_id
from kavach.events.schemas import Evidence


def create_app(substrate: Substrate) -> FastAPI:  # noqa: PLR0915
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if substrate.config.auto_create_schema:
            await substrate.create_schema()
        yield
        await substrate.dispose()

    app = FastAPI(
        title="Kavach Platform API",
        version="1.0.0",
        description="Agent Accountability for Indian BFSI (ADR-0016).",
        lifespan=lifespan,
    )
    app.state.substrate = substrate
    app.state.audit_exports = {}

    @app.exception_handler(ProblemError)
    async def _problem_handler(_req: Request, exc: ProblemError) -> JSONResponse:
        return exc.to_response()

    async def _idempotent(
        sub: Substrate,
        tenant: str,
        key: str | None,
        success_status: int,
        produce: Callable[[], Awaitable[BaseModel]],
    ) -> Response:
        """Run ``produce`` once per (tenant, key); replay returns the original."""
        if key:
            async with session_scope(sub.session_factory) as session:
                hit = await sub.idempotency_store.get(session, tenant, key)
            if hit is not None:
                status, body = hit
                return JSONResponse(body, status_code=status)
        result = await produce()
        body = result.model_dump(mode="json")
        if key:
            async with session_scope(sub.session_factory) as session:
                await sub.idempotency_store.put(session, tenant, key, success_status, body)
        return JSONResponse(body, status_code=success_status)

    # -- system -------------------------------------------------------------

    @app.get("/v1/health", response_model=m.HealthStatus, tags=["system"])
    async def health() -> m.HealthStatus:
        return m.HealthStatus(status="ok", version=kavach.__version__)

    # -- ingress ------------------------------------------------------------

    @app.post("/v1/agents/{agent_id}/actions", tags=["ingress"], status_code=201)
    async def record_action(
        agent_id: str,
        body: m.ActionRecordRequest,
        request: Request,
        principal: AgentPrincipal = Depends(require_agent),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> Response:
        sub = get_substrate(request)
        _ensure_same_agent(principal, agent_id)

        async def produce() -> m.EventReceipt:
            event = await sub.service.record_action(
                tenant_id=principal.tenant_id,
                agent_id=agent_id,
                session_id=body.session_id,
                action_type=body.action_type,
                parameters=body.parameters,
                context=body.context,
            )
            return m.EventReceipt(
                event_id=event.event_id,
                event_type=event.event_type,
                schema_version=event.schema_version,
                recorded_at=event.occurred_at,
            )

        return await _idempotent(sub, principal.tenant_id, idempotency_key, 201, produce)

    # -- decisions ----------------------------------------------------------

    @app.post("/v1/agents/{agent_id}/decisions", tags=["decisions"])
    async def request_decision(
        agent_id: str,
        body: m.DecisionRequest,
        request: Request,
        principal: AgentPrincipal = Depends(require_agent),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        mandate_token: str | None = Header(default=None, alias="X-Kavach-Mandate"),
    ) -> Response:
        sub = get_substrate(request)
        _ensure_same_agent(principal, agent_id)

        async def produce() -> m.DecisionResponse:
            try:
                decision = await sub.service.decide(
                    use_case=body.use_case,
                    tenant_id=principal.tenant_id,
                    agent_id=agent_id,
                    session_id=body.session_id,
                    action_type=body.action_type,
                    parameters=body.parameters,
                    context=body.context,
                    mandate_token=mandate_token,
                )
            except KeyError as exc:
                raise ProblemError(422, "validation_error", "Unknown use case.", str(exc)) from exc
            # Emit a trust assessment off the verified credential so the
            # console's trust view reflects the agent (ADR-0014).
            await sub.service.assess_trust(
                tenant_id=principal.tenant_id,
                agent_id=agent_id,
                context=body.use_case,
                agent=principal.verified,
            )
            ev = decision.decision_event
            step_up = None
            if decision.step_up_event is not None:
                step_up = m.StepUpInfo(
                    reason=decision.step_up_event.reason,
                    required_role=decision.step_up_event.required_role,
                )
            return m.DecisionResponse(
                decision_id=decision.decision_id,
                outcome=decision.outcome,
                rule_id=decision.matched_rule_id,
                evidence=ev.evidence,
                reasoning=ev.reasoning,
                confidence=ev.confidence,
                data_sufficiency=ev.data_sufficiency,
                decided_by=ev.decided_by,
                step_up=step_up,
            )

        return await _idempotent(sub, principal.tenant_id, idempotency_key, 200, produce)

    @app.post("/v1/decisions/{decision_id}/step-up/resolve", tags=["decisions"])
    async def resolve_step_up(
        decision_id: str,
        body: m.StepUpResolveRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> m.DecisionResponse:
        sub = get_substrate(request)
        try:
            resolved = await sub.service.resolve_step_up(
                tenant_id=principal.tenant_id,
                decision_id=decision_id,
                resolution=body.resolution,
                operator_id=body.operator_id,
                rationale=body.rationale,
            )
        except KeyError as exc:
            raise ProblemError(404, "not_found", "Step-up not found.", str(exc)) from exc
        except ValueError as exc:
            raise ProblemError(
                409, "step_up_already_resolved", "Step-up already resolved.", str(exc)
            ) from exc
        from kavach.events.decision_helpers import human_reasoning
        from kavach.events.schemas import rule_deterministic

        return m.DecisionResponse(
            decision_id=decision_id,
            outcome=resolved.final_outcome,
            evidence=_empty_evidence(),
            reasoning=human_reasoning(
                f"Operator {resolved.operator_id} {resolved.resolution}d the step-up."
            ),
            confidence=rule_deterministic(),
            decided_by=f"operator:{resolved.operator_id}",
        )

    @app.get("/v1/step-ups", tags=["decisions"])
    async def list_step_ups(
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> m.StepUpQueuePage:
        sub = get_substrate(request)
        rows = await sub.service.pending_step_ups(tenant_id=principal.tenant_id)
        return m.StepUpQueuePage(
            items=[
                m.StepUpQueueItem(
                    decision_id=r.decision_id,
                    agent_id=r.agent_id,
                    action_type=r.action_type,
                    reason=r.reason,
                    required_role=r.required_role,
                    status=r.status,
                    requested_at=r.requested_at,
                )
                for r in rows
            ]
        )

    # -- trust + timeline ---------------------------------------------------

    @app.get("/v1/agents/{agent_id}/trust", tags=["trust"])
    async def get_trust(
        agent_id: str,
        request: Request,
        context: str = "customer_service",
        principal: OperatorPrincipal = Depends(require_auditor),
    ) -> m.TrustResponse:
        sub = get_substrate(request)
        row = await sub.service.get_trust(
            tenant_id=principal.tenant_id, agent_id=agent_id, context=context
        )
        if row is None:
            raise ProblemError(404, "not_found", "No trust assessment for agent.")
        return m.TrustResponse(
            agent_id=row.agent_id,
            context=row.context,
            dimensions=row.dimensions,
            composed_scalar=row.composed_scalar,
            assessed_at=row.assessed_at,
        )

    @app.get("/v1/agents/{agent_id}/timeline", tags=["trust"])
    async def get_timeline(
        agent_id: str,
        request: Request,
        limit: int = 50,
        principal: OperatorPrincipal = Depends(require_auditor),
    ) -> m.TimelinePage:
        sub = get_substrate(request)
        rows = await sub.service.get_timeline(
            tenant_id=principal.tenant_id, agent_id=agent_id, limit=limit
        )
        items = [
            m.TimelineEntry(
                event_id=r.event_id,
                event_type=r.event_type,
                occurred_at=r.occurred_at,
                summary=r.summary,
                outcome=r.outcome,
            )
            for r in rows
        ]
        return m.TimelinePage(items=items)

    # -- audit export -------------------------------------------------------

    @app.post("/v1/audit/exports", tags=["audit"], status_code=202)
    async def request_audit_export(
        body: m.AuditExportRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_auditor),
    ) -> m.AuditExportStatus:
        sub = get_substrate(request)
        export = await sub.service.export_audit(
            tenant_id=principal.tenant_id,
            agent_id=body.agent_id,
            frm=body.frm,
            to=body.to,
        )
        export_id = new_event_id()
        status = m.AuditExportStatus(
            export_id=export_id,
            status="ready",
            record_count=export.record_count,
            chain_head=(
                export.signature_manifest.chain_head if export.signature_manifest else None
            ),
            signature_manifest=export.signature_manifest,
            records=export.records,
        )
        request.app.state.audit_exports[export_id] = status
        return status

    @app.get("/v1/audit/exports/{export_id}", tags=["audit"])
    async def get_audit_export(
        export_id: str,
        request: Request,
        principal: OperatorPrincipal = Depends(require_auditor),
    ) -> m.AuditExportStatus:
        del principal
        status: m.AuditExportStatus | None = request.app.state.audit_exports.get(export_id)
        if status is None:
            raise ProblemError(404, "not_found", "Export not found.")
        return status

    # -- mandates -----------------------------------------------------------

    @app.post("/v1/mandates", tags=["mandates"], status_code=201)
    async def issue_mandate(
        body: m.MandateIssueRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> m.MandateIssueResult:
        from kavach.events.schemas import Mandate, MandateConstraint

        sub = get_substrate(request)
        mandate = Mandate(
            mandate_id=body.mandate_id,
            originator_id=body.originator_id,
            originator_kind=body.originator_kind,  # type: ignore[arg-type]
            agent_id=body.agent_id,
            action_scope=body.action_scope,
            constraints=[
                MandateConstraint(path=c.path, operator=c.operator, value=c.value)  # type: ignore[arg-type]
                for c in body.constraints
            ],
            expires_at=body.expires_at,
            parent_mandate_id=body.parent_mandate_id,
            nonce=body.nonce,
        )
        try:
            event = await sub.service.issue_mandate(tenant_id=principal.tenant_id, mandate=mandate)
        except ValueError as exc:
            raise ProblemError(
                409, "mandate_already_exists", "Mandate already exists.", str(exc)
            ) from exc
        stored = await sub.service.get_mandate(
            tenant_id=principal.tenant_id, mandate_id=body.mandate_id
        )
        return m.MandateIssueResult(
            mandate_id=event.mandate_id,
            token=stored.token if stored is not None else "",
            mandate_digest=event.mandate_digest,
        )

    @app.get("/v1/mandates/{mandate_id}", tags=["mandates"])
    async def get_mandate(
        mandate_id: str,
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> m.MandateView:
        sub = get_substrate(request)
        row = await sub.service.get_mandate(tenant_id=principal.tenant_id, mandate_id=mandate_id)
        if row is None:
            raise ProblemError(404, "not_found", "Mandate not found.")
        return m.MandateView(
            mandate_id=row.mandate_id,
            agent_id=row.agent_id,
            originator_id=row.originator_id,
            expires_at=row.expires_at,
            payload=row.payload,
        )

    @app.post("/v1/mandates/{mandate_id}/revoke", tags=["mandates"])
    async def revoke_mandate(
        mandate_id: str,
        body: m.MandateRevokeRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> dict[str, str]:
        sub = get_substrate(request)
        try:
            event = await sub.service.revoke_mandate(
                tenant_id=principal.tenant_id,
                mandate_id=mandate_id,
                revoked_by=body.revoked_by,
                reason=body.reason,
            )
        except KeyError as exc:
            raise ProblemError(404, "not_found", "Mandate not found.", str(exc)) from exc
        except ValueError as exc:
            raise ProblemError(
                409, "already_revoked", "Mandate already revoked.", str(exc)
            ) from exc
        return {"mandate_id": event.mandate_id, "status": "revoked"}

    @app.post("/v1/agents/{agent_id}/credentials", tags=["credentials"])
    async def issue_credentials(
        agent_id: str,
        body: m.CredentialIssueRequest,
        request: Request,
        principal: AgentPrincipal = Depends(require_agent),
        authorization: str | None = Header(default=None),
    ) -> m.CredentialIssueResult:
        _ensure_same_agent(principal, agent_id)
        if principal.verified.credential_id:
            raise ProblemError(
                401,
                "unauthorized",
                "Present a holder credential, not a session credential.",
            )
        sub = get_substrate(request)
        try:
            issued = await sub.service.issue_session_credential(
                tenant_id=principal.tenant_id,
                agent_id=agent_id,
                scopes=list(principal.verified.scopes),
                holder_token=_bearer(authorization),
                ttl_seconds=body.ttl_seconds,
            )
        except PermissionError as exc:
            raise ProblemError(401, "agent_revoked", "Agent is revoked.", str(exc)) from exc
        except ValueError as exc:
            raise ProblemError(
                422, "validation_error", "Invalid credential request.", str(exc)
            ) from exc
        return m.CredentialIssueResult(
            credential_id=issued.credential_id,
            session_id=issued.session_id,
            token=issued.token,
            expires_at=issued.expires_at,
            refresh_token=issued.refresh_token,
            refresh_expires_at=issued.refresh_expires_at,
        )

    @app.post("/v1/credentials/refresh", tags=["credentials"])
    async def refresh_credentials(
        request: Request,
        authorization: str | None = Header(default=None),
        tenant_id: str = Header(default="default", alias="X-Kavach-Tenant"),
    ) -> m.CredentialIssueResult:
        sub = get_substrate(request)
        token = _bearer(authorization)
        try:
            issued = await sub.service.refresh_session_credential(
                tenant_id=tenant_id, refresh_token=token
            )
        except PermissionError as exc:
            message = str(exc)
            code = "credential_expired" if "expired" in message else "credential_revoked"
            raise ProblemError(401, code, message) from exc
        except ValueError as exc:
            raise ProblemError(401, "unauthorized", "Refresh token is invalid.", str(exc)) from exc
        return m.CredentialIssueResult(
            credential_id=issued.credential_id,
            session_id=issued.session_id,
            token=issued.token,
            expires_at=issued.expires_at,
            refresh_token=issued.refresh_token,
            refresh_expires_at=issued.refresh_expires_at,
        )

    @app.post("/v1/agents/{agent_id}/revoke", tags=["admin"])
    async def revoke_agent(
        agent_id: str,
        body: m.RevocationRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_admin),
    ) -> dict[str, str]:
        sub = get_substrate(request)
        try:
            event = await sub.service.revoke_agent(
                tenant_id=principal.tenant_id,
                agent_id=agent_id,
                revoked_by=body.revoked_by,
                reason=body.reason,
            )
        except ValueError as exc:
            raise ProblemError(409, "already_revoked", "Agent already revoked.", str(exc)) from exc
        return {"agent_id": event.agent_id, "status": "revoked"}

    @app.post("/v1/credentials/{credential_id}/revoke", tags=["admin"])
    async def revoke_credential(
        credential_id: str,
        body: m.RevocationRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_admin),
    ) -> dict[str, str]:
        sub = get_substrate(request)
        try:
            event = await sub.service.revoke_credential(
                tenant_id=principal.tenant_id,
                credential_id=credential_id,
                revoked_by=body.revoked_by,
                reason=body.reason,
            )
        except KeyError as exc:
            raise ProblemError(404, "not_found", "Credential not found.", str(exc)) from exc
        except ValueError as exc:
            raise ProblemError(
                409, "already_revoked", "Credential already revoked.", str(exc)
            ) from exc
        return {"credential_id": event.credential_id, "status": "revoked"}

    @app.get("/v1/agents/{agent_id}/anomalies", tags=["monitor"])
    async def list_anomalies(
        agent_id: str,
        request: Request,
        principal: OperatorPrincipal = Depends(require_auditor),
    ) -> dict[str, str]:
        sub = get_substrate(request)
        severity = await sub.service.current_anomaly_severity(
            tenant_id=principal.tenant_id, agent_id=agent_id
        )
        return {"agent_id": agent_id, "severity": severity}

    @app.post("/v1/anomalies/{anomaly_id}/acknowledge", tags=["monitor"])
    async def acknowledge_anomaly(
        anomaly_id: str,
        body: m.AnomalyAckRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_operator),
    ) -> dict[str, str]:
        sub = get_substrate(request)
        event = await sub.service.acknowledge_anomaly(
            tenant_id=principal.tenant_id,
            agent_id=body.agent_id,
            anomaly_id=anomaly_id,
            resolution=body.resolution,
            operator_id=body.operator_id,
            rationale=body.rationale,
        )
        return {"anomaly_id": event.anomaly_id, "resolution": event.resolution}

    @app.get("/v1/agents/{agent_id}/metrics", tags=["monitor"])
    async def agent_metrics(
        agent_id: str,
        request: Request,
        principal: AgentPrincipal = Depends(require_agent),
    ) -> dict[str, str]:
        sub = get_substrate(request)
        _ensure_same_agent(principal, agent_id)
        severity = await sub.service.current_anomaly_severity(
            tenant_id=principal.tenant_id, agent_id=agent_id
        )
        return {"agent_id": agent_id, "anomaly_severity": severity}

    # -- webhooks + admin ---------------------------------------------------

    @app.post("/v1/webhooks/subscriptions", tags=["webhooks"], status_code=201)
    async def create_subscription(
        body: m.WebhookSubscriptionRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_admin),
    ) -> m.WebhookSubscription:
        sub = get_substrate(request)
        row = await sub.service.create_webhook_subscription(
            tenant_id=principal.tenant_id,
            url=body.url,
            event_types=body.event_types,
            secret=body.secret,
        )
        return m.WebhookSubscription(
            subscription_id=row.subscription_id,
            url=row.url,
            event_types=row.event_types,
            active=row.active,
            created_at=row.created_at,
        )

    @app.post("/v1/admin/agents", tags=["admin"], status_code=201)
    async def register_agent(
        body: m.AgentRegistrationRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_admin),
    ) -> m.AgentRegistration:
        sub = get_substrate(request)
        row = await sub.service.register_agent(
            tenant_id=principal.tenant_id,
            agent_id=body.agent_id,
            display_name=body.display_name,
            use_case=body.use_case,
            metadata=body.metadata,
        )
        return m.AgentRegistration(
            agent_id=row.agent_id,
            display_name=row.display_name,
            use_case=row.use_case,
            registered_at=row.registered_at,
        )

    @app.post("/v1/admin/policies", tags=["admin"], status_code=201)
    async def upload_policy(
        body: m.PolicyUploadRequest,
        request: Request,
        principal: OperatorPrincipal = Depends(require_admin),
    ) -> m.PolicyUploadResult:
        del principal
        from kavach.capabilities.policy import PolicyRuleSet

        sub = get_substrate(request)
        rule_set = PolicyRuleSet(
            use_case=body.use_case,
            version=body.version,
            default_effect=body.default_effect,  # type: ignore[arg-type]
            default_step_up_role=body.default_step_up_role,
            rules=body.rules,
        )
        count = sub.service.upload_policy(rule_set)
        return m.PolicyUploadResult(
            use_case=body.use_case,
            version=body.version,
            rule_count=count,
            accepted_at=sub.service.now,
        )

    return app


def _ensure_same_agent(principal: AgentPrincipal, agent_id: str) -> None:
    if principal.agent_id != agent_id:
        raise ProblemError(
            403,
            "forbidden",
            "Credential does not authorize acting as this agent.",
            f"Token agent '{principal.agent_id}' != path agent '{agent_id}'.",
        )


def _empty_evidence() -> Evidence:
    return Evidence(attributes={})
