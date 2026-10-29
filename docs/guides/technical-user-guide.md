# Kavach Platform — Technical User Guide

> **Covered as of Phase 1.5.** This guide documents only the substrate as it is
> shipped and tested today. It is a living document that grows at every
> roadmap phase gate (see [`docs/roadmap.md`](../roadmap.md)). Features that
> are planned but not yet shipped are explicitly marked as *forthcoming*.

Audience: engineers, SRE/platform operators, and security reviewers who will
run Kavach and integrate agents with it.

Kavach Platform is an **agent accountability substrate**: agents ask it for
pre-action policy decisions, it records cryptographically chained evidence of
everything that happens, escalates risky actions to a human, and can export an
independently verifiable evidence pack. The external surface is a frozen
`/v1` REST contract ([ADR-0016](../adr/0016-external-api-surface-and-versioning.md)),
deployable on a single host via Docker Compose
([ADR-0017](../adr/0017-on-prem-deployment-posture.md)).

---

## 1. Architecture & runtime topology

Kavach follows a three-layer architecture
([ADR-0001](../adr/0001-three-layer-architecture.md)): **substrate** →
**use cases** → **experiences**. Domain events are the substrate's primary
output ([ADR-0008](../adr/0008-events-as-substrate-primary-output.md)); all
read models are projections rebuildable from the event log
([ADR-0009](../adr/0009-read-side-projections.md)).

### Request → decision flow

```
agent ──▶ FastAPI (/v1) ──▶ policy ──▶ decision (allow/deny/step_up)
                       └──▶ audit  ──▶ HMAC-chained evidence
                                  ──▶ event bus + outbox ──▶ projections ──▶ console
                                                          └─▶ webhooks ──▶ partner
```

- **FastAPI `/v1`** (`kavach/api/app.py`) is the only external surface. It is
  a thin transport layer over the substrate service; request/response bodies
  echo the substrate event schemas (`kavach/events/schemas/`).
- **Policy engine** (`kavach/capabilities/policy/`) evaluates a proposed
  action against the active rule set and emits decision-grade events
  (`PolicyEvaluated`, `DecisionEmitted`, and — on `step_up` — `StepUpRequested`),
  each carrying evidence, reasoning, confidence, and `decided_by`
  ([ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md)).
- **Audit chain** (`kavach/capabilities/audit/`) writes one HMAC-SHA256
  hash-chained record per event, transactionally, via a projection handler
  on the bus.
- **Event bus + transactional outbox** (`kavach/composition/bus.py`) append
  each event and fan it out to projection handlers and the outbox. The
  **worker** (`python -m kavach.worker`) drains the outbox and dispatches
  webhooks.
- **Projections** (`kavach/query/projections/`) build the read models the
  operator console consumes: `agent_timeline`, `agent_trust_current`,
  `decision_log`, `step_up_queue`, `mandate_current`, and
  `agent_anomaly_current`.
- **Monitor** (`kavach/capabilities/monitor/`) runs rate, outcome-drift,
  scope-expansion, and confidence-drop detectors
  ([ADR-0019](../adr/0019-monitor-capability-and-anomaly-feedback-loop.md));
  the open anomaly severity is a policy input.

### The eight core events (frozen v1)

`ActionExecuted`, `PolicyEvaluated`, `DecisionEmitted`, `EvidenceRecorded`,
`TrustAssessmentEmitted`, `DecisionFeedbackRecorded`, `StepUpRequested`,
`StepUpResolved`. All are versioned per
[ADR-0010](../adr/0010-event-schema-versioning.md) and registered for replay.

### Trust & data sufficiency

Trust is a tensor, not a scalar
([ADR-0014](../adr/0014-multidimensional-trust-substrate.md)): a
`TrustAssessment` carries per-dimension values, each with its own
`DataSufficiency` band (`cold` / `thin` / `warm` / `warm_stale`;
[ADR-0013](../adr/0013-multimodal-data-sufficiency.md)) and an optional
composed scalar.

---

## 2. Running the substrate

### 2.1 Services (Docker Compose)

`docker-compose.yml` brings up five services on a single host
([ADR-0017](../adr/0017-on-prem-deployment-posture.md)):

| Service | Image / build | Role | Default host port |
|---------|---------------|------|-------------------|
| `db` | `postgres:16` | Event log, projections, outbox | `5432` (`DB_PORT`) |
| `api` | built from `Dockerfile` | FastAPI substrate (`uvicorn kavach.server:app`) | `8000` (`API_PORT`) |
| `worker` | built from `Dockerfile` | Outbox → webhook dispatcher (`python -m kavach.worker`) | — |
| `mcp` | built from `Dockerfile` | MCP server over `streamable-http` at `/mcp` | `8900` (`MCP_PORT`) |
| `console` | `nginx:1.27-alpine` | Operator console (static SPA) | `8080` (`CONSOLE_PORT`) |

