"""Session credential lifetime (ADR-0020)."""

from __future__ import annotations

from datetime import timedelta

from kavach.capabilities.credentials import (
    clamp_ttl,
    enforce_temporal,
    mint_session,
    verify_session,
)
from kavach.capabilities.sdk_bridge import VerifiedAgent
from kavach.events import utcnow

_KEY = b"test-session-key-must-be-long-enough"
_AUD = "kavach"


def test_ttl_is_capped_at_fifteen_minutes() -> None:
    assert clamp_ttl(None, 900) == 900
    assert clamp_ttl(60, 900) == 60
    assert clamp_ttl(10_000, 900) == 900
    assert clamp_ttl(10_000, 10_000) == 900


def test_session_round_trip_carries_lifetime() -> None:
    issued = mint_session(
        agent_id="agent-1",
        scopes=["account.funds"],
        audience=_AUD,
        key=_KEY,
        ttl_seconds=120,
    )
    verified = verify_session(issued.token, _KEY, _AUD)
    assert verified.verified
    assert verified.agent_id == "agent-1"
    assert verified.credential_id == issued.credential_id
    assert verified.session_id == issued.session_id
    assert verified.scopes == ["account.funds"]
    assert enforce_temporal(verified, utcnow()) is None


def test_expired_and_not_yet_valid_codes() -> None:
    now = utcnow()
    expired = mint_session(
        agent_id="agent-1",
        scopes=["*"],
        audience=_AUD,
        key=_KEY,
        ttl_seconds=60,
        now=now - timedelta(minutes=5),
        not_before=now - timedelta(minutes=5),
        expires_at=now - timedelta(seconds=1),
    )
    assert enforce_temporal(verify_session(expired.token, _KEY, _AUD), now) == "credential_expired"
    future = mint_session(
        agent_id="agent-1",
        scopes=["*"],
        audience=_AUD,
        key=_KEY,
        ttl_seconds=60,
        now=now,
        not_before=now + timedelta(minutes=5),
        expires_at=now + timedelta(minutes=10),
    )
    code = enforce_temporal(verify_session(future.token, _KEY, _AUD), now)
    assert code == "credential_not_yet_valid"


def test_legacy_verified_agent_has_no_lifetime() -> None:
    verified = VerifiedAgent(agent_id="a", verified=True)
    assert enforce_temporal(verified, utcnow()) is None
