"""Short-lived Kavach session credentials (ADR-0020).

The holder credential (Pramana presentation, or the offline ``agent:``
grammar) proves who the agent is. This capability mints a separate
Kavach-signed session JWT, bound to a session, with ``nbf``/``exp`` and
a revocable ``jti``. TTL is capped at 15 minutes. A refresh token
rotates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from kavach.capabilities.sdk_bridge.contracts import VerifiedAgent
from kavach.events import utcnow

SESSION_TYP = "kavach-session"
REFRESH_TYP = "kavach-refresh"
_JWT_DOT_COUNT = 2
MAX_TTL_SECONDS = 900
_REFRESH_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class IssuedCredential:
    """A session JWT plus the refresh token that rotates it."""

    token: str
    credential_id: str
    session_id: str
    expires_at: datetime
    refresh_token: str
    refresh_credential_id: str
    refresh_expires_at: datetime
    scopes: list[str]


@dataclass(frozen=True)
class RefreshClaims:
    """Verified claims of a refresh token. Temporal checks are separate."""

    agent_id: str
    session_id: str
    credential_id: str
    scopes: list[str]
    expires_at: datetime | None
    not_before: datetime | None


def clamp_ttl(requested: int | None, configured_max: int) -> int:
    """Return a TTL in seconds, never above 15 minutes or ``configured_max``."""
    cap = min(max(configured_max, 1), MAX_TTL_SECONDS)
    if requested is None:
        return cap
    if requested <= 0:
        raise ValueError("ttl_seconds must be positive.")
    return min(requested, cap)


def mint_session(
    *,
    agent_id: str,
    scopes: list[str],
    audience: str,
    key: bytes,
    ttl_seconds: int,
    session_id: str | None = None,
    now: datetime | None = None,
    not_before: datetime | None = None,
    expires_at: datetime | None = None,
) -> IssuedCredential:
    """Mint a session JWT and a rotating refresh token."""
    issued_at = now or utcnow()
    nbf = not_before or issued_at
    exp = expires_at or (issued_at + timedelta(seconds=clamp_ttl(ttl_seconds, MAX_TTL_SECONDS)))
    sid = session_id or str(uuid.uuid4())
    credential_id = str(uuid.uuid4())
    refresh_id = str(uuid.uuid4())
    refresh_exp = issued_at + timedelta(seconds=_REFRESH_TTL_SECONDS)
    token = _encode(
        {
            "typ": SESSION_TYP,
            "sub": agent_id,
            "sid": sid,
            "jti": credential_id,
            "scopes": list(scopes),
            "aud": audience,
            "iat": int(issued_at.timestamp()),
            "nbf": int(nbf.timestamp()),
            "exp": int(exp.timestamp()),
        },
        key,
    )
    refresh = _encode(
        {
            "typ": REFRESH_TYP,
            "sub": agent_id,
            "sid": sid,
            "jti": refresh_id,
            "scopes": list(scopes),
            "aud": audience,
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
            "exp": int(refresh_exp.timestamp()),
        },
        key,
    )
    return IssuedCredential(
        token=token,
        credential_id=credential_id,
        session_id=sid,
        expires_at=exp,
        refresh_token=refresh,
        refresh_credential_id=refresh_id,
        refresh_expires_at=refresh_exp,
        scopes=list(scopes),
    )


def verify_session(token: str, key: bytes, audience: str) -> VerifiedAgent:
    """Verify a session JWT. Expiry is reported, not rejected here.

    ``require_agent`` turns ``expires_at`` / ``not_before`` into the
    ``credential_expired`` and ``credential_not_yet_valid`` problem types.
    Signature and audience failures are a plain unverified result.
    """
    claims = _decode(token, key, audience)
    if claims is None or claims.get("typ") != SESSION_TYP:
        return VerifiedAgent(
            agent_id="",
            verified=False,
            reason="Not a Kavach session credential.",
        )
    scopes = claims.get("scopes")
    return VerifiedAgent(
        agent_id=str(claims.get("sub") or ""),
        verified=True,
        scopes=list(scopes) if isinstance(scopes, list) else [],
        expires_at=_from_unix(claims.get("exp")),
        not_before=_from_unix(claims.get("nbf")),
        issued_at=_from_unix(claims.get("iat")),
        session_id=str(claims.get("sid") or "") or None,
        credential_id=str(claims.get("jti") or "") or None,
        reason="Session credential signature valid.",
    )


def verify_refresh(token: str, key: bytes, audience: str) -> RefreshClaims | None:
    """Return refresh claims, or None when the token is not a valid refresh JWT."""
    claims = _decode(token, key, audience)
    if claims is None or claims.get("typ") != REFRESH_TYP:
        return None
    scopes = claims.get("scopes")
    return RefreshClaims(
        agent_id=str(claims.get("sub") or ""),
        session_id=str(claims.get("sid") or ""),
        credential_id=str(claims.get("jti") or ""),
        scopes=list(scopes) if isinstance(scopes, list) else [],
        expires_at=_from_unix(claims.get("exp")),
        not_before=_from_unix(claims.get("nbf")),
    )


def is_session_token(token: str) -> bool:
    """Best-effort check that ``token`` is a Kavach session JWT (unverified)."""
    if token.count(".") != _JWT_DOT_COUNT:
        return False
    try:
        header_claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return False
    return header_claims.get("typ") == SESSION_TYP


def enforce_temporal(verified: VerifiedAgent, now: datetime) -> str | None:
    """Return a problem code when ``verified`` is outside its lifetime.

    ``None`` means the credential has no temporal bound, or it is inside
    it. Legacy dev tokens leave both fields empty and pass.
    """
    if verified.not_before is not None and now < verified.not_before:
        return "credential_not_yet_valid"
    if verified.expires_at is not None and now >= verified.expires_at:
        return "credential_expired"
    return None


def _encode(claims: dict[str, object], key: bytes) -> str:
    encoded = jwt.encode(claims, key, algorithm="HS256")
    return encoded if isinstance(encoded, str) else encoded.decode("ascii")


def _decode(token: str, key: bytes, audience: str) -> dict[str, object] | None:
    try:
        decoded = jwt.decode(
            token,
            key,
            algorithms=["HS256"],
            audience=audience,
            options={"verify_exp": False, "verify_nbf": False, "verify_iat": False},
        )
    except jwt.PyJWTError:
        return None
    return dict(decoded)


def _from_unix(value: object) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(int(value), tz=UTC)
    return None


__all__ = [
    "MAX_TTL_SECONDS",
    "REFRESH_TYP",
    "SESSION_TYP",
    "IssuedCredential",
    "RefreshClaims",
    "clamp_ttl",
    "enforce_temporal",
    "is_session_token",
    "mint_session",
    "verify_refresh",
    "verify_session",
]