### 2.2 Bring-up

```bash
# 1. Configure secrets.
cp .env.example .env
# Edit .env: set strong KAVACH_AUDIT_HMAC_KEY, KAVACH_JWT_SECRET,
# KAVACH_OPERATOR_TOKEN, and POSTGRES_PASSWORD, e.g. `openssl rand -hex 32`.

# 2. Build and start the stack.
docker compose up -d --build

# 3. Apply the database schema (explicit migration step; ADR-0017).
docker compose run --rm api alembic upgrade head

# 4. Verify health.
curl -s http://localhost:8000/v1/health
# {"status":"ok","version":"0.0.1"}
```

On-prem deployments keep schema management explicit (`KAVACH_AUTO_CREATE_SCHEMA=false`)
and run Alembic. The in-process SQLite demo path sets it `true` to create
tables on startup.

Full runbook: [`docs/deployment/on-prem-runbook.md`](../deployment/on-prem-runbook.md).

### 2.3 Configuration (`KAVACH_*`)

All substrate configuration is environment-variable driven, prefixed
`KAVACH_` (`kavach/composition/config.py`, `SubstrateConfig`). Secrets default
to obvious insecure development values and **must** be overridden on-prem.

| Variable | Accepted values | Default | Purpose |
|----------|-----------------|---------|---------|
| `KAVACH_DATABASE_URL` | SQLAlchemy async URL | `sqlite+aiosqlite://` | Postgres (`postgresql+asyncpg://…`) on-prem |
| `KAVACH_AUDIT_HMAC_KEY` | string | `dev-insecure-audit-key-change-me` | Key for the HMAC audit chain / signer / mandate keys |
| `KAVACH_SDK_BRIDGE_MODE` | `fake` \| `pramana` | `fake` | Agent credential verifier (offline fake vs real Pramana SDK) |
| `KAVACH_MANDATE_VERIFIER_MODE` | `fake` \| `ap2` | `fake` | Mandate verifier (fake HMAC vs AP2 SD-JWT) |
| `KAVACH_AUDIT_SIGNER_MODE` | `hmac` \| `kms_stub` | `hmac` | Audit signer; `kms_stub` is a fail-closed placeholder |
| `KAVACH_JWT_SECRET` | string | `dev-insecure-jwt-secret-change-me` | Reserved for JWT-based operator credentials |
| `KAVACH_EXPECTED_AUDIENCE` | string | `kavach` | Audience the agent verifier expects |
| `KAVACH_OPERATOR_TOKEN` | string | `operator-dev-token` | Shared operator/admin bearer token (prototype) |
| `KAVACH_ECHO_SQL` | bool | `false` | Echo SQL for debugging |
| `KAVACH_AUTO_CREATE_SCHEMA` | bool | `true` (compose sets `false`) | Create tables on startup vs explicit Alembic |

The Compose file additionally wires `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`
for the DB, and `KAVACH_API_URL` / `KAVACH_AGENT_TOKEN` / `KAVACH_TENANT` for
the `mcp` service (these are read by the client/MCP server, not by
`SubstrateConfig`).

