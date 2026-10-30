"""Authentication, authorization, and RFC 7807 problem responses.

Agents present either a holder credential (sdk_bridge) or a Kavach
session JWT (ADR-0020). Operators present an OIDC access token
(ADR-0021). Both are checked for lifetime and, for agents, revocation
before any policy effect.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse

from kavach.api.problems import problem_type
from kavach.capabilities.credentials import enforce_temporal, is_session_token, verify_session
from kavach.capabilities.sdk_bridge import VerifiedAgent
from kavach.capabilities.storage import AgentRevocationRow, CredentialRevocationRow, session_scope
from kavach.composition import Substrate
from kavach.events import utcnow
from kavach.identity.oidc import OperatorClaims, OperatorIdentityVerifier

_OPERATOR_ROLES = frozenset({"operator", "admin"})
_AUDITOR_ROLES = frozenset({"auditor", "operator", "admin"})
_ADMIN_ROLES = frozenset({"admin"})


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
            "type": problem_type(self.code),
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
    role: str


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


def _verify_presented(substrate: Substrate, token: str) -> VerifiedAgent:
    if is_session_token(token):
        return verify_session(
            token,
            substrate.config.jwt_secret.encode("utf-8"),
            substrate.config.expected_audience,
        )
    return substrate.verifier.verify(token, expected_audience=substrate.config.expected_audience)


async def require_agent(
    request: Request,
    tenant_id: str = Depends(get_tenant),
    authorization: str | None = Header(default=None),
) -> AgentPrincipal:
    substrate = get_substrate(request)
    token = _bearer(authorization)
    verified = _verify_presented(substrate, token)
    if not verified.verified:
        raise ProblemError(401, "unauthorized", "Agent credential not verified.", verified.reason)
    temporal = enforce_temporal(verified, utcnow())
    if temporal == "credential_expired":
        raise ProblemError(401, "credential_expired", "Agent credential expired.", verified.reason)
    if temporal == "credential_not_yet_valid":
        raise ProblemError(
            401, "credential_not_yet_valid", "Agent credential not yet valid.", verified.reason
        )
    async with session_scope(substrate.session_factory) as session:
        agent_hit = await session.get(AgentRevocationRow, (tenant_id, verified.agent_id))
        if agent_hit is not None:
            raise ProblemError(401, "agent_revoked", "Agent is revoked.")
        if verified.credential_id:
            cred_hit = await session.get(
                CredentialRevocationRow, (tenant_id, verified.credential_id)
            )
            if cred_hit is not None:
                raise ProblemError(401, "credential_revoked", "Credential is revoked.")
    return AgentPrincipal(agent_id=verified.agent_id, tenant_id=tenant_id, verified=verified)


def _operator_verifier(request: Request) -> OperatorIdentityVerifier:
    substrate = get_substrate(request)
    cached: OperatorIdentityVerifier | None = getattr(request.app.state, "operator_verifier", None)
    if cached is None:
        cached = OperatorIdentityVerifier.from_config(substrate.config)
        request.app.state.operator_verifier = cached
    return cached


def _authenticate_operator(
    request: Request, authorization: str | None, tenant_id: str
) -> OperatorClaims:
    token = _bearer(authorization)
    verifier = _operator_verifier(request)
    if not verifier.configured:
        raise ProblemError(401, "unauthorized", "Operator identity is not configured.")
    try:
        claims = verifier.verify(token)
    except jwt.ExpiredSignatureError as exc:
        raise ProblemError(401, "credential_expired", "Operator credential expired.") from exc
    except jwt.ImmatureSignatureError as exc:
        raise ProblemError(
            401, "credential_not_yet_valid", "Operator credential not yet valid."
        ) from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise ProblemError(
            401, "unauthorized", "Operator credential not verified.", str(exc)
        ) from exc
    if claims.tenant != tenant_id:
        raise ProblemError(403, "forbidden", "Token tenant does not match X-Kavach-Tenant.")
    return claims


def _require_role(
    request: Request,
    authorization: str | None,
    tenant_id: str,
    allowed: frozenset[str],
) -> OperatorPrincipal:
    claims = _authenticate_operator(request, authorization, tenant_id)
    role = next((item for item in ("admin", "operator", "auditor") if item in claims.roles), "")
    if role not in allowed:
        raise ProblemError(403, "forbidden", "Operator role is not permitted for this route.")
    return OperatorPrincipal(operator_id=claims.subject, tenant_id=tenant_id, role=role)


def require_operator(
    request: Request,
    tenant_id: str = Depends(get_tenant),
    authorization: str | None = Header(default=None),
) -> OperatorPrincipal:
    """Role ``operator`` or ``admin``."""
    return _require_role(request, authorization, tenant_id, _OPERATOR_ROLES)


def require_auditor(
    request: Request,
    tenant_id: str = Depends(get_tenant),
    authorization: str | None = Header(default=None),
) -> OperatorPrincipal:
    """Role ``auditor``, ``operator``, or ``admin`` (read paths)."""
    return _require_role(request, authorization, tenant_id, _AUDITOR_ROLES)


def require_admin(
    request: Request,
    tenant_id: str = Depends(get_tenant),
    authorization: str | None = Header(default=None),
) -> OperatorPrincipal:
    """Role ``admin`` only."""
    return _require_role(request, authorization, tenant_id, _ADMIN_ROLES)
