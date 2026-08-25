"""Reference Python client for the Kavach API (ADR-0016).

A thin, dependency-light client a partner can copy or import. It wraps the
frozen ``/v1`` contract. Synchronous (httpx) for simple integration code.
The client is illustrative; partners may generate their own from
``docs/api/openapi.yaml``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx


class KavachClient:
    """Minimal client over the Kavach ``/v1`` API."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str,
        tenant: str = "default",
        operator: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)
        self._token = token
        self._tenant = tenant
        self._operator = operator

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "X-Kavach-Tenant": self._tenant,
        }
        if self._operator:
            headers["X-Kavach-Operator"] = self._operator
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> KavachClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- system -------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        data: dict[str, Any] = self._client.get("/v1/health").json()
        return data

    # -- ingress + decisions ------------------------------------------------

    def record_action(
        self,
        agent_id: str,
        *,
        session_id: str,
        action_type: str,
        parameters: dict[str, Any] | None = None,
        context: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/v1/agents/{agent_id}/actions",
            json={
                "session_id": session_id,
                "action_type": action_type,
                "parameters": parameters or {},
                "context": context,
            },
            headers=self._headers(idempotency_key),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def request_decision(
        self,
        agent_id: str,
        *,
        session_id: str,
        action_type: str,
        parameters: dict[str, Any] | None = None,
        use_case: str = "customer_service",
        context: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/v1/agents/{agent_id}/decisions",
            json={
                "session_id": session_id,
                "action_type": action_type,
                "parameters": parameters or {},
                "use_case": use_case,
                "context": context,
            },
            headers=self._headers(idempotency_key),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def resolve_step_up(
        self,
        decision_id: str,
        *,
        resolution: str,
        operator_id: str,
        rationale: str = "",
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"/v1/decisions/{decision_id}/step-up/resolve",
            json={
                "resolution": resolution,
                "operator_id": operator_id,
                "rationale": rationale,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    # -- reads --------------------------------------------------------------

    def get_trust(self, agent_id: str, *, context: str = "customer_service") -> dict[str, Any]:
        resp = self._client.get(
            f"/v1/agents/{agent_id}/trust",
            params={"context": context},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def get_timeline(self, agent_id: str, *, limit: int = 50) -> dict[str, Any]:
        resp = self._client.get(
            f"/v1/agents/{agent_id}/timeline",
            params={"limit": limit},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def request_audit_export(self, *, agent_id: str, frm: datetime, to: datetime) -> dict[str, Any]:
        resp = self._client.post(
            "/v1/audit/exports",
            json={
                "agent_id": agent_id,
                "from": frm.isoformat(),
                "to": to.isoformat(),
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    # -- admin --------------------------------------------------------------

    def register_agent(
        self,
        *,
        agent_id: str,
        display_name: str,
        use_case: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/v1/admin/agents",
            json={
                "agent_id": agent_id,
                "display_name": display_name,
                "use_case": use_case,
                "metadata": metadata or {},
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def upload_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post("/v1/admin/policies", json=payload, headers=self._headers())
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def create_webhook_subscription(
        self, *, url: str, event_types: list[str], secret: str | None = None
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/v1/webhooks/subscriptions",
            json={"url": url, "event_types": event_types, "secret": secret},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data