Enabling real identity verification: obtain the `aurvia-pramana` wheel, place
it in `vendor/`, uncomment the Pramana install lines in the `Dockerfile`,
set `KAVACH_SDK_BRIDGE_MODE=pramana`, and rebuild
([ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).

---

## 3. Authentication & tenancy

All endpoints require a **bearer token** (`Authorization: Bearer <token>`).
A missing or malformed header returns `401 unauthorized`. There are two
principal classes (`kavach/api/security.py`):

### Agent principals (`require_agent`)

The token is verified by the configured credential verifier. In `fake` mode
the token grammar is human-writable:

- `agent:<agent_id>` → verified, scope `*`
- `agent:<agent_id>:<scope1,scope2,...>` → verified, listed scopes
- anything starting with `invalid` → not verified → `401`

An agent may only act on its **own** `agent_id`. If the token's agent differs
from the `{agent_id}` in the path, the request is rejected with
`403 forbidden`.

### Operator principals (`require_operator`)

The token must equal `KAVACH_OPERATOR_TOKEN` exactly, otherwise `403 forbidden`.
The optional `X-Kavach-Operator` header (default `operator`) sets the
`operator_id` recorded on operator actions.

### Tenancy

The `X-Kavach-Tenant` header selects the tenant (default `default`). Tenancy
is enforced throughout: timelines, mandates, step-ups, and audit exports are
all tenant-scoped.

### Idempotency

State-changing ingress and decision POSTs accept an `Idempotency-Key` header
and deduplicate per `(tenant, key)`: a replay returns the original stored
status and body. In Phase 1 this is implemented for `POST …/actions` and
`POST …/decisions`.

### Mandate presentation

A signed mandate is presented on the decision request via the
`X-Kavach-Mandate` header (see §6).

---

## 4. The `/v1` API

Base URL: `https://{host}/v1` (default `http://localhost:8000/v1`). The frozen
contract lives in [`docs/api/openapi.yaml`](../api/openapi.yaml); the
authoritative implementation is `kavach/api/app.py`.

Errors follow **RFC 7807** (`application/problem+json`) with body fields
`type`, `title`, `status`, `code`, and an optional `detail`.

### 4.1 System

| Method & path | Auth | Success | Notes |
|---------------|------|---------|-------|
| `GET /v1/health` | none | `200` | `{"status":"ok","version":"0.0.1"}` |

### 4.2 Ingress & actions

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/agents/{agent_id}/actions` | agent | `201` EventReceipt | `401`, `403` (agent mismatch), `422` |

```bash
curl -s -X POST http://localhost:8000/v1/agents/agent-cs-01/actions \
  -H "Authorization: Bearer agent:agent-cs-01:kyc,account.funds" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","action_type":"kyc.document.verify","parameters":{"document":"passport"},"context":"customer_service"}'
```

### 4.3 Decisions & step-up

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/agents/{agent_id}/decisions` | agent | `200` DecisionResponse | `401`, `403` (agent mismatch), `422` (unknown use case) |
| `POST /v1/decisions/{decision_id}/step-up/resolve` | operator | `200` DecisionResponse | `404` not_found, `409` **step_up_already_resolved** |
| `GET /v1/step-ups` | operator | `200` StepUpQueuePage | `401`, `403` |

A decision returns `outcome` of `allow`, `deny`, or `step_up`, along with
the embedded `evidence`, `reasoning`, `confidence`, `data_sufficiency`, and
`decided_by`. When the outcome is `step_up`, the response includes a `step_up`
object (`reason`, `required_role`). Accepts the `X-Kavach-Mandate` header.

```bash
curl -s -X POST http://localhost:8000/v1/agents/agent-cs-01/decisions \
  -H "Authorization: Bearer agent:agent-cs-01:kyc,account.funds" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","action_type":"account.funds.transfer","parameters":{"amount":250000,"to":"acc-9"},"use_case":"customer_service"}'
```

Resolving a step-up (operator):

```bash
curl -s -X POST http://localhost:8000/v1/decisions/$DECISION_ID/step-up/resolve \
  -H "Authorization: Bearer $KAVACH_OPERATOR_TOKEN" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Content-Type: application/json" \
  -d '{"resolution":"approve","operator_id":"ops-1","rationale":"verified by phone"}'
```

### 4.4 Trust & timeline

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `GET /v1/agents/{agent_id}/trust?context=customer_service` | operator | `200` TrustResponse | `404` (no assessment) |
| `GET /v1/agents/{agent_id}/timeline?limit=50` | operator | `200` TimelinePage | `401` |

### 4.5 Mandates

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/mandates` | operator | `201` MandateIssueResult | `409` **mandate_already_exists** |
| `GET /v1/mandates/{mandate_id}` | operator | `200` MandateView | `404` not_found |
| `POST /v1/mandates/{mandate_id}/revoke` | operator | `200` `{mandate_id,status}` | `404` not_found, `409` **already_revoked** |

Issuing a mandate returns the signed `token` (presented later on
`X-Kavach-Mandate`) and the `mandate_digest`:

```bash
curl -s -X POST http://localhost:8000/v1/mandates \
  -H "Authorization: Bearer $KAVACH_OPERATOR_TOKEN" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Content-Type: application/json" \
  -d '{
        "mandate_id":"m-001",
        "originator_id":"user-42",
        "originator_kind":"human",
        "agent_id":"agent-cs-01",
        "action_scope":["account.funds.transfer"],
        "constraints":[{"path":"payment_amount.amount","operator":"lte","value":500000}],
        "expires_at":"2026-12-31T00:00:00Z",
        "nonce":"n-001"
      }'
```

`originator_kind` is one of `human`, `service`, `agent`, `wallet`.

### 4.6 Audit exports

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/audit/exports` | operator | `202` AuditExportStatus | `422` |
| `GET /v1/audit/exports/{export_id}` | operator | `200` AuditExportStatus | `404` not_found |

The request body uses `agent_id`, `from`, and `to` (ISO-8601). The prototype
produces the pack synchronously (status `ready`) and embeds the records plus
the detached `signature_manifest` (see §8).

### 4.7 Monitor / anomalies

