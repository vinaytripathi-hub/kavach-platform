# Kavach Platform — Technical User Guide

> **Covered as of Phase 2a.** This guide documents only the substrate as it is
> shipped and tested today. It is a living document that grows at every
> roadmap phase gate (see [`docs/roadmap.md`](../roadmap.md)). Features that
> are planned but not yet shipped are explicitly marked as *forthcoming*.

Audience: engineers, SRE/platform operators, and security reviewers who will
run Kavach and integrate agents with it.

Kavach Platform is an **agent accountability substrate**: agents ask it for
pre-action policy decisions, it records cryptographically chained evidence of
everything that happens, escalates risky actions to a human, and can export an
independently verifiable evidence pack. The external surface is a frozen
`/v1` REST contract ([ADR-0016](../adr/0016-external-api-surface-and-versioning.md)).
[ADR-0021](../adr/0021-operator-identity.md) amends that contract for the
operator security scheme only: operator, auditor, and admin routes take an
OIDC access token. There are **21** accepted ADRs
([index](../adr/README.md)). The stack deploys on a single host via Docker
Compose ([ADR-0017](../adr/0017-on-prem-deployment-posture.md)).

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
agent ──▶ FastAPI (/v1) ──▶ lifetime + revocation ──▶ policy ──▶ decision (allow/deny/step_up)
operator (OIDC) ──▶ role check (operator | auditor | admin)
                       └──▶ audit  ──▶ HMAC-chained evidence
                                  ──▶ event bus + outbox ──▶ projections ──▶ console
                                                          ├─▶ webhooks ──▶ partner
                                                          └─▶ signal outbox ──▶ CAEP SET
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
  **worker** (`python -m kavach.worker`) drains that outbox to webhooks and,
  in the same process, runs `SignalDispatcher` for CAEP/SSF delivery.
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

Phase 2a also emits `AgentRevoked` and `CredentialRevoked`
(`kavach/events/schemas/revocation.py`). `MandateRevoked` was already
emitted when a mandate is revoked. These are additional domain events;
they are not part of the frozen eight above.

### Trust & data sufficiency

Trust is a tensor, not a scalar
([ADR-0014](../adr/0014-multidimensional-trust-substrate.md)): a
`TrustAssessment` carries per-dimension values, each with its own
`DataSufficiency` band (`cold` / `thin` / `warm` / `warm_stale`;
[ADR-0013](../adr/0013-multimodal-data-sufficiency.md)) and an optional
composed scalar.

### CAEP / Shared Signals

`SignalOutboxProjection` (`kavach/capabilities/signals/dispatch.py`) copies
three event types onto the `signal_outbox` table in the publishing
transaction ([ADR-0020](../adr/0020-revocation-and-credential-lifetime.md)):

| Domain event | Enqueued when | SET event URI |
|--------------|---------------|----------------|
| `MandateRevoked` | always | `https://schemas.openid.net/secevent/caep/event-type/credential-change` |
| `AgentRevoked` | always | `https://schemas.openid.net/secevent/caep/event-type/session-revoked` |
| `AnomalyDetected` | `severity` is `critical` only | `https://schemas.kavach.invalid/secevent/caep/event-type/anomaly-detected` |

`SignalDispatcher` signs a Security Event Token (HS256, key
`KAVACH_JWT_SECRET`) and POSTs it to `KAVACH_SIGNAL_RECEIVER_URL` with
`Content-Type: application/secevent+jwt`. The SET `iss` and `aud` are
`KAVACH_SIGNAL_ISSUER` (default `https://kavach.example`) and
`KAVACH_SIGNAL_AUDIENCE` (default `kavach-ssf`). An empty receiver URL
disables outbound signals: the dispatcher returns without sending. Delivery
errors leave the row undispatched (`last_error` set) for a later poll. The
worker runs this loop beside the webhook dispatcher (`asyncio.gather` in
`kavach/worker.py`).

---

## 2. Running the substrate

### 2.1 Services (Docker Compose)

`docker-compose.yml` brings up six services on a single host
([ADR-0017](../adr/0017-on-prem-deployment-posture.md)):

