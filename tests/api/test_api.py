"""API integration tests using an in-process ASGI transport."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from kavach.api import create_app
from kavach.capabilities.policy import PolicyCondition, PolicyRule, PolicyRuleSet
from kavach.composition import SubstrateConfig, build_substrate

AGENT_TOKEN = "agent:agent-1:kyc,account.funds"  # noqa: S105
OPERATOR_TOKEN = "op-secret"  # noqa: S105


class _CustomerServiceRules:
    use_case = "customer_service"

    def rule_set(self) -> PolicyRuleSet:
        return PolicyRuleSet(
            use_case="customer_service",
            default_effect="deny",
            rules=[
                PolicyRule(rule_id="allow-kyc", action_type="kyc.*", effect="allow", priority=10),
                PolicyRule(
                    rule_id="stepup-high-value",
                    action_type="account.funds.transfer",
                    effect="step_up",
                    conditions=[
                        PolicyCondition(attribute="parameters.amount", operator="gt", value=50000)
                    ],
                    step_up_role="senior_ops",
                    priority=10,
                ),
            ],
        )


def _agent_headers(idem: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {AGENT_TOKEN}", "X-Kavach-Tenant": "bank-1"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def _operator_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {OPERATOR_TOKEN}", "X-Kavach-Tenant": "bank-1"}


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    sub = build_substrate(
        SubstrateConfig(database_url="sqlite+aiosqlite://", operator_token=OPERATOR_TOKEN),
        rule_providers=[_CustomerServiceRules()],
    )
    await sub.create_schema()
    app = create_app(sub)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await sub.dispose()


async def test_health(client: httpx.AsyncClient) -> None:
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_missing_token_is_401(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s1", "action_type": "kyc.x", "parameters": {}},
    )
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_agent_cannot_act_as_other_agent(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/agents/someone-else/actions",
        json={"session_id": "s1", "action_type": "kyc.x", "parameters": {}},
        headers=_agent_headers(),
    )
    assert resp.status_code == 403


async def test_record_action_and_timeline(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/agents/agent-1/actions",
        json={
            "session_id": "s1",
            "action_type": "kyc.document.verify",
            "parameters": {"doc": "passport"},
        },
        headers=_agent_headers(),
    )
    assert resp.status_code == 201
    assert resp.json()["event_type"] == "ActionExecuted"

    timeline = await client.get("/v1/agents/agent-1/timeline", headers=_operator_headers())
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) == 1


async def test_decision_allow(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/agents/agent-1/decisions",
        json={
            "session_id": "s1",
            "action_type": "kyc.document.verify",
            "parameters": {},
            "use_case": "customer_service",
        },
        headers=_agent_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "allow"
    assert body["confidence"]["kind"] == "rule_deterministic"


async def test_decision_step_up_then_resolve(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/agents/agent-1/decisions",
        json={
            "session_id": "s1",
            "action_type": "account.funds.transfer",
            "parameters": {"amount": 100000},
            "use_case": "customer_service",
        },
        headers=_agent_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "step_up"
    assert body["step_up"]["required_role"] == "senior_ops"
    decision_id = body["decision_id"]

    resolve = await client.post(
        f"/v1/decisions/{decision_id}/step-up/resolve",
        json={"resolution": "approve", "operator_id": "op-1", "rationale": "ok"},
        headers=_operator_headers(),
    )
    assert resolve.status_code == 200
    assert resolve.json()["outcome"] == "allow"

    # Resolving twice conflicts.
    again = await client.post(
        f"/v1/decisions/{decision_id}/step-up/resolve",
        json={"resolution": "approve", "operator_id": "op-1"},
        headers=_operator_headers(),
    )
    assert again.status_code == 409


async def test_idempotency_replays_result(client: httpx.AsyncClient) -> None:
    headers = _agent_headers(idem="key-123")
    first = await client.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s1", "action_type": "kyc.x", "parameters": {}},
        headers=headers,
    )
    second = await client.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s1", "action_type": "kyc.x", "parameters": {}},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["event_id"] == second.json()["event_id"]


async def test_operator_token_required_for_resolve(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/v1/decisions/nope/step-up/resolve",
        json={"resolution": "approve", "operator_id": "op-1"},
        headers={"Authorization": "Bearer wrong-token", "X-Kavach-Tenant": "bank-1"},
    )
    assert resp.status_code == 403


async def test_audit_export_via_api(client: httpx.AsyncClient) -> None:
    await client.post(
        "/v1/agents/agent-1/actions",
        json={"session_id": "s1", "action_type": "kyc.x", "parameters": {}},
        headers=_agent_headers(),
    )
    resp = await client.post(
        "/v1/audit/exports",
        json={
            "agent_id": "agent-1",
            "from": "2020-01-01T00:00:00+00:00",
            "to": "2100-01-01T00:00:00+00:00",
        },
        headers=_operator_headers(),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["record_count"] >= 1
    assert body["signature_manifest"]["algorithm"] == "HMAC-SHA256"

    export_id = body["export_id"]
    fetched = await client.get(f"/v1/audit/exports/{export_id}", headers=_operator_headers())
    assert fetched.status_code == 200
    assert fetched.json()["export_id"] == export_id