These endpoints are implemented in `kavach/api/app.py` for the monitor
capability ([ADR-0019](../adr/0019-monitor-capability-and-anomaly-feedback-loop.md)).
They are **not yet part of the
frozen `openapi.yaml`** contract.

| Method & path | Auth | Success | Notes |
|---------------|------|---------|-------|
| `GET /v1/agents/{agent_id}/anomalies` | operator | `200` `{agent_id,severity}` | Current open anomaly severity |
| `POST /v1/anomalies/{anomaly_id}/acknowledge` | operator | `200` `{anomaly_id,resolution}` | Operator acknowledges an anomaly |
| `GET /v1/agents/{agent_id}/metrics` | agent | `200` `{agent_id,anomaly_severity}` | Agent self-scoped; agent-mismatch → `403` |

### 4.8 Webhooks & admin

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/webhooks/subscriptions` | operator | `201` WebhookSubscription | `422` |
| `POST /v1/admin/agents` | operator | `201` AgentRegistration | `422` |
| `POST /v1/admin/policies` | operator | `201` PolicyUploadResult | `422` |

Webhook subscriptions take `url`, `event_types`, and an optional write-only
HMAC `secret` for signing outbound deliveries (dispatched by the worker from
the transactional outbox).

### Error codes summary

- **`401 unauthorized`** — missing/malformed bearer, or agent credential not verified.
- **`403 forbidden`** — operator token invalid, or an agent acting as a different agent.
- **`404 not_found`** — unknown step-up, mandate (get/revoke), trust assessment, or export.
- **`409`** — `mandate_already_exists`, `step_up_already_resolved`, `already_revoked`.
- **`422 validation_error`** — request body validation failure, or unknown use case on a decision.

---

## 5. Mandates — issuing, presenting, verifying

A mandate is a signed authorization that an **originator** (a human, service,
agent, or wallet) grants an agent to perform a scoped set of actions under
constraints ([ADR-0018](../adr/0018-signed-mandates-and-policy-integration.md)).
Capability code lives in
`kavach/capabilities/mandate/`.

### Lifecycle

1. **Issue** — `POST /v1/mandates` persists the mandate and returns a signed
   `token`.
2. **Present** — the agent includes `X-Kavach-Mandate: <token>` on its
   `POST …/decisions` call. The substrate verifies the token against the
   requesting agent, the action, the clock, and the revocation set.
3. **Revoke** — `POST /v1/mandates/{id}/revoke` marks it revoked; subsequent
   verification fails closed.

### Verifier modes

Selected by `KAVACH_MANDATE_VERIFIER_MODE` (`make_mandate_verifier`):

- **`fake` (default)** — `FakeMandateVerifier`. The token is a compact HS256
  JWT whose `mandate` claim is the canonical mandate object. Deterministic and
  offline; used by tests and demos.
- **`ap2`** — `AP2MandateVerifier`. A token containing `~` is treated as an
  **SD-JWT payment chain** minted by Google's AP2 SDK: the verifier checks the
  issuer signature, holder key binding, and the closed mandate's
  `transaction_id` against the presentation nonce, then reconstructs the
  substrate `Mandate`. Any other token is an offline HS256 stand-in shaped
  like an AP2 payment mandate (so `ap2` mode works without the SDK installed).

To enable real AP2 SD-JWT verification, install the optional `ap2` extra and
select the mode:

```bash
# The AP2 SDK is not on PyPI; the extra pins the tested commit.
pip install -e '.[ap2]'
export KAVACH_MANDATE_VERIFIER_MODE=ap2
```

The `Dockerfile` already installs the pinned AP2 commit, so
`KAVACH_MANDATE_VERIFIER_MODE=ap2` verifies a real SD-JWT chain in the
container.

### `mandate_required` rules & attenuation

A policy rule can set `mandate_required: true` ([ADR-0018](../adr/0018-signed-mandates-and-policy-integration.md),
optionally restricting `mandate_originator_kinds`). When such a rule matches, the engine denies the
action unless a verified mandate is present, its originator kind is allowed,
and its constraints are satisfied by the request parameters
(`_mandate_block` in the policy engine). For example, customer-service
transfers require a mandate.

**Attenuation** (`_internal/attenuation.py`): a sub-mandate (one with a
`parent_mandate_id`) is valid only if its action scope is a *strict subset*
of the parent's and every parent constraint has a child constraint that is at
least as tight (`lte`/`lt` lower-or-equal, `gte`/`gt` greater-or-equal, `in`
subset, else equality). Scope patterns are restricted to `*`, a literal
action type, or a dotted prefix ending in `.*` (`scope.py`).

---

## 6. Policy authoring

Policies are declarative rule sets (`kavach/capabilities/policy/`) uploaded via
`POST /v1/admin/policies`. The structure maps directly to the OpenAPI
`PolicyRule` schema.

### Rule set

- `use_case` — the use-case key the rule set applies to.
- `version` — free-form version string (default `"0"`).
- `default_effect` — `allow` \| `deny` \| `step_up`. **Defaults to `deny`**
  (default-deny posture).
- `default_step_up_role` — default role for step-up (default `supervisor`).
- `rules` — list of `PolicyRule`.

### Rule

- `rule_id`, optional `description`.
- `action_type` — an `fnmatch` glob over the action type, e.g.
  `account.funds.*`.
- `effect` — `allow` \| `deny` \| `step_up`.
- `conditions` — list of `PolicyCondition` (all must hold for the rule to
  match).
- `step_up_role` — overrides the default step-up role.
- `priority` — integer, **lower wins** (default `100`).
- `mandate_required` — boolean (see §5).
- `mandate_originator_kinds` — optional allow-list of originator kinds.

### Conditions

A condition is `attribute` + `operator` + `value`. The `attribute` is a dotted
path resolved against the evaluation context, which exposes `parameters.*`,
`action_type`, `agent_id`, `context`, `mandate`, and
`agent.anomaly_severity`. Operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`,
`in`, `contains`, plus the mandate-aware `mandate_covers_action` and
`mandate_constraint_satisfied`.

