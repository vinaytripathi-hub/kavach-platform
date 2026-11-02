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


def _refresh_headers(refresh_token: str, tenant: str = "bank-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {refresh_token}", "X-Kavach-Tenant": tenant}


async def _issue(http: httpx.AsyncClient) -> dict[str, str]:
    issued = await http.post(
        "/v1/agents/agent-1/credentials",
        json={"ttl_seconds": 300},
        headers=_agent(),
    )
    assert issued.status_code == 200, issued.text
    body: dict[str, str] = issued.json()
    return body


async def _refresh(http: httpx.AsyncClient, refresh_token: str) -> httpx.Response:
    return await http.post("/v1/credentials/refresh", headers=_refresh_headers(refresh_token))


async def test_revoked_credential_refresh_returns_401(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, _sub = client
    issued = await _issue(http)
    revoked = await http.post(
        f"/v1/credentials/{issued['credential_id']}/revoke",
        json={"revoked_by": "op-demo", "reason": "lost"},
        headers=_admin(),
    )
    assert revoked.status_code == 200, revoked.text
    refreshed = await _refresh(http, issued["refresh_token"])
    assert refreshed.status_code == 401
    assert refreshed.headers["content-type"].startswith("application/problem+json")
    assert refreshed.json()["code"] == "credential_revoked"
    assert "token" not in refreshed.json()


async def test_prerevocation_refresh_token_unusable_afterward(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, _sub = client
    issued = await _issue(http)
    rotated = await _refresh(http, issued["refresh_token"])
    assert rotated.status_code == 200, rotated.text
    current = rotated.json()
    revoked = await http.post(
        f"/v1/credentials/{current['credential_id']}/revoke",
        json={"revoked_by": "op-demo", "reason": "lost"},
        headers=_admin(),
    )
    assert revoked.status_code == 200, revoked.text
    denied = await _refresh(http, current["refresh_token"])
    assert denied.status_code == 401
    assert denied.json()["code"] == "credential_revoked"
    action = await http.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s", "action_type": "kyc.x", "parameters": {}},
        headers=_agent(current["token"]),
    )
    assert action.status_code == 401
    assert action.json()["code"] == "credential_revoked"


async def test_revoked_chain_blocks_every_earlier_refresh_token(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, _sub = client
    first = await _issue(http)
    second_response = await _refresh(http, first["refresh_token"])
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    third_response = await _refresh(http, second["refresh_token"])
    assert third_response.status_code == 200, third_response.text
    third = third_response.json()
    revoked = await http.post(
        f"/v1/credentials/{third['credential_id']}/revoke",
        json={"revoked_by": "op-demo", "reason": "chain"},
        headers=_admin(),
    )
    assert revoked.status_code == 200, revoked.text
    for refresh_token in (first["refresh_token"], second["refresh_token"], third["refresh_token"]):
        denied = await _refresh(http, refresh_token)
        assert denied.status_code == 401
        assert denied.json()["code"] == "credential_revoked"


async def test_refresh_rechecks_holder_credential(
    client: tuple[httpx.AsyncClient, object],
) -> None:
    http, sub = client
    inner = sub.verifier  # type: ignore[attr-defined]

    class _RejectAfter:
        def __init__(self) -> None:
            self.calls = 0

        def verify(
            self,
            token: str,
            *,
            expected_audience: str,
            required_action: str | None = None,
        ) -> object:
            self.calls += 1
            if self.calls > 1:
                from kavach.capabilities.sdk_bridge import VerifiedAgent

                return VerifiedAgent(agent_id="", verified=False, reason="holder no longer valid")
            return inner.verify(
                token, expected_audience=expected_audience, required_action=required_action
            )

    gate = _RejectAfter()
    sub.verifier = gate  # type: ignore[attr-defined]
    sub.service._verifier = gate  # type: ignore[attr-defined]
    issued = await _issue(http)
    refreshed = await _refresh(http, issued["refresh_token"])
    assert gate.calls >= 2
    assert refreshed.status_code == 401
    assert refreshed.json()["code"] == "unauthorized"


async def test_legacy_agent_token_rejected_when_verifier_mode_is_not_fake() -> None:
    sub = build_substrate(
        SubstrateConfig(
            database_url="sqlite+aiosqlite://",
            jwt_secret=_JWT,
            sdk_bridge_mode="pramana",
            **oidc_settings(),
        )
    )
    await sub.create_schema()
    app = create_app(sub)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            resp = await http.post(
                "/v1/agents/agent-1/actions",
                json={"session_id": "s", "action_type": "kyc.x", "parameters": {}},
                headers=_agent(),
            )
    finally:
        await sub.dispose()
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "unauthorized"
    assert "not fake" in body["detail"]


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
