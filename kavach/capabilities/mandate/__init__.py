"""Mandate capability — signed task authorization (ADR-0018)."""

from __future__ import annotations

from typing import Literal

from kavach.capabilities.mandate._internal.ap2_adapter import AP2MandateVerifier, issue_ap2_mandate
from kavach.capabilities.mandate._internal.fake import FakeMandateVerifier, issue_fake_mandate
from kavach.capabilities.mandate.contracts import MandateVerifier, VerifiedMandate

MandateVerifierMode = Literal["fake", "ap2"]


def make_mandate_verifier(mode: MandateVerifierMode, key: bytes) -> MandateVerifier:
    """Select a mandate verifier. ``fake`` is the offline default."""
    if mode == "ap2":
        return AP2MandateVerifier(key)
    return FakeMandateVerifier(key)


__all__ = [
    "AP2MandateVerifier",
    "FakeMandateVerifier",
    "MandateVerifier",
    "MandateVerifierMode",
    "VerifiedMandate",
    "issue_ap2_mandate",
    "issue_fake_mandate",
    "make_mandate_verifier",
]
