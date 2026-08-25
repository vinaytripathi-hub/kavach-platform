"""Authentication, authorization, and RFC 7807 problem responses (ADR-0016).

Two principal classes: agents (Pramana credential, verified by the
sdk_bridge) and operators/admins (a Kavach-issued bearer token; the
prototype uses a shared operator token from configuration).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse

from kavach.capabilities.sdk_bridge import VerifiedAgent
from kavach.composition import Substrate


class ProblemError(Exception):
    """Raised to produce an RFC 7807 problem+json response."""

    def __init__(self, status: int, code: str, title: str, detail: str | None = None) -> None:
        super().__init__(title)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail

    def to_response(self) -> JSONResponse:
        body = {
            "type": "about:blank",
            "title": self.title,
            "status": self.status,
            "code": self.code,
        }
        if self.detail:
            body["detail"] = self.detail
        return JSONResponse(
            status_code=self.status,
            content=body,
            media_type="application/problem+json",
        )


@dataclass
class AgentPrincipal:
    agent_id: str
    tenant_id: str
    verified: VerifiedAgent


@dataclass
class OperatorPrincipal:
    operator_id: str
    tenant_id: str


def get_substrate(request: Request) -> Substrate:
    substrate: Substrate | None = getattr(request.app.state, "substrate", None)
    if substrate is None:  # pragma: no cover - defensive
        raise ProblemError(500, "internal_error", "Substrate not initialised.")
    return substrate


def get_tenant(x_kavach_tenant: str = Header(default="default")) -> str:
    return x_kavach_tenant


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ProblemError(401, "unauthorized", "Missing or malformed bearer credential.")
    return authorization[7:].strip()


def require_agent(
    request: Request,
    tenant_id: str = Depends(get_tenant),
    authorization: str | None = Header(default=None),
) -> AgentPrincipal:
    substrate = get_substrate(request)
    token = _bearer(authorization)
    verified = substrate.verifier.verify(
        token, expected_audience=substrate.config.expected_audience
    )
    if not verified.verified:
        raise ProblemError(401, "unauthorized", "Agent credential not verified.", verified.reason)
    return AgentPrincipal(agent_id=verified.agent_id, tenant_id=tenant_id, verified=verified)


def require_operator(
    request: Request,
    tenant_id: str = Depends(get_tenant),
    authorization: str | None = Header(default=None),
    x_kavach_operator: str = Header(default="operator"),
) -> OperatorPrincipal:
    substrate = get_substrate(request)
    token = _bearer(authorization)
    if token != substrate.config.operator_token:
        raise ProblemError(403, "forbidden", "Operator token invalid.")
    return OperatorPrincipal(operator_id=x_kavach_operator, tenant_id=tenant_id)
