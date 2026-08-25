"""SDK bridge capability — Pramana identity boundary (ADR-0015).

Public API: the ``VerifiedAgent`` result, the ``CredentialVerifier``
Protocol, the two concrete verifiers, and a ``make_verifier`` factory the
composition layer uses to select one by mode.
"""

from __future__ import annotations

from typing import Literal

from kavach.capabilities.sdk_bridge._internal.fake import FakeCredentialVerifier
from kavach.capabilities.sdk_bridge._internal.pramana_adapter import LocalPramanaAdapter
from kavach.capabilities.sdk_bridge.contracts import CredentialVerifier, VerifiedAgent

VerifierMode = Literal["fake", "pramana"]


def make_verifier(mode: VerifierMode = "fake") -> CredentialVerifier:
    """Build a credential verifier for the given mode (ADR-0015).

    ``fake`` is the offline, deterministic verifier used by tests and
    demos; ``pramana`` wraps the real SDK.
    """
    if mode == "pramana":
        return LocalPramanaAdapter()
    return FakeCredentialVerifier()


__all__ = [
    "CredentialVerifier",
    "FakeCredentialVerifier",
    "LocalPramanaAdapter",
    "VerifiedAgent",
    "VerifierMode",
    "make_verifier",
]
