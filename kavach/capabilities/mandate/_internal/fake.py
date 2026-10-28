"""Offline HMAC mandate verifier (ADR-0018).

Token is a compact HS256 JWT whose ``mandate`` claim is the canonical
mandate object. Used by tests and demos; production deployments select
the AP2 adapter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kavach.capabilities.mandate._internal.attenuation import attenuation_ok
from kavach.capabilities.mandate._internal.tokens import decode_hs256, issue_hs256, mandate_digest
from kavach.capabilities.mandate.contracts import VerifiedMandate
from kavach.capabilities.mandate.scope import is_supported_pattern, scope_covers_action
from kavach.events.schemas.mandate import Mandate


def issue_fake_mandate(mandate: Mandate, key: bytes) -> str:
    """Sign ``mandate`` for the fake verifier."""
    return issue_hs256({"mandate": mandate.model_dump(mode="json"), "typ": "kavach-mandate"}, key)


class FakeMandateVerifier:
    """Deterministic HS256 mandate verifier."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def verify(
        self,
        token: str,
        *,
        expected_agent_id: str,
        expected_action: str,
        now: datetime,
        revoked_ids: frozenset[str] = frozenset(),
        parent: Mandate | None = None,
    ) -> VerifiedMandate:
        claims = decode_hs256(token, self._key)
        if claims is None or claims.get("typ") != "kavach-mandate":
            return VerifiedMandate(verified=False, reason="Mandate signature invalid.")
        raw = claims.get("mandate")
        if not isinstance(raw, dict):
            return VerifiedMandate(verified=False, reason="Mandate claim missing.")
        try:
            mandate = Mandate.model_validate(raw)
        except ValueError as exc:
            return VerifiedMandate(verified=False, reason=f"Mandate schema invalid: {exc}")
        return _check_mandate(
            mandate,
            expected_agent_id=expected_agent_id,
            expected_action=expected_action,
            now=now,
            revoked_ids=revoked_ids,
            parent=parent,
        )


def _check_mandate(
    mandate: Mandate,
    *,
    expected_agent_id: str,
    expected_action: str,
    now: datetime,
    revoked_ids: frozenset[str],
    parent: Mandate | None,
) -> VerifiedMandate:
    digest = mandate_digest(mandate)
    if mandate.agent_id != expected_agent_id:
        return VerifiedMandate(
            mandate=mandate, verified=False, reason="Mandate agent mismatch.", digest=digest
        )
    if mandate.expires_at <= now:
        return VerifiedMandate(
            mandate=mandate, verified=False, reason="Mandate expired.", digest=digest
        )
    if not all(is_supported_pattern(scope) for scope in mandate.action_scope):
        return VerifiedMandate(
            mandate=mandate,
            verified=False,
            reason="Mandate scope uses an unsupported pattern.",
            digest=digest,
        )
    if not scope_covers_action(mandate.action_scope, expected_action):
        return VerifiedMandate(
            mandate=mandate,
            verified=False,
            reason="Mandate scope does not cover the action.",
            digest=digest,
        )
    chain_ok, chain_reason = attenuation_ok(parent, mandate)
    not_revoked = mandate.mandate_id not in revoked_ids
    verified = chain_ok and not_revoked
    reason = "Mandate verified."
    if not chain_ok:
        reason = chain_reason
    elif not not_revoked:
        reason = "Mandate revoked."
    return VerifiedMandate(
        mandate=mandate,
        verified=verified,
        reason=reason,
        chain_ok=chain_ok,
        not_revoked=not_revoked,
        digest=digest,
    )


def constraint_value(mandate: Mandate, path: str) -> Any:  # noqa: ANN401
    """Return the first constraint value for ``path``, if any."""
    for item in mandate.constraints:
        if item.path == path:
            return item.value
    return None
