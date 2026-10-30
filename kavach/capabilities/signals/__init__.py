"""Outbound CAEP/SSF signals (ADR-0020).

A ``SignalEmitter`` turns a domain event into an OpenID Shared Signals
Framework Security Event Token and delivers it. The webhook implementation
signs a SET and POSTs it. Dispatch is outbox-backed so delivery is
retried independently of the request that revoked the principal.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

import jwt

from kavach.events import utcnow
from kavach.events._base import DomainEvent

Sender = Callable[[str, bytes, dict[str, str]], Awaitable[int]]

CAEP_SESSION_REVOKED = "https://schemas.openid.net/secevent/caep/event-type/session-revoked"
CAEP_CREDENTIAL_CHANGE = "https://schemas.openid.net/secevent/caep/event-type/credential-change"
CAEP_ANOMALY = "https://schemas.kavach.invalid/secevent/caep/event-type/anomaly-detected"

EVENT_URIS: dict[str, str] = {
    "AgentRevoked": CAEP_SESSION_REVOKED,
    "MandateRevoked": CAEP_CREDENTIAL_CHANGE,
    "AnomalyDetected": CAEP_ANOMALY,
}

SIGNAL_EVENT_TYPES = frozenset(EVENT_URIS)


class SignalEmitter(Protocol):
    """Delivers one security event to a receiver."""

    name: str

    async def emit(self, event: DomainEvent) -> None: ...


def build_set(
    payload: dict[str, object],
    event_type: str,
    *,
    issuer: str,
    audience: str,
    key: bytes,
) -> str:
    """Build a signed Security Event Token for ``event_type``."""
    event_uri = EVENT_URIS[event_type]
    now = int(utcnow().timestamp())
    subject_id = str(payload.get("agent_id") or payload.get("mandate_id") or "")
    claims: dict[str, object] = {
        "iss": issuer,
        "iat": now,
        "jti": str(payload.get("event_id") or uuid.uuid4()),
        "aud": audience,
        "events": {
            event_uri: {
                "subject": {"format": "opaque", "id": subject_id},
                "event_timestamp": now,
            }
        },
    }
    encoded = jwt.encode(claims, key, algorithm="HS256")
    return encoded if isinstance(encoded, str) else encoded.decode("ascii")


class WebhookSignalEmitter:
    """Signs a SET and POSTs it to one receiver. ``send`` is injected."""

    name = "caep-webhook"

    def __init__(
        self,
        receiver_url: str,
        *,
        issuer: str,
        audience: str,
        key: bytes,
        send: Sender,
    ) -> None:
        self._receiver_url = receiver_url
        self._issuer = issuer
        self._audience = audience
        self._key = key
        self._send = send

    async def emit_payload(self, event_type: str, payload: dict[str, object]) -> int:
        token = build_set(
            payload, event_type, issuer=self._issuer, audience=self._audience, key=self._key
        )
        body = token.encode("utf-8")
        return await self._send(
            self._receiver_url,
            body,
            {"Content-Type": "application/secevent+jwt"},
        )


__all__ = [
    "CAEP_ANOMALY",
    "CAEP_CREDENTIAL_CHANGE",
    "CAEP_SESSION_REVOKED",
    "EVENT_URIS",
    "SIGNAL_EVENT_TYPES",
    "SignalEmitter",
    "WebhookSignalEmitter",
    "build_set",
]
