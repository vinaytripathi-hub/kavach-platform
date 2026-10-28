"""Signing boundary for the audit chain (ADR-0012, ADR-0017).

The chain writer and exporter depend on ``Signer``, not on a particular
key store. ``HMACSigner`` is the shipping implementation. ``KmsSignerStub``
is the interface placeholder for an HSM or cloud KMS adapter.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Protocol


class Signer(Protocol):
    """Signs and verifies raw bytes of an audit record's link material.

    The byte boundary keeps the contract agnostic of the digest encoding a
    key store returns (an HSM or KMS returns raw signature bytes), while the
    chain stores the hex form.
    """

    key_id: str

    def sign(self, message: bytes) -> bytes: ...

    def verify(self, message: bytes, signature: bytes) -> bool: ...


class HMACSigner:
    """HMAC-SHA256 signer. Behaviour matches the original chain."""

    def __init__(self, key: bytes, *, key_id: str | None = None) -> None:
        self._key = key
        digest = hashlib.sha256(b"kavach-audit-keyid:" + key).hexdigest()
        self.key_id = key_id or digest[:16]

    def sign(self, message: bytes) -> bytes:
        return hmac.new(self._key, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        return hmac.compare_digest(self.sign(message), signature)


class KmsSignerStub:
    """Placeholder for a KMS-backed signer. Calls fail closed."""

    def __init__(self, *, key_id: str = "kms-unconfigured") -> None:
        self.key_id = key_id

    def sign(self, message: bytes) -> bytes:
        del message
        raise RuntimeError(f"KMS signer '{self.key_id}' is not configured.")

    def verify(self, message: bytes, signature: bytes) -> bool:
        del message, signature
        return False


def make_signer(mode: str, key: bytes) -> Signer:
    """Build the audit signer selected by configuration."""
    if mode == "kms_stub":
        return KmsSignerStub()
    return HMACSigner(key)
