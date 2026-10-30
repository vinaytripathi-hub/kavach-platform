"""Contracts for the Pramana SDK bridge (ADR-0007, ADR-0015).

The substrate depends on the ``CredentialVerifier`` Protocol, not on
``import pramana`` directly. Concrete verifiers live under ``_internal/``:
a real Pramana adapter and an offline fake. The composition layer selects
one by configuration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class VerifiedAgent(BaseModel):
    """Result of verifying an agent credential presentation."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    verified: bool
    scopes: list[str] = Field(default_factory=list)
    delegation_ok: bool = True
    reason: str = ""
    # Session-credential lifetime (ADR-0020). Empty for holder credentials
    # and the legacy ``agent:`` dev token, which carry no expiry.
    expires_at: datetime | None = None
    not_before: datetime | None = None
    issued_at: datetime | None = None
    session_id: str | None = None
    credential_id: str | None = None

    def authorizes(self, action_type: str) -> bool:
        """Whether the verified scopes permit ``action_type``.

        A ``*`` scope authorizes everything; otherwise a scope authorizes
        an action if it equals the action or is a dotted prefix of it
        (e.g. scope ``account.funds`` authorizes ``account.funds.transfer``).
        """
        if not self.verified or not self.delegation_ok:
            return False
        for scope in self.scopes:
            if scope in ("*", action_type):
                return True
            if action_type.startswith(scope + "."):
                return True
        return False


class CredentialVerifier(Protocol):
    """Verifies an agent's bearer credential and (optionally) delegation."""

    def verify(
        self,
        token: str,
        *,
        expected_audience: str,
        required_action: str | None = None,
    ) -> VerifiedAgent: ...
