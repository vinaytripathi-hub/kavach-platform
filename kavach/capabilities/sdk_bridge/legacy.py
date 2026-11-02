"""Legacy ``agent:<id>`` development credentials (ADR-0020).

Every presentation is logged. Only ``fake`` mode accepts the grammar.
"""

from __future__ import annotations

import logging

from kavach.capabilities.sdk_bridge.contracts import VerifiedAgent

logger = logging.getLogger(__name__)


def reject_legacy_outside_fake(token: str, *, mode: str) -> VerifiedAgent | None:
    """Log a legacy ``agent:`` token. Reject it when ``mode`` is not ``fake``.

    Returns ``None`` when ``token`` is not a legacy credential, or when fake
    mode should keep parsing it. Returns an unverified result when the token
    must be rejected.
    """
    if not token.startswith("agent:"):
        return None
    logger.warning(
        "Legacy agent: credential presented (verifier mode=%s). "
        "These tokens have no expiry and are accepted only in fake mode.",
        mode,
    )
    if mode != "fake":
        return VerifiedAgent(
            agent_id="",
            verified=False,
            reason="Legacy agent: tokens are rejected when the verifier mode is not fake.",
        )
    return None


__all__ = ["reject_legacy_outside_fake"]
