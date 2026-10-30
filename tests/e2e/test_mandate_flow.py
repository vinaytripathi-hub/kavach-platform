"""HTTP-level mandate flow. Marked e2e by directory."""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from kavach.api.app import create_app
from kavach.composition import SubstrateConfig, build_substrate
from kavach.events import utcnow
from kavach.testing.oidc import mint_operator_token, oidc_settings
from kavach.usecases.customer_service import CustomerServiceRules


@pytest.mark.asyncio
async def test_decision_header_presents_mandate() -> None:
    substrate = build_substrate(
        SubstrateConfig(
            database_url="sqlite+aiosqlite:///:memory:",
            audit_hmac_key="e2e-key",
            **oidc_settings(),
        ),
        rule_providers=[CustomerServiceRules()],
    )
    await substrate.create_schema()
    app = create_app(substrate)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        issued = await client.post(
            "/v1/mandates",
            headers={
                "Authorization": f"Bearer {mint_operator_token(role='admin', tenant='t1')}",
                "X-Kavach-Tenant": "t1",
            },
            json={
                "mandate_id": "m-e2e",
                "originator_id": "customer-1",
                "originator_kind": "human",
                "agent_id": "agent-1",
                "action_scope": ["account.funds.transfer"],
                "constraints": [
                    {"path": "payment_amount.amount", "operator": "lte", "value": 500000}
                ],
                "expires_at": (utcnow() + timedelta(hours=1)).isoformat(),
                "nonce": "n",
            },
        )
        assert issued.status_code == 201, issued.text
        token = issued.json()["token"]
        decision = await client.post(
            "/v1/agents/agent-1/decisions",
            headers={
                "Authorization": "Bearer agent:agent-1:account.funds",
                "X-Kavach-Tenant": "t1",
                "X-Kavach-Mandate": token,
            },
            json={
                "session_id": "s",
                "action_type": "account.funds.transfer",
                "parameters": {"amount": 250000},
                "use_case": "customer_service",
            },
        )
        assert decision.status_code == 200, decision.text
        assert decision.json()["outcome"] == "step_up"
    await substrate.dispose()
