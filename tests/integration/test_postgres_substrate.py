"""End-to-end substrate against a real Postgres (the production target).

Auto-marked ``integration`` by directory. Skipped unless a Postgres URL is
provided in ``KAVACH_DATABASE_URL`` (the CI integration job sets it). The
URL is read at import time because the autouse env-isolation fixture strips
``KAVACH_*`` variables during each test.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio

from kavach.api import create_app
from kavach.composition import SubstrateConfig, build_substrate
from kavach.events import utcnow
from kavach.testing.oidc import mint_operator_token, oidc_settings
from kavach.usecases.customer_service import CustomerServiceRules

_PG_URL = os.environ.get("KAVACH_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not _PG_URL.startswith("postgresql"),
    reason="Set KAVACH_DATABASE_URL to a postgresql+asyncpg URL to run.",
)

_OPERATOR_TOKEN = mint_operator_token(role="admin", tenant="bank-1")


@pytest_asyncio.fixture
async def pg_client() -> AsyncIterator[httpx.AsyncClient]:
    sub = build_substrate(
        SubstrateConfig(database_url=_PG_URL, **oidc_settings()),
        rule_providers=[CustomerServiceRules()],
    )
    await sub.create_schema()
    app = create_app(sub)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await sub.dispose()


def _agent_headers(agent_id: str) -> dict[str, str]:
    token = f"agent:{agent_id}:kyc,account.funds,complaint"
    return {"Authorization": f"Bearer {token}", "X-Kavach-Tenant": "bank-1"}


def _operator_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_OPERATOR_TOKEN}", "X-Kavach-Tenant": "bank-1"}


async def test_full_flow_on_postgres(pg_client: httpx.AsyncClient) -> None:
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    mandate_id = f"m-{uuid.uuid4().hex[:8]}"

    payload = {
        "mandate_id": mandate_id,
        "originator_id": "customer-1",
        "originator_kind": "human",
        "agent_id": agent_id,
        "action_scope": ["account.funds.transfer"],
        "constraints": [{"path": "payment_amount.amount", "operator": "lte", "value": 500000}],
        "expires_at": (utcnow() + timedelta(hours=1)).isoformat(),
        "nonce": f"n-{uuid.uuid4().hex[:8]}",
    }
    issued = await pg_client.post("/v1/mandates", json=payload, headers=_operator_headers())
    assert issued.status_code == 201, issued.text
    token = issued.json()["token"]

    # Duplicate issuance conflicts on the real unique constraint (409, not 500).
    dup = await pg_client.post("/v1/mandates", json=payload, headers=_operator_headers())
    assert dup.status_code == 409, dup.text
    assert dup.json()["code"] == "mandate_already_exists"

    # High-value transfer within the mandate steps up.
    decision = await pg_client.post(
        f"/v1/agents/{agent_id}/decisions",
        json={
            "session_id": "s1",
            "action_type": "account.funds.transfer",
            "parameters": {"amount": 250000},
            "use_case": "customer_service",
        },
        headers={**_agent_headers(agent_id), "X-Kavach-Mandate": token},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["outcome"] == "step_up"


async def test_revocation_prevents_reuse_on_postgres(pg_client: httpx.AsyncClient) -> None:
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    mandate_id = f"m-{uuid.uuid4().hex[:8]}"
    payload = {
        "mandate_id": mandate_id,
        "originator_id": "customer-1",
        "originator_kind": "human",
        "agent_id": agent_id,
        "action_scope": ["account.funds.transfer"],
        "constraints": [{"path": "payment_amount.amount", "operator": "lte", "value": 500000}],
        "expires_at": (utcnow() + timedelta(hours=1)).isoformat(),
        "nonce": f"n-{uuid.uuid4().hex[:8]}",
    }
    issued = await pg_client.post("/v1/mandates", json=payload, headers=_operator_headers())
    assert issued.status_code == 201, issued.text
    token = issued.json()["token"]

    revoke = await pg_client.post(
        f"/v1/mandates/{mandate_id}/revoke",
        json={"revoked_by": "op-1", "reason": "test"},
        headers=_operator_headers(),
    )
    assert revoke.status_code == 200, revoke.text

    # Revoking again conflicts.
    again = await pg_client.post(
        f"/v1/mandates/{mandate_id}/revoke",
        json={"revoked_by": "op-1", "reason": "test"},
        headers=_operator_headers(),
    )
    assert again.status_code == 409, again.text

    # A revoked mandate no longer authorizes the transfer.
    decision = await pg_client.post(
        f"/v1/agents/{agent_id}/decisions",
        json={
            "session_id": "s1",
            "action_type": "account.funds.transfer",
            "parameters": {"amount": 250000},
            "use_case": "customer_service",
        },
        headers={**_agent_headers(agent_id), "X-Kavach-Mandate": token},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["outcome"] == "deny"
