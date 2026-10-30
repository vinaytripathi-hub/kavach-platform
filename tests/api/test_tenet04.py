"""Phase 2a gate: revocation, lifetime, and CAEP delivery."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import jwt
import pytest_asyncio

from kavach.api import create_app
from kavach.capabilities.credentials import mint_session
from kavach.capabilities.signals.dispatch import SignalDispatcher
from kavach.composition import SubstrateConfig, build_substrate
from kavach.events import utcnow
from kavach.testing.oidc import mint_operator_token, oidc_settings

_JWT = "tenet04-jwt-secret-value-32bytes!"
_AGENT = "agent:agent-1:kyc,account.funds"


def _agent(token: str = _AGENT, tenant: str = "bank-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Kavach-Tenant": tenant}


def _admin(tenant: str = "bank-1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {mint_operator_token(role='admin', tenant=tenant)}",
        "X-Kavach-Tenant": tenant,
    }


@pytest_asyncio.fixture
async def client() -> AsyncIterator[tuple[httpx.AsyncClient, object]]:
    sub = build_substrate(
        SubstrateConfig(database_url="sqlite+aiosqlite://", jwt_secret=_JWT, **oidc_settings())
    )
    await sub.create_schema()
    app = create_app(sub)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, sub
    await sub.dispose()


async def test_revoked_agent_denied_on_next_request(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, _sub = client
    started = time.perf_counter()
    revoked = await http.post(
        "/v1/agents/agent-1/revoke",
        json={"revoked_by": "op-demo", "reason": "compromised"},
        headers=_admin(),
    )
    assert revoked.status_code == 200, revoked.text
    denied = await http.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s", "action_type": "kyc.x", "parameters": {}},
        headers=_agent(),
    )
    assert denied.status_code == 401
    assert denied.headers["content-type"].startswith("application/problem+json")
    body = denied.json()
    assert body["code"] == "agent_revoked"
    assert body["type"].endswith("/agent-revoked")
    assert time.perf_counter() - started < 1


async def test_revoked_credential_denied_on_next_request(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, _sub = client
    issued = await http.post(
        "/v1/agents/agent-1/credentials",
        json={"ttl_seconds": 300},
        headers=_agent(),
    )
    assert issued.status_code == 200, issued.text
    payload = issued.json()
    started = time.perf_counter()
    revoked = await http.post(
        f"/v1/credentials/{payload['credential_id']}/revoke",
        json={"revoked_by": "op-demo", "reason": "lost"},
        headers=_admin(),
    )
    assert revoked.status_code == 200, revoked.text
    denied = await http.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s", "action_type": "kyc.x", "parameters": {}},
        headers=_agent(payload["token"]),
    )
    assert denied.status_code == 401
    assert denied.json()["code"] == "credential_revoked"
    assert time.perf_counter() - started < 1


async def test_expired_session_is_401_problem(client: tuple[httpx.AsyncClient, object]) -> None:
    http, _sub = client
    now = utcnow()
    issued = mint_session(
        agent_id="agent-1",
        scopes=["kyc"],
        audience="kavach",
        key=_JWT.encode(),
        ttl_seconds=60,
        now=now - timedelta(minutes=5),
        not_before=now - timedelta(minutes=5),
        expires_at=now - timedelta(seconds=5),
    )
    resp = await http.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s", "action_type": "kyc.x", "parameters": {}},
        headers=_agent(issued.token),
    )
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["code"] == "credential_expired"


async def test_not_yet_valid_session_is_401_problem(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, _sub = client
    now = utcnow()
    issued = mint_session(
        agent_id="agent-1",
        scopes=["kyc"],
        audience="kavach",
        key=_JWT.encode(),
        ttl_seconds=60,
        now=now,
        not_before=now + timedelta(minutes=5),
        expires_at=now + timedelta(minutes=10),
    )
    resp = await http.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s", "action_type": "kyc.x", "parameters": {}},
        headers=_agent(issued.token),
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "credential_not_yet_valid"


async def test_caep_event_received_within_one_second(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, sub = client
    received: list[bytes] = []

    async def _sender(url: str, body: bytes, headers: dict[str, str]) -> int:
        del url, headers
        received.append(body)
        return 202

    started = time.perf_counter()
    revoked = await http.post(
        "/v1/agents/agent-1/revoke",
        json={"revoked_by": "op-demo", "reason": "caep"},
        headers=_admin(),
    )
    assert revoked.status_code == 200, revoked.text
    dispatcher = SignalDispatcher(
        sub.session_factory,  # type: ignore[attr-defined]
        _sender,
        receiver_url="http://receiver.test/ssf",
        issuer="https://kavach.example",
        audience="kavach-ssf",
        key=_JWT.encode(),
    )
    delivered = await dispatcher.process_once()
    assert delivered == 1
    assert received
    claims = jwt.decode(received[0], _JWT, algorithms=["HS256"], audience="kavach-ssf")
    assert "https://schemas.openid.net/secevent/caep/event-type/session-revoked" in claims["events"]
    assert time.perf_counter() - started < 1
