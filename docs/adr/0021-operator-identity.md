# ADR-0021 — Operator identity via Keycloak OIDC

**Status:** Accepted
**Date:** 2026-10-30

## Context

Operator and admin routes authenticate by comparing the bearer token to
a single shared secret, `KAVACH_OPERATOR_TOKEN`
(`kavach/api/security.py`, `require_operator`). The operator's id is
whatever the caller puts in `X-Kavach-Operator`. Nothing checks a role,
an expiry, an audience, or a tenant. Every operator in a deployment
shares one password, and that password lives in `.env`.

NIST tenet 04 calls this out by name: long-lived bearer tokens and the
absence of an identity provider are why the tenet is **Weak**. ADR-0020
closes the agent-credential half (TTL, refresh, revocation). This ADR
closes the operator half.

The deployment posture is on-prem Docker Compose (ADR-0017), inside the
partner perimeter (ADR-0004). The IdP therefore has to run beside
Postgres, not as a SaaS dependency. Keycloak is the IdP already assumed
by the on-prem runbook's "operator IdP" hardening note.

Roles the substrate actually needs, and no others:

| Role | May |
|------|-----|
| `operator` | Resolve step-ups, issue and revoke mandates, read trust, timeline, anomalies |
| `auditor` | Read trust, timeline, anomalies, request evidence exports. No mutations. |
| `admin` | Everything an operator may do, plus register agents, upload policy, manage webhook subscriptions, revoke agents and credentials |

Tenant scoping: a token's tenant claim must equal the `X-Kavach-Tenant`
header. A token for `bank-1` cannot operate on `bank-2`.

## Decision

**1. Operator routes require an OIDC access token, not a shared
secret.** `require_operator` validates a bearer JWT against the
configured JWKS:

- signature (RS256)
- `iss` equals `KAVACH_OIDC_ISSUER`
- `aud` contains `KAVACH_OIDC_AUDIENCE`
- `exp` / `nbf` against the request clock
- a role claim containing one of `operator`, `auditor`, `admin`
- a tenant claim equal to `X-Kavach-Tenant`

The role claim is read from Keycloak's standard location
(`realm_access.roles`, falling back to a flat `roles` claim so unit
tests can mint compact tokens). The tenant claim is
`KAVACH_OIDC_TENANT_CLAIM` (default `tenant`).

`KAVACH_OPERATOR_TOKEN` is removed from `.env.example` and from the
Compose API environment. `SubstrateConfig.operator_token` is removed.
There is no static operator secret left to leak.

**2. Three FastAPI dependencies, one verifier.**

- `require_operator` — role `operator` or `admin`
- `require_auditor` — role `auditor`, `operator`, or `admin` (read paths)
- `require_admin` — role `admin` only

Revoke-agent and revoke-credential (ADR-0020) require `admin`.
Evidence export requires `auditor` (or above). Mutations of live
control state require `operator` (or admin).

**3. Keycloak ships in Compose.** `docker-compose.yml` gains a
`keycloak` service (`quay.io/keycloak/keycloak`, `start-dev` for the
reference stack) importing a realm that defines the three roles, a
`kavach` client, and the tenant claim. The API depends on it. A short
note in the on-prem runbook records how an operator logs in. This is
the reference IdP, not a mandate that a partner cannot front Kavach
with another OIDC issuer: any issuer that serves a JWKS and the claims
above satisfies the verifier.

**4. Tests do not boot Keycloak.** Unit and e2e tests mint RS256
tokens with an in-process keypair and point the verifier at an
in-process JWKS. A real-Keycloak test lives under `tests/integration/`
and is skipped unless `KAVACH_OIDC_ISSUER` is set to a reachable
issuer, following the same import-time env gate as the Postgres
integration tests. CI stays green without a Keycloak container.

**5. The `/v1` contract change is the operator security scheme.** Agent
routes keep `bearerAuth` (holder credential or Kavach session JWT).
Operator, auditor, and admin routes use an OIDC bearer scheme. This is
a breaking change for callers that sent `KAVACH_OPERATOR_TOKEN`, and it
is intentional: that secret is the thing tenet 04 says must go. ADR-0016's
"frozen `/v1`" rule is amended by this ADR for the operator security
scheme only. Request and response bodies do not change.

## Consequences

**Positive:**

- Operators are individual principals with an expiry, an audience, a
  role, and a tenant. Shared-password operator access is gone.
- The same verifier accepts Keycloak or any conforming OIDC issuer, so
  a partner IdP does not require a code change.
- Tests stay deterministic. The gate "no static operator secret in
  `.env.example`" is checkable with `grep`.

**Negative:**

- On-prem now has a sixth service. Keycloak's datastore in the
  reference stack is its own embedded DB (`start-dev`); production
  partners should point Keycloak at Postgres. This ADR does not
  automate that.
- Every existing operator client, demo harness, and e2e test must send
  a real JWT. The migration is mechanical (mint a test token) but it
  touches every operator call site.
- JWKS fetching needs a cache and a failure mode. If the IdP is
  unreachable, operator routes fail closed (401), which is correct and
  which will page someone. Agent routes do not depend on the IdP.
- Clock skew. The verifier allows a small leeway (default 30 seconds)
  on `exp`/`nbf`. Larger skew is an operational problem, not something
  the substrate silently absorbs.

## Alternatives Considered

- **Keep the static token behind a config flag "for demos".**
  Rejected. A flag that reintroduces the Weak control will be left on.
  Demos mint a short-lived operator JWT the same way tests do.
- **Authenticate operators with the Pramana SDK.** Rejected.
  Pramana verifies agent holder credentials (ADR-0015). Operators are
  humans in the partner's IdP. Conflating them breaks ADR-0003 and
  forces every partner to issue agent-shaped credentials to staff.
- **Build a miniature IdP inside Kavach.** Rejected. Keycloak (or the
  partner's existing IdP) already does registration, password policy,
  MFA, and revocation. Re-implementing that is out of scope and a
  liability.
- **Require a live Keycloak in CI.** Rejected. It makes every unit run
  depend on a container pull. The in-process JWKS covers the verifier;
  one gated integration test covers the real issuer.

## References

- [ADR-0004](0004-self-hosted-postgres-on-yotta.md) — perimeter and data residency.
- [ADR-0016](0016-external-api-surface-and-versioning.md) — `/v1` security schemes; amended here for operator auth only.
- [ADR-0017](0017-on-prem-deployment-posture.md) — Compose is where Keycloak is added.
- [ADR-0020](0020-revocation-and-credential-lifetime.md) — agent credential lifetime; revoke endpoints require `admin`.
- OpenID Connect Core 1.0; RFC 7517 (JWKS); RFC 7519 (JWT).
- NIST tenet 04, `docs/compliance/nist-agentic-iam-mapping.md`.
