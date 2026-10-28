"""Signer is byte-oriented and preserves the existing HMAC chain."""

from __future__ import annotations

import pytest

from kavach.capabilities.audit._internal.chain import compute_hash, sign
from kavach.capabilities.audit.signer import HMACSigner, KmsSignerStub, make_signer


def test_hmac_signer_returns_raw_bytes() -> None:
    signer = HMACSigner(b"legacy-audit-key-0123456789abcdef")
    signature = signer.sign(b"GENESIS|0|evt-1|abc")
    assert isinstance(signature, bytes)
    assert len(signature) == 32  # SHA-256 digest size


def test_hmac_signer_hex_matches_legacy_chain() -> None:
    key = b"legacy-audit-key-0123456789abcdef"
    signer = HMACSigner(key)
    legacy = compute_hash(key, None, 0, "evt-1", "abc")
    assert signer.sign(b"GENESIS|0|evt-1|abc").hex() == legacy


def test_hmac_signer_verifies_its_own_signature() -> None:
    signer = HMACSigner(b"k" * 32)
    message = b"head-material"
    assert signer.verify(message, signer.sign(message))
    assert not signer.verify(message, b"not-the-signature")


def test_hmac_signer_verify_matches_legacy_sign() -> None:
    key = b"legacy-audit-key-0123456789abcdef"
    signer = HMACSigner(key)
    legacy_head_sig = bytes.fromhex(sign(key, "head"))
    assert signer.verify(b"head", legacy_head_sig)


def test_kms_stub_fails_closed() -> None:
    stub = KmsSignerStub()
    assert stub.verify(b"m", b"sig") is False
    with pytest.raises(RuntimeError):
        stub.sign(b"m")


def test_make_signer_selects_mode() -> None:
    assert isinstance(make_signer("hmac", b"k" * 32), HMACSigner)
    assert isinstance(make_signer("kms_stub", b"k" * 32), KmsSignerStub)
