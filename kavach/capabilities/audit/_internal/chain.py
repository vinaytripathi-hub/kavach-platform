"""Pure HMAC-SHA256 hash-chain primitives (ADR-0012).

Each audit record links to its predecessor via ``prev_hash``; the
record's own ``this_hash`` is an HMAC over the link material. Any change
to a payload, an ordering, or an inserted/removed record breaks the chain
and is detectable by recomputation with the signing key.
"""

from __future__ import annotations

import hashlib
import hmac
import json

GENESIS = "GENESIS"


def payload_digest(payload: dict[str, object]) -> str:
    """SHA-256 over the canonical JSON form of an event payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def link_message(prev_hash: str | None, position: int, event_id: str, digest: str) -> str:
    """Deterministic material that ``this_hash`` is computed over."""
    return f"{prev_hash or GENESIS}|{position}|{event_id}|{digest}"


def compute_hash(
    key: bytes, prev_hash: str | None, position: int, event_id: str, digest: str
) -> str:
    """HMAC-SHA256 of the link material under ``key``."""
    msg = link_message(prev_hash, position, event_id, digest)
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def key_id(key: bytes) -> str:
    """Stable, non-revealing identifier for a signing key."""
    return hashlib.sha256(b"kavach-audit-keyid:" + key).hexdigest()[:16]


def sign(key: bytes, chain_head: str) -> str:
    """Signature over a chain head, for an export's signature manifest."""
    return hmac.new(key, chain_head.encode("utf-8"), hashlib.sha256).hexdigest()