### Matching

Candidate rules are those whose `action_type` glob matches the request, sorted
by `priority` ascending; the first whose conditions all hold wins. If none
match, the `default_effect` applies. A `step_up` outcome emits a
`StepUpRequested` for the resolved role.

```json
{
  "use_case": "customer_service",
  "version": "1",
  "default_effect": "deny",
  "default_step_up_role": "supervisor",
  "rules": [
    { "rule_id": "kyc-allow", "action_type": "kyc.*", "effect": "allow", "priority": 10 },
    { "rule_id": "transfer-stepup", "action_type": "account.funds.transfer",
      "effect": "step_up", "step_up_role": "supervisor", "priority": 20,
      "conditions": [{ "attribute": "parameters.amount", "operator": "gte", "value": 100000 }],
      "mandate_required": true, "mandate_originator_kinds": ["human"] }
  ]
}
```

---

## 7. Audit & evidence

The audit capability (`kavach/capabilities/audit/`) writes a tamper-evident
record per event, transactionally, as a bus projection handler
(`AuditChainWriter`).

### HMAC hash chain

Each record's `this_hash` is derived from the link material
(`link_message(prev_hash, position, event_id, payload_digest)`) signed by the
configured `Signer`. Because every record commits to the previous record's
hash, altering any historical record breaks the chain from that point forward.

### The `Signer` protocol

`kavach/capabilities/audit/signer.py` defines a byte-oriented boundary so an
HSM/KMS adapter can return raw signature bytes:

```python
class Signer(Protocol):
    key_id: str
    def sign(self, message: bytes) -> bytes: ...
    def verify(self, message: bytes, signature: bytes) -> bool: ...
```

Implementations (selected by `KAVACH_AUDIT_SIGNER_MODE` via `make_signer`):

- **`hmac`** — `HMACSigner`, HMAC-SHA256 over the audit key; `key_id` is a
  stable fingerprint of the key. The chain stores the hex form and verifies
  bit-for-bit.
- **`kms_stub`** — `KmsSignerStub`, a placeholder whose `sign` raises and
  whose `verify` returns `False` (fails closed) until a real KMS adapter is
  wired.

### Exporting & verifying evidence

`AuditExporter.export(...)` builds a time-bounded, agent-scoped slice of the
chain plus a detached `SignatureManifest` (`algorithm`, `key_id`,
`chain_head`, `signature`). `AuditExporter.verify(export)` recomputes every
`this_hash` from the stored link material, checks the manifest's `chain_head`
matches the last record, and verifies the signature over the chain head —
returning `True` only if the pack is fully intact. This is exposed via
`POST /v1/audit/exports` and consumed by the operator console's evidence
screen; it maps to EU AI Act Articles 12 (logging) and 13 (transparency).

---

## 8. Integrating an agent today

Phase 1.5 ships **first-class SDKs in two languages**, plus the MCP server:

- **Python — `aurvia-kavach`** (import package `kavach`), exposing
  `kavach.client.KavachClient`.
- **TypeScript — `@aurvia/kavach`**, exposing `KavachClient`, whose methods
  mirror the Python client **1:1** in camelCase and are kept in lockstep by a
  cross-SDK contract test (§8.4).
- **MCP server** (`kavach.experiences.mcp_server`) for local and networked
  agent hosts.

