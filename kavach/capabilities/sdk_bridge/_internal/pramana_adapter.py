"""Real Pramana SDK adapter (ADR-0015).

This is the only module in the substrate that imports ``pramana``. It
verifies an agent's credential presentation and delegation chain via the
public Pramana SDK and maps the result onto ``VerifiedAgent``. The
``pramana`` import is local so the substrate loads even when the SDK is
absent (offline mode uses the fake verifier instead).
"""

from __future__ import annotations

from kavach.capabilities.sdk_bridge.contracts import VerifiedAgent


class LocalPramanaAdapter:
    """Verifies agent credentials using the locally-installed Pramana SDK."""

    def verify(
        self,
        token: str,
        *,
        expected_audience: str,
        required_action: str | None = None,
    ) -> VerifiedAgent:
        try:
            import pramana
        except ImportError:
            return VerifiedAgent(
                agent_id="",
                verified=False,
                reason="Pramana SDK not installed; cannot verify presentation.",
            )

        try:
            pres = pramana.verify_presentation(token, expected_audience=expected_audience)
        except Exception as exc:
            return VerifiedAgent(agent_id="", verified=False, reason=f"Presentation error: {exc}")

        if not getattr(pres, "verified", False):
            return VerifiedAgent(
                agent_id=getattr(pres, "holder_did", "") or "",
                verified=False,
                reason=getattr(pres, "reason", "Presentation not verified."),
            )

        agent_id = getattr(pres, "holder_did", "") or ""
        scopes: list[str] = ["*"]
        delegation_ok = True
        reason = "Presentation verified."

        # If the credential carries a delegation, verify the chain too.
        try:
            deleg = pramana.verify_delegation_chain(token, required_action=required_action)
            delegation_ok = bool(getattr(deleg, "verified", True))
            effective_scope = getattr(deleg, "effective_scope", None)
            if effective_scope:
                scopes = list(effective_scope)
            if not delegation_ok:
                reason = getattr(deleg, "reason", "Delegation chain not verified.")
        except Exception:
            # Not a delegation token; presentation alone stands.
            delegation_ok = True

        return VerifiedAgent(
            agent_id=agent_id,
            verified=True,
            scopes=scopes,
            delegation_ok=delegation_ok,
            reason=reason,
        )
