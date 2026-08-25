# ADR-0017 — On-prem deployment posture (Docker Compose first)

**Status:** Accepted
**Date:** 2026-06-12

## Context

ADR-0004 committed Kavach to self-hosted PostgreSQL 16 on Yotta Yntraa
for sovereign Indian data residency. The working prototype adds a
sharper requirement: a BFSI partner must be able to install and run
the entire platform inside their own perimeter, where data never
leaves their infrastructure. This is frequently a hard procurement
gate for Tier-A Indian BFSI.

The substrate, the API, the operator console, and a background worker
must therefore ship as a coherent, self-contained, installable unit.
Two realistic shapes exist:

1. **Single-host Docker Compose.** One `docker-compose.yml` brings up
   Postgres, the Kavach API, the console, and a worker. Trivial for a
   partner to run on a VM; minimal operational surface.
2. **Kubernetes / Helm.** Fits the operating model of large banks with
   existing clusters, but is materially more work to author and to
   support, and is overkill for a prototype.

## Decision

**1. Single-host Docker Compose is the prototype's deployment unit.**
`docker-compose.yml` at the repo root composes four services:

- `db` — PostgreSQL 16 (the ADR-0004 engine), with a named volume.
- `api` — the FastAPI substrate service (ADR-0016).
- `worker` — the outbox dispatcher / webhook sender / projection
  background worker (ADR-0008, ADR-0009).
- `console` — the operator console (ADR-0001 experiences layer).

A `Dockerfile` (multi-stage) builds the Python image shared by `api`
and `worker`; the console builds from its own stage or image.

**2. Configuration is environment-variable driven**, all prefixed
`KAVACH_` (the prefix `tests/conftest.py` already isolates). A
`.env.example` documents every variable. Secrets (DB password, JWT
signing key, audit HMAC key) are supplied at deploy time, never baked
into the image. A documented `KAVACH_SDK_BRIDGE_MODE` selects the real
Pramana adapter or the offline fake (ADR-0015).

**3. Migrations run as an explicit step, not implicitly on boot.**
Alembic `upgrade head` runs via a documented one-shot command (an
`api` entrypoint subcommand) so a partner controls schema changes.
This matches the ADR-0009 discipline that projection and capability
tables are migration-managed.

**4. A post-install smoke script** drives the synthetic-agent harness
against the running stack and asserts an end-to-end flow (action ->
decision -> step-up -> resolve -> signed evidence export verifies).
This is the partner's "did it install correctly" check and the demo's
backbone.

**5. mTLS and gateway concerns live at the deployment edge, not in
substrate code.** The prototype documents terminating TLS / mTLS at a
reverse proxy in front of `api`; the substrate trusts the
authenticated principal the proxy forwards plus its own bearer-token
verification (ADR-0016). This keeps transport security out of the
application code while remaining honest about the production posture.

**6. Kubernetes/Helm is deferred to partner demand.** The Compose
stack maps cleanly to a later Helm chart (one Deployment per service,
a StatefulSet for Postgres or an external managed DB). We do not author
the chart until a partner's operating model requires it.

## Consequences

**Positive:**

- A partner runs `docker compose up` on a VM inside their perimeter
  and has the whole platform; data residency (ADR-0004) is satisfied
  by where they run it.
- The four-service decomposition matches the substrate's runtime
  shape (API request path vs. background event processing) and
  previews a clean Helm mapping.
- The smoke script makes "is it working" objective.

**Negative:**

- Single-host Compose is not highly available. Accepted for a
  prototype; HA is a Helm/production concern.
- Two runtimes in the repo (Python substrate + Node console) increase
  build complexity. Mitigation: multi-stage Docker builds; the console
  is a thin projection reader.
- Running Postgres in Compose is fine for a prototype but a production
  deployment will likely point at a managed/HA Postgres. The config
  makes the DB endpoint an environment variable so this swap is trivial.

## Alternatives Considered

- **Kubernetes/Helm first.** Rejected for prototype: disproportionate
  authoring and support cost; Compose proves the same end-to-end story.
- **Single all-in-one container (Postgres + app + console).** Rejected:
  conflates lifecycles, defeats the managed-DB swap, and is poor
  practice even for a prototype.
- **Cloud-managed PaaS deployment.** Rejected: violates the on-prem,
  in-perimeter requirement that motivates this ADR.
- **Implicit migrate-on-boot.** Rejected: partners and auditors expect
  schema changes to be explicit, controlled steps.

## References

- ADR-0001 — Three-layer architecture (the four services map to layers)
- ADR-0004 — Self-hosted Postgres 16 on Yotta (the DB engine and residency)
- ADR-0008 — Events as primary output (the worker dispatches the outbox)
- ADR-0009 — Read-side projections (the worker can rebuild projections)
- ADR-0015 — Pramana SDK packaging (how the image gets Pramana; mode switch)
- ADR-0016 — External API surface (the `api` service contract)
- `docker-compose.yml`, `Dockerfile`, `.env.example` — the artifacts
- `scripts/smoke-onprem.sh` — the post-install end-to-end check