> **Registry release is pending.** The `aurvia-kavach` and `@aurvia/kavach`
> packages are built and release-ready, and the publish CI exists (§8.4), but
> the **first publish to PyPI and npm has not happened yet** — it is blocked on
> PyPI Trusted Publishing / `NPM_TOKEN` setup and claiming the `@aurvia` npm
> scope. The `pip install aurvia-kavach` / `npm install @aurvia/kavach`
> commands below are the **intended** usage once published. Until then, install
> from source as noted in each subsection (`pip install -e .` for Python, the
> `file:` link / `scripts/smoke-sdk-node.sh` for TypeScript).

### 8.1 Python SDK (`aurvia-kavach`)

The Python distribution is published as **`aurvia-kavach`** while the import
package stays **`kavach`** (Stripe-style: `pip install aurvia-kavach` /
`import kavach`). It supports **Python 3.11, 3.12, and 3.13**
(`requires-python = ">=3.11,<3.14"`).

```bash
# Intended, once published to PyPI:
pip install aurvia-kavach

# Today (registry release pending), install from source:
pip install -e .
```

`KavachClient` (`kavach/client.py`) is a thin synchronous `httpx` wrapper over
the `/v1` contract. It sets `Authorization`, `X-Kavach-Tenant`, optional
`X-Kavach-Operator`, `Idempotency-Key`, and `X-Kavach-Mandate` headers for
you.

```python
from kavach.client import KavachClient

with KavachClient(
    "http://localhost:8000",
    token="agent:agent-cs-01:kyc,account.funds",
    tenant="bank-1",
) as client:
    client.record_action(
        "agent-cs-01",
        session_id="s1",
        action_type="kyc.document.verify",
        parameters={"document": "passport"},
    )
    decision = client.request_decision(
        "agent-cs-01",
        session_id="s1",
        action_type="account.funds.transfer",
        parameters={"amount": 250000, "to": "acc-9"},
        use_case="customer_service",
        mandate_token="<token from issue_mandate>",
    )
    print(decision["outcome"])
```

Operator-scoped helpers (`issue_mandate`, `revoke_mandate`, `resolve_step_up`,
`get_trust`, `get_timeline`, `request_audit_export`, `register_agent`,
`upload_policy`, `create_webhook_subscription`) require an operator token.

### 8.2 TypeScript SDK (`@aurvia/kavach`)

`@aurvia/kavach` (`sdks/typescript/`) is a hand-polished `KavachClient` whose
methods mirror `kavach/client.py` 1:1 in camelCase. The wire-level types under
`src/types.ts` are generated from the frozen
[`docs/api/openapi.yaml`](../api/openapi.yaml) via `openapi-typescript`
(`npm run gen:types`); the client itself returns plain JSON objects to match
the Python client's `dict[str, Any]` ergonomics. It requires **Node 18+**
(uses the global `fetch`).

```bash
# Intended, once published to npm:
npm install @aurvia/kavach

# Today (registry release pending), consume from source via a file: link,
# as examples/node/minimal-agent does:
#   "@aurvia/kavach": "file:../../../sdks/typescript"
```

```ts
import { KavachClient, KavachApiError } from "@aurvia/kavach";

// Two principals: the agent acts; the operator governs.
const agent = new KavachClient({
  baseUrl: "http://127.0.0.1:8000",
  token: "agent:agent-cs-01:account.funds,kyc",
  tenant: "bank-1",
});
const operator = new KavachClient({
  baseUrl: "http://127.0.0.1:8000",
  token: process.env.KAVACH_OPERATOR_TOKEN!,
  tenant: "bank-1",
  operator: "op-demo",
});

// Operator issues a bounded, signed mandate.
const issued = await operator.issueMandate({
  mandate_id: "m-001",
  originator_id: "customer-1",
  originator_kind: "human",
  agent_id: "agent-cs-01",
  action_scope: ["account.funds.transfer"],
  constraints: [{ path: "payment_amount.amount", operator: "lte", value: 500000 }],
  expires_at: new Date(Date.now() + 3600_000).toISOString(),
  nonce: "n-001",
});

try {
  const decision = await agent.requestDecision("agent-cs-01", {
    sessionId: "s1",
    actionType: "account.funds.transfer",
    parameters: { amount: 250000 },
    useCase: "customer_service",
    mandateToken: issued.token as string, // presented on X-Kavach-Mandate
  });
  if (decision.outcome === "step_up") {
    // route to a human operator to resolve
    await operator.resolveStepUp(decision.decision_id as string, {
      resolution: "approve",
      operatorId: "op-demo",
      rationale: "verified with customer",
    });
  }
} catch (err) {
  if (err instanceof KavachApiError) {
    console.error(err.status, err.problem); // RFC 7807 problem body
  }
}
```

**Client options** (`KavachClientOptions`): `baseUrl`, `token`, optional
`tenant` (default `default`), optional `operator` (sets `X-Kavach-Operator`),
and optional `timeoutMs` (default `10_000`).

