"""Offline fake credential verifier (ADR-0015).

Deterministic, requires no Pramana SDK. Used by tests and offline demos.
Token grammar (compact and human-writable for demos):

    ``agent:<agent_id>``                       -> verified, scope ``*``
    ``agent:<agent_id>:<scope1,scope2,...>``   -> verified, listed scopes
    anything starting with ``invalid``         -> not verified

This is intentionally not cryptographic; it exists so the substrate can
run end-to-end without provisioning real Pramana credentials.
"""

from __future__ import annotations

from kavach.capabilities.sdk_bridge.contracts import VerifiedAgent
from kavach.capabilities.sdk_bridge.legacy import reject_legacy_outside_fake

# Token form ``agent:<id>:<scopes>`` has three colon-separated parts.
_SCOPED_TOKEN_PARTS = 3


class FakeCredentialVerifier:
    """A deterministic, non-cryptographic verifier for offline use."""

    def __init__(self, jwt_secret: bytes | None = None) -> None:
        self._jwt_secret = jwt_secret

    def verify(
        self,
        token: str,
        *,
        expected_audience: str,
        required_action: str | None = None,
    ) -> VerifiedAgent:
        del required_action  # not used by the fake
        legacy = reject_legacy_outside_fake(token, mode="fake")
        if legacy is not None:
            return legacy
        if self._jwt_secret and token.count(".") == 2:  # noqa: PLR2004 - JWT has two dots
            from kavach.capabilities.credentials import is_session_token, verify_session

            if is_session_token(token):
                return verify_session(token, self._jwt_secret, expected_audience)
        if not token or token.startswith("invalid"):
            return VerifiedAgent(
                agent_id="",
                verified=False,
                reason="Fake verifier: token missing or marked invalid.",
            )
        if not token.startswith("agent:"):
            return VerifiedAgent(
                agent_id="",
                verified=False,
                reason="Fake verifier: expected 'agent:<id>[:scopes]' token.",
            )
        parts = token.split(":", 2)
        agent_id = parts[1]
        scopes = ["*"]
        if len(parts) == _SCOPED_TOKEN_PARTS and parts[2]:
            scopes = [s.strip() for s in parts[2].split(",") if s.strip()]
        return VerifiedAgent(
            agent_id=agent_id,
            verified=True,
            scopes=scopes,
            delegation_ok=True,
            reason="Fake verifier: accepted.",
        )
