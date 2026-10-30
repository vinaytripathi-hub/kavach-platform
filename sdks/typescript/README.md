# @aurvia/kavach

TypeScript SDK for the [Kavach Platform](https://github.com/vinaytripathi-hub/kavach-platform) `/v1` API — agent accountability for Indian BFSI.

Method names mirror the reference Python client (`kavach/client.py`) 1:1, camelCased, and a contract test keeps the two SDKs in lockstep. Types under `src/types.ts` are generated from the frozen `docs/api/openapi.yaml`.

## Install

```bash
npm install @aurvia/kavach
```

Requires Node 18+ (uses the global `fetch`).

## Usage

```ts
import { KavachClient } from "@aurvia/kavach";

const agent = new KavachClient({
  baseUrl: "https://kavach.internal.bank",
  token: "agent:agent-1:account.funds",
  tenant: "bank-1",
});

const decision = await agent.requestDecision("agent-1", {
  sessionId: "s1",
  actionType: "account.funds.transfer",
  parameters: { amount: 250000 },
  useCase: "customer_service",
  mandateToken, // presented on X-Kavach-Mandate
});

if (decision.outcome === "step_up") {
  // route to a human operator to resolve
}
```

Operator-scoped calls (issuing mandates, resolving step-ups, exporting evidence)
use an operator token:

```ts
const operator = new KavachClient({
  baseUrl: "https://kavach.internal.bank",
  token: process.env.KAVACH_OPERATOR_TOKEN!,
  tenant: "bank-1",
  operator: "op-1",
});
```

Non-2xx responses throw `KavachApiError`, carrying the RFC 7807 problem body.

## Available methods

`health`, `recordAction`, `requestDecision`, `resolveStepUp`, `getTrust`,
`getTimeline`, `requestAuditExport`, `registerAgent`, `issueMandate`,
`getMandate`, `revokeMandate`, `uploadPolicy`, `createWebhookSubscription`.

## Development

```bash
npm install
npm run gen:types   # regenerate types from ../../docs/api/openapi.yaml
npm run typecheck
npm test            # vitest contract suite
npm run build
```

See [`examples/node/minimal-agent`](../../examples/node/minimal-agent) for a runnable agent.
