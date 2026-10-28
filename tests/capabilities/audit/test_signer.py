"""Signer protocol preserves the existing HMAC chain."""

from __future__ import annotations

from kavach.capabilities.audit._internal.chain import compute_hash, sign
from kavach.capabilities.audit.signer import HMACSigner, KmsSignerStub


def test_hmac_signer_matches_legacy_chain() -> None:
    key = b"legacy-audit-key-0123456789abcdef"
    signer = HMACSigner(key)
    legacy = compute_hash(key, None, 0, "evt-1", "abc")
    assert signer.sign("GENESIS|0|evt-1|abc") == legacy
    assert signer.verify("head", sign(key, "head"))


def test_kms_stub_fails_closed() -> None:
    stub = KmsSignerStub()
    assert stub.verify("m", "sig") is False
