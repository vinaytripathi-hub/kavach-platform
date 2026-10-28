"""Contracts for mandate verification (ADR-0018).

The substrate depends on ``MandateVerifier``, not on a particular token
format. Concrete verifiers (fake HMAC, AP2) live under ``_internal/``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from kavach.events.schemas.mandate import Mandate


class VerifiedMandate(BaseModel):
    """Result of verifying a presented mandate token."""

    model_config = ConfigDict(extra="forbid")

    mandate: Mandate | None = None
    verified: bool
    reason: str = ""
    chain_ok: bool = True
    not_revoked: bool = True
    digest: str = ""


class MandateVerifier(Protocol):
    """Verifies a mandate token against agent, action, and time."""

    def verify(
        self,
        token: str,
        *,
        expected_agent_id: str,
        expected_action: str,
        now: datetime,
        revoked_ids: frozenset[str] = frozenset(),
        parent: Mandate | None = None,
    ) -> VerifiedMandate: ...