**Available methods** (camelCase counterparts of the Python client):
`health`, `recordAction`, `requestDecision`, `resolveStepUp`, `getTrust`,
`getTimeline`, `requestAuditExport`, `registerAgent`, `issueMandate`,
`getMandate`, `revokeMandate`, `uploadPolicy`, `createWebhookSubscription`.

**Error handling:** any non-2xx response throws **`KavachApiError`**, which
carries the numeric `status` and the parsed RFC 7807 `problem` body (object or
string).

**Reference app & cross-language proof:**

- [`examples/node/minimal-agent`](../../examples/node/minimal-agent) — a
  ~100-line Node agent on `@aurvia/kavach` that drives the full
  issue-mandate → request-decision → handle-`step_up` → export-evidence loop,
  mirroring the Python customer-service harness. Configured by `KAVACH_BASE_URL`,
  `KAVACH_TENANT`, and `KAVACH_OPERATOR_TOKEN`.
- [`scripts/smoke-sdk-node.sh`](../../scripts/smoke-sdk-node.sh) — one command
  that boots a local API (fake verifier, file-backed SQLite), builds and links
  the SDK, then runs the Node reference agent end-to-end against the live API.
  Ends with `SDK NODE SMOKE TEST PASSED`.

### 8.3 MCP server (`kavach.experiences.mcp_server`)

Kavach ships an MCP server built on the official Model Context Protocol SDK.
Each tool is a thin wrapper over `KavachClient`. It speaks two transports:

```bash
# Local agents (Claude Desktop, Cursor):
python -m kavach.experiences.mcp_server --transport stdio

# Networked deployments (default port 8900, path /mcp):
python -m kavach.experiences.mcp_server --transport streamable-http --host 0.0.0.0 --port 8900
```

It is configured via environment variables: `KAVACH_API_URL`,
`KAVACH_AGENT_TOKEN`, `KAVACH_TENANT`, and `KAVACH_OPERATOR_TOKEN`.

The **six tools**:

| Tool | Scope | Wraps |
|------|-------|-------|
| `decide` | agent | `POST …/decisions` |
| `verify_mandate` | agent | `POST …/decisions` bound to an `X-Kavach-Mandate` token |
| `issue_mandate` | operator | `POST /v1/mandates` |
| `resolve_step_up` | operator | `POST …/step-up/resolve` |
| `get_trust` | operator | `GET …/trust` |
| `get_timeline` | operator | `GET …/timeline` |

Example Claude Desktop config (from `scripts/smoke-mcp.sh`):

```json
"kavach": {
  "command": "python",
  "args": ["-m", "kavach.experiences.mcp_server", "--transport", "stdio"],
  "env": {
    "KAVACH_API_URL": "http://localhost:8000",
    "KAVACH_TENANT": "bank-1",
    "KAVACH_AGENT_TOKEN": "agent:agent-cs-01:kyc,account.funds,complaint",
    "KAVACH_OPERATOR_TOKEN": "operator-dev-token"
  }
}
```

### 8.4 SDK contract tests, CI & publishing

**Cross-SDK contract tests** keep the two SDKs from drifting:

- `sdks/typescript/test/contract.spec.ts` (vitest) exercises every TS method
  against a mocked `fetch`, asserting the exact HTTP verb, path, headers
  (`Authorization`, `X-Kavach-Tenant`, `X-Kavach-Operator`, `Idempotency-Key`,
  `X-Kavach-Mandate`), and the **snake_case** request body — the same wire
  contract the Python client speaks. It also asserts `KavachApiError` is thrown
  with the RFC 7807 body on a non-2xx.
- `tests/sdk/test_python_sdk_contract.py` (pytest) asserts the Python
  distribution is named **`aurvia-kavach`** (while the import package is
  `kavach` and its version matches), and that **every** public method on
  `kavach.client.KavachClient` has a camelCase counterpart in the committed TS
  `client.ts`.

**TypeScript SDK CI** — `.github/workflows/sdk-typescript.yml` runs on pushes
and PRs to `main` that touch `sdks/typescript/**`, `docs/api/openapi.yaml`, or
the workflow itself (Node 20). Steps: install → **OpenAPI types in-sync check**
(`npm run gen:types` then `git diff --exit-code src/types.ts`, failing if the
generated `src/types.ts` is stale) → `npm run typecheck` → `npm test` (the
contract suite) → `npm run build`.

**Publish workflows** (tag `v*` or a published GitHub Release; releases to the
public registries are **pending** first-time setup):