| Service | Image / build | Role | Default host port |
|---------|---------------|------|-------------------|
| `db` | `postgres:16` | Event log, projections, outbox | `5432` (`DB_PORT`) |
| `keycloak` | `quay.io/keycloak/keycloak:26.0` | Reference OIDC issuer (`start-dev --import-realm`) | `8180` (`KEYCLOAK_PORT`) |
| `api` | built from `Dockerfile` | FastAPI substrate (`uvicorn kavach.server:app`) | `8000` (`API_PORT`) |
| `worker` | built from `Dockerfile` | Outbox → webhooks, plus CAEP `SignalDispatcher` (`python -m kavach.worker`) | — |
| `mcp` | built from `Dockerfile` | MCP server over `streamable-http` at `/mcp` | `8900` (`MCP_PORT`) |
| `console` | `nginx:1.27-alpine` | Operator console (static SPA) | `8080` (`CONSOLE_PORT`) |

Keycloak imports [`deploy/keycloak/kavach-realm.json`](../../deploy/keycloak/kavach-realm.json)
on start ([ADR-0021](../adr/0021-operator-identity.md)): realm `kavach`,
public client `kavach` (direct access grants and standard flow enabled),
realm roles `operator`, `auditor`, and `admin`, and a demo user `operator`
/ `change-me-operator` with realm role `admin` and tenant attribute
`bank-1`. Change that password before any partner deployment. The API
container points at the in-network issuer
`http://keycloak:8080/realms/kavach` and JWKS
`http://keycloak:8080/realms/kavach/protocol/openid-connect/certs`.
Bootstrap admin credentials are `admin` /
`KEYCLOAK_ADMIN_PASSWORD` (`.env.example` default
`change-me-keycloak-admin`). Any OIDC issuer that serves a JWKS and the
claims in §3 satisfies the verifier; Keycloak is the reference IdP, not
the only one.

### 2.2 Bring-up

```bash
# 1. Configure secrets.
cp .env.example .env
# Edit .env: set strong KAVACH_AUDIT_HMAC_KEY, KAVACH_JWT_SECRET,
# KEYCLOAK_ADMIN_PASSWORD, and POSTGRES_PASSWORD, e.g. `openssl rand -hex 32`.
# There is no static operator API secret. Operator routes require an OIDC
# access token (§3). Compose sets KAVACH_OIDC_ISSUER and
# KAVACH_OIDC_JWKS_URL on the api service, aimed at keycloak.

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
| `KAVACH_JWT_SECRET` | string | `dev-insecure-jwt-secret-change-me` | HS256 key for session JWTs, refresh tokens, and CAEP Security Event Tokens |
| `KAVACH_EXPECTED_AUDIENCE` | string | `kavach` | Audience (`aud`) on agent session and refresh JWTs |
| `KAVACH_OIDC_ISSUER` | URL | empty (fail closed) | Expected `iss` on operator access tokens. Compose sets `http://keycloak:8080/realms/kavach` |
| `KAVACH_OIDC_JWKS_URL` | URL | empty | Remote JWKS. Compose sets the Keycloak certs URL |
| `KAVACH_OIDC_AUDIENCE` | string | `kavach` | Expected `aud` on operator access tokens |
| `KAVACH_OIDC_JWKS` | JSON | empty | Optional inline JWKS document. Tests and `scripts/smoke-sdk-node.sh` set this instead of fetching a URL |
| `KAVACH_OIDC_TENANT_CLAIM` | string | `tenant` | Claim that must equal `X-Kavach-Tenant` |
| `KAVACH_OIDC_LEEWAY_SECONDS` | int | `30` | Clock skew allowed on operator `exp` / `nbf` |
| `KAVACH_AGENT_CREDENTIAL_TTL_SECONDS` | int | `900` | Session TTL cap in seconds. The minter also hard-caps at 900 |
| `KAVACH_SIGNAL_RECEIVER_URL` | URL | empty (signals off) | CAEP/SSF receiver. Wired on the worker, not the API |
| `KAVACH_SIGNAL_ISSUER` | string | `https://kavach.example` | `iss` on outbound Security Event Tokens |
| `KAVACH_SIGNAL_AUDIENCE` | string | `kavach-ssf` | `aud` on outbound Security Event Tokens |
| `KAVACH_ECHO_SQL` | bool | `false` | Echo SQL for debugging |
| `KAVACH_AUTO_CREATE_SCHEMA` | bool | `true` (compose sets `false`) | Create tables on startup vs explicit Alembic |

