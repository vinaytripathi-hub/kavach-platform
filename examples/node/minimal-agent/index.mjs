// Minimal Node agent on @aurvia/kavach.
//
// Mirrors the Python customer-service harness, driving the same accountability
// loop against a running Kavach /v1 API:
//
//   1. an operator issues a bounded, signed mandate for the agent
//   2. the agent requests a decision for a high-value transfer, presenting the
//      mandate -> policy escalates to a human (step_up)
//   3. the operator resolves the step-up -> allow
//   4. the operator exports the signed, tamper-evident evidence trail
//
// Run against a live API (see scripts/smoke-sdk-node.sh for a one-command
// bring-up), configured entirely through the environment.

import { KavachClient } from "@aurvia/kavach";

const BASE_URL = process.env.KAVACH_BASE_URL ?? "http://127.0.0.1:8000";
const TENANT = process.env.KAVACH_TENANT ?? "bank-1";
const OPERATOR_TOKEN = process.env.KAVACH_OPERATOR_TOKEN ?? "operator-dev-token";

const agentId = `agent-${Math.random().toString(36).slice(2, 8)}`;
const mandateId = `m-${Math.random().toString(36).slice(2, 8)}`;
const agentToken = `agent:${agentId}:account.funds,kyc,complaint`;

// Two principals: the agent acts; the operator governs.
const agent = new KavachClient({ baseUrl: BASE_URL, token: agentToken, tenant: TENANT });
const operator = new KavachClient({
  baseUrl: BASE_URL,
  token: OPERATOR_TOKEN,
  tenant: TENANT,
  operator: "op-demo",
});

function assert(cond, message) {
  if (!cond) {
    console.error(`FAILED: ${message}`);
    process.exit(1);
  }
}

async function main() {
  console.log("Kavach minimal Node agent");
  console.log(`  API:   ${BASE_URL}`);
  console.log(`  agent: ${agentId}`);
  console.log();

  // 1. Operator issues a bounded, signed mandate.
  const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();
  const issued = await operator.issueMandate({
    mandate_id: mandateId,
    originator_id: "customer-1",
    originator_kind: "human",
    agent_id: agentId,
    action_scope: ["account.funds.transfer"],
    constraints: [{ path: "payment_amount.amount", operator: "lte", value: 500000 }],
    expires_at: expiresAt,
    nonce: `n-${mandateId}`,
  });
  const mandateToken = issued.token;
  assert(typeof mandateToken === "string" && mandateToken.length > 0, "mandate token issued");
  console.log(`  1. mandate issued ......... ${mandateId}`);

  // 2. Agent requests a decision for a high-value transfer, presenting the mandate.
  const decision = await agent.requestDecision(agentId, {
    sessionId: "s1",
    actionType: "account.funds.transfer",
    parameters: { amount: 250000 },
    useCase: "customer_service",
    mandateToken,
  });
  assert(decision.outcome === "step_up", `expected step_up, got ${decision.outcome}`);
  console.log(`  2. transfer decision ...... ${decision.outcome}`);

  // 3. Operator resolves the step-up.
  const resolved = await operator.resolveStepUp(decision.decision_id, {
    resolution: "approve",
    operatorId: "op-demo",
    rationale: "verified with customer",
  });
  assert(resolved.outcome === "allow", `expected allow, got ${resolved.outcome}`);
  console.log(`  3. operator resolution .... ${resolved.outcome}`);

  // 4. Operator exports the signed evidence trail.
  const exported = await operator.requestAuditExport({
    agentId,
    from: new Date("2020-01-01T00:00:00Z"),
    to: new Date("2100-01-01T00:00:00Z"),
  });
  assert(exported.record_count >= 1, "evidence export has records");
  assert(exported.signature_manifest, "evidence export is signed");
  console.log(
    `  4. evidence export ........ ${exported.record_count} record(s), ` +
      `${exported.signature_manifest.algorithm}`,
  );

  console.log();
  console.log("MINIMAL AGENT FLOW PASSED");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
