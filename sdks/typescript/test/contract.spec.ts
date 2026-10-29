/**
 * Behavioural contract for the TypeScript SDK (Phase 1.5).
 *
 * Every method is exercised against a mocked `fetch` so we can assert the exact
 * HTTP verb, path, headers, and (snake_case) body it emits — the same wire
 * contract the Python reference client speaks. A companion Python test
 * (`tests/sdk/test_python_sdk_contract.py`) asserts the method inventories
 * match 1:1, so the two SDKs cannot drift.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KavachApiError, KavachClient } from "../src/client.js";

interface Captured {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: Record<string, unknown> | undefined;
}

let captured: Captured[];
let nextResponse: { status: number; body: unknown };

function installFetch(): void {
  captured = [];
  nextResponse = { status: 200, body: { ok: true } };
  globalThis.fetch = vi.fn(async (input: unknown, init: unknown) => {
    const req = init as { method: string; headers: Record<string, string>; body?: string };
    captured.push({
      url: String(input),
      method: req.method,
      headers: req.headers,
      body: req.body ? (JSON.parse(req.body) as Record<string, unknown>) : undefined,
    });
    return new Response(JSON.stringify(nextResponse.body), {
      status: nextResponse.status,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

function client(operator?: string): KavachClient {
  return new KavachClient({
    baseUrl: "http://test/",
    token: "tok-123",
    tenant: "bank-1",
    operator,
  });
}

beforeEach(installFetch);
afterEach(() => vi.restoreAllMocks());

describe("auth + tenancy headers", () => {
  it("sends bearer token and tenant on every call", async () => {
    await client().health();
    const call = captured[0]!;
    expect(call.url).toBe("http://test/v1/health");
    expect(call.method).toBe("GET");
    expect(call.headers.Authorization).toBe("Bearer tok-123");
    expect(call.headers["X-Kavach-Tenant"]).toBe("bank-1");
    expect(call.headers["X-Kavach-Operator"]).toBeUndefined();
  });

  it("adds the operator header when configured", async () => {
    await client("op-1").getTrust("agent-1");
    expect(captured[0]!.headers["X-Kavach-Operator"]).toBe("op-1");
  });
});

describe("ingress + decisions", () => {
  it("recordAction posts snake_case body and idempotency key", async () => {
    await client().recordAction("agent-1", {
      sessionId: "s1",
      actionType: "kyc.x",
      parameters: { doc: "passport" },
      idempotencyKey: "idem-1",
    });
    const call = captured[0]!;
    expect(call.method).toBe("POST");
    expect(call.url).toBe("http://test/v1/agents/agent-1/actions");
    expect(call.body).toEqual({
      session_id: "s1",
      action_type: "kyc.x",
      parameters: { doc: "passport" },
      context: null,
    });
    expect(call.headers["Idempotency-Key"]).toBe("idem-1");
  });

  it("requestDecision carries the mandate token header and use_case", async () => {
    await client().requestDecision("agent-1", {
      sessionId: "s1",
      actionType: "account.funds.transfer",
      parameters: { amount: 100000 },
      mandateToken: "mandate~~token",
    });
    const call = captured[0]!;
    expect(call.url).toBe("http://test/v1/agents/agent-1/decisions");
    expect(call.body!.use_case).toBe("customer_service");
    expect(call.body!.action_type).toBe("account.funds.transfer");
    expect(call.headers["X-Kavach-Mandate"]).toBe("mandate~~token");
  });

  it("resolveStepUp targets the decision resolve path", async () => {
    await client("op-1").resolveStepUp("dec-1", {
      resolution: "approve",
      operatorId: "op-1",
      rationale: "ok",
    });
    const call = captured[0]!;
    expect(call.url).toBe("http://test/v1/decisions/dec-1/step-up/resolve");
    expect(call.body).toEqual({ resolution: "approve", operator_id: "op-1", rationale: "ok" });
  });
});

describe("reads", () => {
  it("getTrust defaults the context query", async () => {
    await client("op-1").getTrust("agent-1");
    expect(captured[0]!.url).toBe("http://test/v1/agents/agent-1/trust?context=customer_service");
  });

  it("getTimeline defaults the limit query", async () => {
    await client("op-1").getTimeline("agent-1", { limit: 10 });
    expect(captured[0]!.url).toBe("http://test/v1/agents/agent-1/timeline?limit=10");
  });

  it("requestAuditExport serialises dates to ISO and from/to keys", async () => {
    await client("op-1").requestAuditExport({
      agentId: "agent-1",
      from: new Date("2020-01-01T00:00:00Z"),
      to: new Date("2100-01-01T00:00:00Z"),
    });
    const call = captured[0]!;
    expect(call.url).toBe("http://test/v1/audit/exports");
    expect(call.body).toEqual({
      agent_id: "agent-1",
      from: "2020-01-01T00:00:00.000Z",
      to: "2100-01-01T00:00:00.000Z",
    });
  });
});

describe("mandates + admin", () => {
  it("issueMandate posts the payload verbatim", async () => {
    await client("op-1").issueMandate({ mandate_id: "m-1", agent_id: "agent-1" });
    const call = captured[0]!;
    expect(call.url).toBe("http://test/v1/mandates");
    expect(call.body).toEqual({ mandate_id: "m-1", agent_id: "agent-1" });
  });

  it("getMandate reads by id", async () => {
    await client("op-1").getMandate("m-1");
    expect(captured[0]!.url).toBe("http://test/v1/mandates/m-1");
    expect(captured[0]!.method).toBe("GET");
  });

  it("revokeMandate posts revoked_by/reason", async () => {
    await client("op-1").revokeMandate("m-1", { revokedBy: "op-1", reason: "cancelled" });
    const call = captured[0]!;
    expect(call.url).toBe("http://test/v1/mandates/m-1/revoke");
    expect(call.body).toEqual({ revoked_by: "op-1", reason: "cancelled" });
  });

  it("registerAgent maps camelCase to snake_case", async () => {
    await client("op-1").registerAgent({ agentId: "agent-1", displayName: "Agent One" });
    expect(captured[0]!.body).toEqual({
      agent_id: "agent-1",
      display_name: "Agent One",
      use_case: null,
      metadata: {},
    });
  });

  it("uploadPolicy posts the payload", async () => {
    await client("op-1").uploadPolicy({ use_case: "customer_service" });
    expect(captured[0]!.url).toBe("http://test/v1/admin/policies");
  });

  it("createWebhookSubscription maps eventTypes to event_types", async () => {
    await client("op-1").createWebhookSubscription({
      url: "https://example.test/hook",
      eventTypes: ["DecisionEmitted"],
    });
    expect(captured[0]!.body).toEqual({
      url: "https://example.test/hook",
      event_types: ["DecisionEmitted"],
      secret: null,
    });
  });
});

describe("error handling", () => {
  it("throws KavachApiError carrying the RFC 7807 problem body", async () => {
    nextResponse = {
      status: 409,
      body: { type: "about:blank", title: "Conflict", status: 409, code: "mandate_already_exists" },
    };
    await expect(client("op-1").issueMandate({ mandate_id: "dup" })).rejects.toMatchObject({
      name: "KavachApiError",
      status: 409,
    });
  });
});