`KAVACH_OPERATOR_TOKEN` is not a `SubstrateConfig` field and is not in
`.env.example`. Operator identity is the OIDC settings above. On the
Compose `api` service, `KAVACH_OIDC_ISSUER` and `KAVACH_OIDC_JWKS_URL` are
literals (the in-network Keycloak URLs), not interpolated from `.env`.
`KAVACH_OIDC_AUDIENCE` is `${KAVACH_OIDC_AUDIENCE:-kavach}`. The worker
receives `KAVACH_SIGNAL_RECEIVER_URL` from the environment (empty disables
signals).

The Compose file additionally wires `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`
for the DB, `KEYCLOAK_ADMIN_PASSWORD` for Keycloak, and
`KAVACH_API_URL` / `KAVACH_AGENT_TOKEN` / `KAVACH_OPERATOR_ACCESS_TOKEN` for
the `mcp` service. The MCP process reads `KAVACH_API_URL`,
`KAVACH_AGENT_TOKEN`, `KAVACH_TENANT`, and `KAVACH_OPERATOR_ID` (§8.3). It
does not read `KAVACH_OPERATOR_ACCESS_TOKEN`.

Enabling real identity verification: obtain the `aurvia-pramana` wheel, place
it in `vendor/`, uncomment the Pramana install lines in the `Dockerfile`,
set `KAVACH_SDK_BRIDGE_MODE=pramana`, and rebuild
([ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).

---

## 3. Authentication & tenancy

All endpoints except `GET /v1/health` require a **bearer token**
(`Authorization: Bearer <token>`). A missing or malformed header returns
`401 unauthorized` (`application/problem+json`). There are two principal
classes (`kavach/api/security.py`).

### Agent principals (`require_agent`)

The bearer is either a **holder credential** or a **Kavach session JWT**
([ADR-0020](../adr/0020-revocation-and-credential-lifetime.md)).

**Holder credential.** Verified by the configured SDK bridge. In `fake`
mode (`KAVACH_SDK_BRIDGE_MODE=fake`) the grammar is human-writable and has
no expiry:

- `agent:<agent_id>` → verified, scope `*`
- `agent:<agent_id>:<scope1,scope2,...>` → verified, listed scopes
- anything starting with `invalid` → not verified → `401`

`pramana` mode does not accept that grammar. Agent-level revocation still
applies to a legacy `agent:` token: the next request is `401 agent_revoked`.

**Session JWT.** HS256, signed with `KAVACH_JWT_SECRET`, `typ` claim
`kavach-session`. `require_agent` enforces lifetime **before** any policy
effect:

- `now < nbf` → `401 credential_not_yet_valid`
- `now >= exp` → `401 credential_expired`

Both are RFC 7807 `application/problem+json`. The `type` URI is under
`https://kavach.invalid/problems/` (`credential-not-yet-valid`,
`credential-expired`). A holder credential with no `nbf`/`exp` is not
rejected for lifetime.

After the temporal check, `require_agent` reads `agent_revocations` and,
when the token carries a `jti`, `credential_revocations`. A hit is
`401 agent_revoked` or `401 credential_revoked` on that request. The check
is a primary-key read, not a projection.

An agent may only act on its **own** `agent_id`. If the token's agent differs
from the `{agent_id}` in the path, the request is rejected with
`403 forbidden`.

Exchanging a holder credential for a session JWT is
`POST /v1/agents/{id}/credentials` (§4.9). Presenting a session JWT to that
route is `401 unauthorized` ("Present a holder credential, not a session
credential.").

### Operator principals (OIDC)

Operator, auditor, and admin routes require an **OIDC access token**, not a
shared secret ([ADR-0021](../adr/0021-operator-identity.md)).
`OperatorIdentityVerifier` (`kavach/identity/oidc.py`) checks RS256 against
an inline JWKS (`KAVACH_OIDC_JWKS`) or a remote JWKS (`KAVACH_OIDC_JWKS_URL`):

- `iss` equals `KAVACH_OIDC_ISSUER`
- `aud` contains `KAVACH_OIDC_AUDIENCE`
- `exp` / `nbf`, with `KAVACH_OIDC_LEEWAY_SECONDS` (default 30)
- a role from the flat `roles` claim, or from `realm_access.roles`
- the tenant claim (`KAVACH_OIDC_TENANT_CLAIM`, default `tenant`) equals
  `X-Kavach-Tenant`

An empty issuer, or an issuer with no JWKS, fails closed:
`401 unauthorized` ("Operator identity is not configured."). A bad
signature, issuer, or audience is `401 unauthorized`. An expired operator
token is `401 credential_expired`; one not yet valid is
`401 credential_not_yet_valid`. A tenant mismatch is `403 forbidden`. A
role outside the route's allow-list is `403 forbidden`.

The principal's `operator_id` is the token `sub`. The API does not read
`X-Kavach-Operator` for authorization. Step-up and anomaly bodies still
carry their own `operator_id` field, which is what those events record.

Three dependencies, one verifier:

| Dependency | Roles allowed |
|------------|----------------|
| `require_operator` | `operator`, `admin` |
| `require_auditor` | `auditor`, `operator`, `admin` |
| `require_admin` | `admin` |

When a token carries more than one of those roles, the recorded role is
the first match in the order `admin`, `operator`, `auditor`.

Unit and e2e tests do not boot Keycloak. They mint RS256 tokens with
`kavach.testing.oidc.mint_operator_token` (issuer
`https://kavach.test/realms/kavach`, audience `kavach`, inline JWKS).
`scripts/smoke-sdk-node.sh` uses the same helper and exports the token as
the **client** variable `KAVACH_OPERATOR_TOKEN` for the Node example. That
name is not a server secret. A live Keycloak test,
`tests/integration/test_keycloak_oidc.py`, is skipped unless
`KAVACH_OIDC_ISSUER` is set to an `http` URL.

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
`type`, `title`, `status`, `code`, and an optional `detail`. `type` is a
URI under `https://kavach.invalid/problems/` (`kavach/api/problems.py`).
Unknown codes fall back to `about:blank`.

In the tables below, **Auth** names the dependency from §3: `agent` is
`require_agent`; `operator` is `require_operator` (`operator` or `admin`);
`auditor` is `require_auditor` (`auditor`, `operator`, or `admin`);
`admin` is `require_admin`. Operator curls use `$OIDC_ACCESS_TOKEN`: an
OIDC access token whose tenant claim matches `X-Kavach-Tenant` and whose
role is allowed for that route. `scripts/smoke-sdk-node.sh` mints one
against an in-process JWKS (`kavach.testing.oidc`) and passes it to the
Node example as the client variable `KAVACH_OPERATOR_TOKEN`. That variable
is not a server secret.

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

Resolving a step-up (`require_operator`; `$OIDC_ACCESS_TOKEN` is an OIDC
access token, role `operator` or `admin`, tenant claim `bank-1`):

```bash
curl -s -X POST http://localhost:8000/v1/decisions/$DECISION_ID/step-up/resolve \
  -H "Authorization: Bearer $OIDC_ACCESS_TOKEN" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Content-Type: application/json" \
  -d '{"resolution":"approve","operator_id":"ops-1","rationale":"verified by phone"}'
```

### 4.4 Trust & timeline

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `GET /v1/agents/{agent_id}/trust?context=customer_service` | auditor | `200` TrustResponse | `404` (no assessment) |
| `GET /v1/agents/{agent_id}/timeline?limit=50` | auditor | `200` TimelinePage | `401` |

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
  -H "Authorization: Bearer $OIDC_ACCESS_TOKEN" \
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
| `POST /v1/audit/exports` | auditor | `202` AuditExportStatus | `422` |
| `GET /v1/audit/exports/{export_id}` | auditor | `200` AuditExportStatus | `404` not_found |

The request body uses `agent_id`, `from`, and `to` (ISO-8601). The prototype
produces the pack synchronously (status `ready`) and embeds the records plus
the detached `signature_manifest` (see §8).

### 4.7 Monitor / anomalies

These endpoints are implemented in `kavach/api/app.py` and described in
[`docs/api/openapi.yaml`](../api/openapi.yaml)
([ADR-0019](../adr/0019-monitor-capability-and-anomaly-feedback-loop.md)).

| Method & path | Auth | Success | Notes |
|---------------|------|---------|-------|
| `GET /v1/agents/{agent_id}/anomalies` | auditor | `200` `{agent_id,severity}` | Current open anomaly severity |
| `POST /v1/anomalies/{anomaly_id}/acknowledge` | operator | `200` `{anomaly_id,resolution}` | Operator acknowledges an anomaly |
| `GET /v1/agents/{agent_id}/metrics` | agent | `200` `{agent_id,anomaly_severity}` | Agent self-scoped; agent-mismatch → `403` |

### 4.8 Webhooks & admin

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/webhooks/subscriptions` | admin | `201` WebhookSubscription | `422` |
| `POST /v1/admin/agents` | admin | `201` AgentRegistration | `422` |
| `POST /v1/admin/policies` | admin | `201` PolicyUploadResult | `422` |

Webhook subscriptions take `url`, `event_types`, and an optional write-only
HMAC `secret` for signing outbound deliveries (dispatched by the worker from
the transactional outbox).

### 4.9 Session credentials

[ADR-0020](../adr/0020-revocation-and-credential-lifetime.md). Capability
code: `kavach/capabilities/credentials/`. The holder credential proves who
the agent is. Kavach then mints a separate HS256 session JWT (key
`KAVACH_JWT_SECRET`) that authorizes API calls. Claims:

| Claim | Meaning |
|-------|---------|
| `typ` | `kavach-session` (refresh tokens use `kavach-refresh`) |
| `sub` | Agent id |
| `sid` | Session id |
| `jti` | Credential id (revocation key) |
| `scopes` | Scopes copied from the verified holder |
| `aud` | `KAVACH_EXPECTED_AUDIENCE` |
| `iat` / `nbf` / `exp` | Issued-at, not-before, expiry |

TTL is `min(requested, KAVACH_AGENT_CREDENTIAL_TTL_SECONDS)` and never
above **900 seconds**. Omitting `ttl_seconds` uses that cap. A requested
value above the cap is clamped; a non-positive value is
`422 validation_error`.

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/agents/{agent_id}/credentials` | agent (holder credential) | `200` CredentialIssueResult | `401` (session token presented, or `agent_revoked`), `422` |
| `POST /v1/credentials/refresh` | refresh token as the bearer | `200` CredentialIssueResult | `401` `credential_expired`, `credential_revoked`, or `unauthorized` |

The issue body is `{"ttl_seconds": 300}` (`ttl_seconds` optional). The
result is `credential_id`, `session_id`, `token`, `expires_at`,
`refresh_token`, and `refresh_expires_at`. The refresh token lasts 24
hours. `POST /v1/credentials/refresh` checks that refresh token, mints a
new session JWT and a new refresh token, and retires the previous refresh
`jti` (a row in `credential_revocations`, `revoked_by` `refresh`). Rows
are stored in `agent_credentials` (migration `0003_credentials`).

```bash
curl -s -X POST http://localhost:8000/v1/agents/agent-cs-01/credentials \
  -H "Authorization: Bearer agent:agent-cs-01:kyc,account.funds" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Content-Type: application/json" \
  -d '{"ttl_seconds":300}'
```

Proof-of-possession (DPoP, RFC 9449) is explicitly deferred in ADR-0020.
A stolen session JWT is replayable until `exp` or revocation.

The published SDKs (`aurvia-kavach` 0.0.1 and `@aurvia/kavach` 0.0.1) do
not wrap these two routes. Call them over HTTP, or keep using the legacy
`agent:` bearer in `fake` mode.

### 4.10 Agent and credential revocation

| Method & path | Auth | Success | Errors |
|---------------|------|---------|--------|
| `POST /v1/agents/{agent_id}/revoke` | admin | `200` `{agent_id,status}` | `409` **already_revoked** |
| `POST /v1/credentials/{credential_id}/revoke` | admin | `200` `{credential_id,status}` | `404` not_found, `409` **already_revoked** |

Body: `revoked_by` (required) and `reason` (optional, default `""`).
Revoking an agent inserts `agent_revocations` and emits `AgentRevoked`.
Revoking a credential inserts `credential_revocations` (keyed by `jti`)
and emits `CredentialRevoked`. Both are checked in `require_agent` on the
**next** request (§3). Revoking an agent denies every later presentation
of that agent, including a freshly minted session JWT and a legacy
`agent:` token. Revoking a credential denies that `jti` only. Unknown
credential ids are `404 not_found`. Mandate revocation is unchanged
(§5) and is still `require_operator`.

```bash
curl -s -X POST http://localhost:8000/v1/agents/agent-cs-01/revoke \
  -H "Authorization: Bearer $OIDC_ACCESS_TOKEN" \
  -H "X-Kavach-Tenant: bank-1" \
  -H "Content-Type: application/json" \
  -d '{"revoked_by":"op-1","reason":"compromised"}'
```

`$OIDC_ACCESS_TOKEN` here must include the `admin` role. The same body
shape revokes one credential at
`POST /v1/credentials/{credential_id}/revoke`. `AgentRevoked` is also
enqueued for CAEP delivery (§1).

### Error codes summary

The `code` enum in `docs/api/openapi.yaml` and `kavach/api/problems.py`
is: `unauthorized`, `forbidden`, `not_found`, `validation_error`,
`step_up_already_resolved`, `mandate_already_exists`, `already_revoked`,
`credential_expired`, `credential_not_yet_valid`, `agent_revoked`,
`credential_revoked`, `internal_error`. It does not include
`idempotency_conflict`.

- **`401 unauthorized`** — missing/malformed bearer, agent credential not verified, operator identity not configured, or operator token not verified.
- **`401 credential_expired` / `credential_not_yet_valid`** — session, refresh, or operator token outside its lifetime. `type` ends with `/credential-expired` or `/credential-not-yet-valid`.
- **`401 agent_revoked` / `credential_revoked`** — revocation row hit on this request. `type` ends with `/agent-revoked` or `/credential-revoked`.
- **`403 forbidden`** — role not permitted, token tenant does not match `X-Kavach-Tenant`, or an agent acting as a different agent.
- **`404 not_found`** — unknown step-up, mandate (get/revoke), credential (revoke), trust assessment, or export.
- **`409`** — `mandate_already_exists`, `step_up_already_resolved`, `already_revoked` (mandate, agent, or credential).
- **`422 validation_error`** — request body validation failure, unknown use case on a decision, or invalid `ttl_seconds`.

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
   `expires_at` was already enforced. `not_before` is optional; when it is
   set and `now < not_before`, verification fails closed with reason
   `Mandate not yet valid.`
   (`temporal_rejection` in `kavach/capabilities/mandate/_internal/tokens.py`,
   used by both the fake and AP2 verifiers). That is not an HTTP error:
   the decision proceeds without a verified mandate, and a
   `mandate_required` rule denies. Gate:
   `test_mandate_not_before_fails_closed`.
3. **Revoke** — `POST /v1/mandates/{id}/revoke` marks it revoked; subsequent
   verification fails closed. `MandateRevoked` is also copied onto the
   signal outbox (§1).

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

> **Both SDKs are published and live.** `aurvia-kavach` **v0.0.1** is on PyPI
> ([pypi.org/project/aurvia-kavach/0.0.1](https://pypi.org/project/aurvia-kavach/0.0.1/))
> and `@aurvia/kavach` **v0.0.1** is on npm
> ([npmjs.com/package/@aurvia/kavach/v/0.0.1](https://www.npmjs.com/package/@aurvia/kavach/v/0.0.1)).
> Both were published from GitHub Release `v0.0.1` (§8.4): the Python
> distribution via **PyPI Trusted Publishing (OIDC)** with **PEP 740
> attestations**, and the TypeScript package with **npm provenance**
> (`npm publish --provenance --access public`). Both were independently
> verified by a **clean-room install from the live registries**: a fresh
> Python 3.12 venv `pip install aurvia-kavach` ran the customer-service demo
> end-to-end (health `0.0.1`, KYC `allow`, high-value transfer `step_up`,
> operator resolution `allow`, signed mandate `m-demo-1`, and a signed
> evidence export of 12 records with `audit_signed: true`, HMAC-SHA256), and a
> fresh Node project `npm install @aurvia/kavach@0.0.1` ran the
> `examples/node/minimal-agent` flow end-to-end (mandate issued → transfer
> `step_up` → operator resolution `allow` → evidence export of 7 records with
> an HMAC-SHA256 signature manifest → `MINIMAL AGENT FLOW PASSED`). The
> editable / `file:` installs shown in each subsection remain available for
> working on the SDK source.

### 8.1 Python SDK (`aurvia-kavach`)

The Python distribution is published as **`aurvia-kavach`** while the import
package stays **`kavach`** (Stripe-style: `pip install aurvia-kavach` /
`import kavach`). It supports **Python 3.11, 3.12, and 3.13**
(`requires-python = ">=3.11,<3.14"`).

```bash
# Install from PyPI:
pip install aurvia-kavach

# For local development against a checkout:
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
`upload_policy`, `create_webhook_subscription`) require an **OIDC access
token** as `token` ([ADR-0021](../adr/0021-operator-identity.md)). The
client still sends `X-Kavach-Operator` when `operator` is set; the API
identifies the operator from the token `sub` (§3). `register_agent`,
`upload_policy`, and `create_webhook_subscription` need the `admin` role.
Read helpers (`get_trust`, `get_timeline`, `request_audit_export`) accept
`auditor`, `operator`, or `admin`.

### 8.2 TypeScript SDK (`@aurvia/kavach`)

`@aurvia/kavach` (`sdks/typescript/`) is a hand-polished `KavachClient` whose
methods mirror `kavach/client.py` 1:1 in camelCase. The wire-level types under
`src/types.ts` are generated from the frozen
[`docs/api/openapi.yaml`](../api/openapi.yaml) via `openapi-typescript`
(`npm run gen:types`); the client itself returns plain JSON objects to match
the Python client's `dict[str, Any]` ergonomics. It requires **Node 18+**
(uses the global `fetch`).

```bash
# Install from npm:
npm install @aurvia/kavach

# For local development, consume from source via a file: link,
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
// token must be an OIDC access token (role operator or admin).
// scripts/smoke-sdk-node.sh mints one against an in-process JWKS
// and exports it as KAVACH_OPERATOR_TOKEN for this process.
// That name is a client variable, not a server secret.
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
  `KAVACH_TENANT`, and `KAVACH_OPERATOR_TOKEN`. The last of those must be an
  OIDC access token. `scripts/smoke-sdk-node.sh` mints one with
  `kavach.testing.oidc` against an in-process JWKS and exports it under
  that name before starting the example.
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

It is configured via environment variables the process actually reads:
`KAVACH_API_URL`, `KAVACH_AGENT_TOKEN`, `KAVACH_TENANT`, and
`KAVACH_OPERATOR_ID` (sent as `X-Kavach-Operator`; default `op-demo`).
One `KavachClient` serves every tool, so operator-scoped tools present
the same bearer as `KAVACH_AGENT_TOKEN`. Those routes succeed only when
that bearer is an OIDC access token (§3). `scripts/smoke-mcp.sh` calls
the agent-scoped `decide` tool, which still accepts the fake `agent:`
grammar. Compose injects `KAVACH_OPERATOR_ACCESS_TOKEN` into the `mcp`
service; the server does not read it.

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
    "KAVACH_OPERATOR_ID": "op-demo"
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

**Publish workflows** (tag `v*` for a dry-run, a published GitHub Release for
the real publish). The first release, `v0.0.1`, has shipped **`aurvia-kavach`
v0.0.1 to PyPI** and **`@aurvia/kavach` v0.0.1 to npm** through this flow:

- `.github/workflows/publish-python.yml` — builds the sdist + wheel (`uv build`),
  runs a **smoke-install matrix** that installs the built wheel and imports
  `kavach` on **Python 3.11 / 3.12 / 3.13**, performs a **TestPyPI dry-run**,
  and publishes to **PyPI only on a published Release** via **Trusted
  Publishing (OIDC)** with **PEP 740 attestations** — no long-lived tokens.
  This published `aurvia-kavach` v0.0.1 from the `v0.0.1` Release.
- `.github/workflows/publish-npm.yml` — typecheck + test + build, then
  `npm publish --provenance --access public` (a `--dry-run` on a tag, the real
  publish on a Release). **Provenance** cryptographically links the artifact
  to the workflow run. This published `@aurvia/kavach` v0.0.1 from the same
  `v0.0.1` Release.

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
and ≥ 70% for use cases / experiences. CI enforces `--cov-fail-under=80`
(`.github/workflows/ci.yml`) with branch coverage. Deployment entrypoints and the reference client
(`kavach/client.py`, `kavach/worker.py`, the customer-service harness, and
`kavach/experiences/mcp_server/*`) are covered end-to-end by the smoke scripts
rather than unit tests and are omitted from the coverage source.

### Smoke scripts (`scripts/`)

- **`smoke-onprem.sh`** — drives the synthetic Customer Service flow against a
  running API (register → KYC allow → high-value transfer `step_up` → operator
  resolve → signed evidence export) and asserts the export verifies and a
  mandate digest is present. Ends with `SMOKE TEST PASSED`. The operator
  bearer is `KAVACH_OPERATOR_ACCESS_TOKEN`, and it must be an OIDC access
  token (the script exits if it is unset). In `ap2` mode it also asserts the
  mandate token is an AP2 SD-JWT chain (`~~`).
- **`smoke-sdk-node.sh`** — boots a local API, mints an operator access
  token with `kavach.testing.oidc` against an in-process JWKS, builds
  `@aurvia/kavach`, and runs `examples/node/minimal-agent`. Ends with
  `SDK NODE SMOKE TEST PASSED`.
- **`smoke-mcp.sh`** — uses the official MCP client over stdio to
  `initialize`, `tools/list`, and `tools/call decide`, asserting an `allow`
  outcome. Ends with `MCP SMOKE PASSED`. Requires the `[mcp]` extra.

### Phase 2a gate (NIST tenet 04)

NIST tenet 04 (short-lived, dynamic, revocable authorization) is
**Implemented**. The scorecard in
[`docs/compliance/nist-agentic-iam-mapping.md`](../compliance/nist-agentic-iam-mapping.md)
is **7 / 3 / 0**: seven Implemented (tenets 04–10), three Partial (01–03),
zero Weak. There are 21 accepted ADRs.

Gate tests:

| Test | File |
|------|------|
| `test_revoked_agent_denied_on_next_request` | `tests/api/test_tenet04.py` |
| `test_revoked_credential_denied_on_next_request` | `tests/api/test_tenet04.py` |
| `test_expired_session_is_401_problem` | `tests/api/test_tenet04.py` |
| `test_not_yet_valid_session_is_401_problem` | `tests/api/test_tenet04.py` |
| `test_caep_event_received_within_one_second` | `tests/api/test_tenet04.py` |
| `test_mandate_not_before_fails_closed` | `tests/capabilities/mandate/test_not_before.py` |

`tests/integration/test_keycloak_oidc.py` is skipped unless
`KAVACH_OIDC_ISSUER` is an `http` URL. Other tests mint RS256 tokens via
`kavach.testing.oidc` and do not start Keycloak.
- **`dev-setup.sh`** — one-command developer bootstrap.
- **`check-gpg-signature.sh`** — pre-push helper enforcing GPG-signed commits.

---

## 10. Troubleshooting & FAQ

- **`401 unauthorized`** — the `Authorization` header is missing/malformed,
  (fake mode) the agent token does not start with `agent:` / is marked
  `invalid`, operator identity is not configured (empty `KAVACH_OIDC_ISSUER`
  or no JWKS), or the operator access token failed signature, issuer, or
  audience checks. A session JWT presented to
  `POST …/credentials` also returns this code.
- **`401 credential_expired` / `credential_not_yet_valid`** — a session JWT
  or operator access token is outside `nbf`/`exp`. Both are
  `application/problem+json` with a `type` under
  `https://kavach.invalid/problems/`. Legacy `agent:` tokens have no expiry.
- **`401 agent_revoked` / `credential_revoked`** — `require_agent` found a
  row in `agent_revocations` or `credential_revocations` on this request.
- **`403 forbidden`** — the OIDC token's role is not allowed for the route,
  its tenant claim does not match `X-Kavach-Tenant`, or an agent tried to
  act on an `agent_id` that is not its own.
- **`409 mandate_already_exists`** — re-issuing an existing `mandate_id`.
- **`409 step_up_already_resolved` / `409 already_revoked`** — the step-up,
  mandate, agent, or credential is already in a terminal state.
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
- **Phase 1.5 — `aurvia-kavach` v0.0.1 published and live on PyPI +
  `@aurvia/kavach` v0.0.1 published and live on npm (TS SDK 1:1 with the Python
  client), contract tests, Node reference agent, and publish CI — both packages
  released from GitHub Release `v0.0.1` (PyPI Trusted Publishing/OIDC +
  attestations; npm provenance) and independently clean-room verified from the
  live registries.**
- **Phase 2a — NIST tenet 04:** OIDC operator identity (Keycloak in Compose,
  no `KAVACH_OPERATOR_TOKEN`), 15-minute session credentials and refresh,
  agent and credential revocation checked on the next request, mandate
  `not_before`, and CAEP/SSF delivery from the worker. Scorecard 7/3/0.
  ADRs 0020 and 0021 (21 accepted).
