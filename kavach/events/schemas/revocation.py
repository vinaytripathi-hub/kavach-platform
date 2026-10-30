"""Agent and credential revocation events (ADR-0020)."""

from __future__ import annotations

from typing import ClassVar

from kavach.events._base import DomainEvent


class AgentRevoked(DomainEvent):
    """Emitted when an agent principal is revoked."""

    event_type: ClassVar[str] = "AgentRevoked"
    schema_version: ClassVar[int] = 1

    agent_id: str
    revoked_by: str
    reason: str = ""


class CredentialRevoked(DomainEvent):
    """Emitted when one session or refresh credential (``jti``) is revoked."""

    event_type: ClassVar[str] = "CredentialRevoked"
    schema_version: ClassVar[int] = 1

    agent_id: str
    credential_id: str
    revoked_by: str
    reason: str = ""


__all__ = ["AgentRevoked", "CredentialRevoked"]
