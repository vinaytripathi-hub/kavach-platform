# ADR-0016 — External API surface, contract, and versioning

**Status:** Accepted
**Date:** 2026-06-12

## Context

The substrate's contract with the rest of the world is its event
schema (ADR-0008) and its read-side projections (ADR-0009). But a BFSI
partner does not import Python; they integrate over a network boundary.
The agent (or the partner's orchestrator) must be able to:

- Tell Kavach what an agent did (ingress).
- Ask Kavach whether an agent may do something (pre-action decision).
- Resolve a human-in-the-loop step-up (Article 14 oversight).
- Read an agent's current trust assessment and activity timeline.
- Export a cryptographically signed evidence pack for a regulator.
- Subscribe to substrate events (webhooks).
- Register agents and upload policy rule sets (admin).

The prototype needs a single, frozen, versioned HTTP contract that a
partner architect can design against in parallel with substrate
implementation. Without a frozen contract, the API and the substrate
co-evolve chaotically and the partner cannot start.

## Decision

**1. REST over HTTP, described by a single OpenAPI 3.1 document at
`docs/api/openapi.yaml`.** The document is the contract. FastAPI
implements it; the generated schema is checked against the committed
document in CI (longer arc). The committed document is authoritative
for partners.

**2. URL-path major versioning: `/v1/...`.** Breaking changes to the
HTTP surface produce `/v2`. This is distinct from, and composed with,
the per-event `schema_version` discipline of ADR-0010: a `/v1`
response may carry an event payload whose `schema_version` is 2. The
URL version governs the HTTP envelope; the event version governs the
payload body.

**3. Endpoint surface (frozen v1):**

| Method + path | Purpose |
|---|---|
| `POST /v1/agents/{agent_id}/actions` | Ingress: record an executed action |
| `POST /v1/agents/{agent_id}/decisions` | Synchronous policy decision (allow / deny / step_up) |
| `POST /v1/decisions/{decision_id}/step-up/resolve` | Operator resolves a step-up |
| `GET  /v1/agents/{agent_id}/trust` | Current multidimensional trust assessment |
| `GET  /v1/agents/{agent_id}/timeline` | Paginated activity timeline |
| `POST /v1/audit/exports` | Request a signed evidence pack |
| `GET  /v1/audit/exports/{export_id}` | Poll and download an evidence pack |
| `POST /v1/webhooks/subscriptions` | Subscribe partner systems to events |
| `POST /v1/admin/agents` | Register an agent |
| `POST /v1/admin/policies` | Upload a policy rule set |
| `GET  /v1/health` | Liveness/readiness |

**4. Errors are RFC 7807 `application/problem+json`** with a stable
machine-readable `type` URI and a `code` enum. The error taxonomy is
versioned with the API.

**5. Idempotency.** State-changing POSTs accept an `Idempotency-Key`
header. The substrate deduplicates by `(tenant, idempotency_key)` and
returns the original result on replay. This makes agent retries safe
and aligns with the at-least-once posture of the event outbox
(ADR-0008).

**6. Authentication and authorization.** Two principal classes:

- **Agents** authenticate with a Pramana-issued credential presentation
  (a signed JWT/VP) carried in `Authorization: Bearer`. The `sdk_bridge`
  capability (ADR-0015) verifies it. The agent's authority derives from
  the delegation chain, not from a Kavach-local role.
- **Operators and admins** authenticate with a Kavach-issued JWT
  (console login). Authorization is tenant-scoped and role-gated.

The prototype implements bearer-token verification and tenant scoping;
mTLS is a deployment-layer concern documented in ADR-0017 and not a
substrate code dependency.

**7. Payloads echo event schemas.** Request and response bodies are
derived from the `kavach/events/schemas/` Pydantic models wherever a
body corresponds to an event, so there is one source of truth for
shape. The API layer adds only transport concerns (pagination
envelopes, problem+json, idempotency).

## Consequences

**Positive:**

- A partner architect can build against `openapi.yaml` immediately.
- The decision/action/step-up triad makes the EU AI Act Article 14
  (oversight) and Article 12 (logging) mechanisms concrete at the
  network boundary.
- Echoing event schemas keeps HTTP and substrate shapes from drifting.

**Negative:**

- Keeping the committed OpenAPI document in sync with FastAPI's
  generated schema requires a CI check (longer arc). Until that check
  exists, drift is possible. Mitigation: the document is generated
  from and validated against the same Pydantic models.
- URL versioning plus event versioning is two version axes. This is
  intentional but must be explained to integrators; the API reference
  documents both.

## Alternatives Considered

- **GraphQL.** Rejected: BFSI integration teams expect REST + OpenAPI;
  the query flexibility GraphQL offers is not needed for a
  command-oriented accountability API.
- **gRPC.** Rejected for the external boundary: heavier client
  tooling for partners; revisit for internal sub-product boundaries
  (ADR-0011) if they ever go cross-process.
- **No frozen contract; let FastAPI's generated schema be the only
  artifact.** Rejected: partners need a stable document to design
  against before the implementation is complete.
- **Header-based or content-negotiation versioning instead of URL
  path.** Rejected: URL path versioning is the most legible for BFSI
  integrators and the easiest to route at a gateway.

## References

- ADR-0008 — Events as the substrate's primary output (payloads echo events)
- ADR-0009 — Read-side projections (trust/timeline reads hit projections)
- ADR-0010 — Event schema versioning (the payload version axis)
- ADR-0012 — Decision events with evidence and reasoning (decision responses)
- ADR-0015 — Pramana SDK packaging (agent credential verification)
- ADR-0017 — On-prem deployment posture (mTLS, gateway)
- `docs/api/openapi.yaml` — the frozen v1 contract