- `.github/workflows/publish-python.yml` — builds the sdist + wheel (`uv build`),
  runs a **smoke-install matrix** that installs the built wheel and imports
  `kavach` on **Python 3.11 / 3.12 / 3.13**, performs a **TestPyPI dry-run**,
  and publishes to **PyPI only on a published Release** via **Trusted
  Publishing (OIDC)** — no long-lived tokens. Publishers must be configured on
  PyPI/TestPyPI before the first release.
- `.github/workflows/publish-npm.yml` — typecheck + test + build, then
  `npm publish --provenance --access public` (a `--dry-run` on a tag, the real
  publish on a Release). Requires an `NPM_TOKEN` with publish rights and the
  claimed `@aurvia` scope; **provenance** cryptographically links the artifact
  to the workflow run.

---

## 9. Testing & verification

The test suite follows the TDD discipline of
[ADR-0006](../adr/0006-tdd-discipline.md). Markers are auto-applied by test
location (`tests/conftest.py`).

### Markers & suites

- `unit` — fast, isolated, no I/O.
- `integration` — DB/HTTP/filesystem; the Postgres integration suite exercises
  the full issue → duplicate-`409` → decide and revoke → deny flows against a
  real database.
- `e2e` — slow, full-system user-facing flows.
- `slow`, `external` — additional markers for timing/external dependencies.

```bash
# Developer bootstrap (uv-based):
./scripts/dev-setup.sh

# Fast unit loop (bare pytest; integration/e2e have their own invocations):
pytest

# Targeted suites:
pytest -m integration
pytest -m e2e
```

### Coverage gates

Per ADR-0006, floors are ≥ 80% for capabilities / events / composition / query
and ≥ 70% for use cases / experiences; the whole suite sits at ≥ 85%. CI
enforces `--cov-fail-under=80` (`.github/workflows/ci.yml`) with branch
coverage. Deployment entrypoints and the reference client
(`kavach/client.py`, `kavach/worker.py`, the customer-service harness, and
`kavach/experiences/mcp_server/*`) are covered end-to-end by the smoke scripts
rather than unit tests and are omitted from the coverage source.

### Smoke scripts (`scripts/`)

- **`smoke-onprem.sh`** — drives the synthetic Customer Service flow against a
  running API (register → KYC allow → high-value transfer `step_up` → operator
  resolve → signed evidence export) and asserts the export verifies and a
  mandate digest is present. Ends with `SMOKE TEST PASSED`. In `ap2` mode it
  also asserts the mandate token is an AP2 SD-JWT chain (`~~`).
- **`smoke-mcp.sh`** — uses the official MCP client over stdio to
  `initialize`, `tools/list`, and `tools/call decide`, asserting an `allow`
  outcome. Ends with `MCP SMOKE PASSED`. Requires the `[mcp]` extra.
- **`dev-setup.sh`** — one-command developer bootstrap.
- **`check-gpg-signature.sh`** — pre-push helper enforcing GPG-signed commits.

---

## 10. Troubleshooting & FAQ

- **`401 unauthorized`** — the `Authorization` header is missing/malformed, or
  (fake mode) the agent token does not start with `agent:` / is marked
  `invalid`.
- **`403 forbidden`** — an operator call used a token that does not equal
  `KAVACH_OPERATOR_TOKEN`, or an agent tried to act on an `agent_id` that is
  not its own.
- **`409 mandate_already_exists`** — re-issuing an existing `mandate_id`;
  previously this surfaced as a `500`.
- **`409 step_up_already_resolved` / `409 already_revoked`** — the step-up or
  mandate is already in a terminal state.
- **Decision returns `deny` unexpectedly** — check default-deny: no rule
  matched, or a matched rule had `mandate_required` without a satisfying
  mandate. Inspect the `reasoning.decision_path` in the response.
- **A malformed `X-Kavach-Mandate` header does not error** — this is by
  design: an invalid mandate is never trusted and never raises `500`; the
  decision simply proceeds without a verified mandate (and is denied if one
  was required).
- **`ImportError: AP2 SDK is not installed`** when minting SD-JWT chains —
  install the `[ap2]` extra; without it, `ap2` mode falls back to the offline
  HS256 stand-in.
- **Schema/table errors on a fresh Postgres** — run
  `docker compose run --rm api alembic upgrade head`; on-prem does not
  auto-create the schema.
- **Rebuilding read models** — the event log is the source of truth
  (ADR-0009); every projection is rebuildable from it, so back up the
  `kavach_pgdata` volume and projections reconstitute on replay.

---

## Changelog

- **Phase 1 — initial guide:** architecture, run/config, `/v1` API reference,
  mandates (fake + AP2), policy, audit/Signer, MCP + Python-client
  integration, testing.
- **Phase 1.5 — `aurvia-kavach` on PyPI + `@aurvia/kavach` TS SDK (1:1 with the
  Python client), contract tests, Node reference agent, and publish CI
  (registry release pending).**
