# Kavach Platform — On-Prem Deployment Runbook

This runbook installs the Kavach prototype on a single host inside the
partner's perimeter, satisfying the data-residency posture of
[ADR-0004](../adr/0004-self-hosted-postgres-on-yotta.md) and the
deployment posture of [ADR-0017](../adr/0017-on-prem-deployment-posture.md).

## Prerequisites

- A Linux host (or VM) with Docker Engine 24+ and the Docker Compose plugin.
- Outbound access only as the partner's policy requires; the stack runs
  fully in-perimeter. No Kavach SaaS callback is required.
- 2 vCPU / 4 GB RAM is sufficient for the prototype.

## Components

`docker compose` brings up the on-prem stack (ADR-0017, ADR-0021):

| Service | Image | Role |
|---------|-------|------|
| `db` | postgres:16 | Event log, projections, outbox (ADR-0004) |
| `keycloak` | quay.io/keycloak/keycloak:26.0 | Operator IdP (ADR-0021). Realm `kavach` is imported on start. |
| `api` | built from `Dockerfile` | FastAPI substrate (ADR-0016) |
| `worker` | built from `Dockerfile` | Outbox -> webhook and CAEP dispatcher |
| `console` | nginx | Operator console (static SPA) |

## Install

```bash
# 1. Configure secrets.
cp .env.example .env
# Edit .env: set strong KAVACH_AUDIT_HMAC_KEY, KAVACH_JWT_SECRET,
# KEYCLOAK_ADMIN_PASSWORD, and POSTGRES_PASSWORD. e.g.:
#   openssl rand -hex 32
# There is no static operator API secret. Operators sign in through
# Keycloak (realm kavach, client kavach). The imported demo user is
# `operator` / `change-me-operator` with role admin and tenant bank-1.
# Change that password before any partner deployment.

# 2. Build and start the stack.
docker compose up -d --build

# 3. Apply the database schema (explicit migration step; ADR-0017).
docker compose run --rm api alembic upgrade head

# 4. Verify health.
curl -s http://localhost:8000/v1/health
```

## Post-install smoke test

Drives the synthetic Customer Service flow end-to-end and asserts a
signed evidence pack verifies:

```bash
docker compose run --rm \
  -e KAVACH_API_URL=http://api:8000 \
  -e KAVACH_OPERATOR_ACCESS_TOKEN=$KAVACH_OPERATOR_ACCESS_TOKEN \
  api ./scripts/smoke-onprem.sh
```

(Or run `scripts/smoke-onprem.sh` from a host with the package installed,
pointing `KAVACH_API_URL` at the published API port.)

Expected output ends with `SMOKE TEST PASSED`.

## Operator console

Open `http://<host>:8080`. In the top bar set:

- API base URL: `http://<host>:8000`
- Tenant: your tenant id (e.g. `bank-1`)
- Operator token: a short-lived access token from Keycloak
  (`POST /realms/kavach/protocol/openid-connect/token`,
  grant type `password`, client `kavach`). The API rejects any static
  shared secret.

The four screens (Timeline, Trust, Step-up queue, Evidence export) read
the substrate's read-side projections (ADR-0009) through the API.

## Identity mode (ADR-0015)

The prototype defaults to `KAVACH_SDK_BRIDGE_MODE=fake` (offline,
deterministic agent tokens of the form `agent:<id>:<scopes>`). To enable
real Pramana credential verification:

1. Obtain the `aurvia-pramana` wheel (private index or build from the
   Pramana repo).
2. Place it in `vendor/` and uncomment the Pramana install lines in the
   `Dockerfile`.
3. Set `KAVACH_SDK_BRIDGE_MODE=pramana` in `.env` and rebuild.

## Backups

The event log is the source of truth (ADR-0009); projections rebuild from
it. Back up the Postgres volume `kavach_pgdata` (e.g. `pg_dump`). Restore
plus projection rebuild fully reconstitutes the read side.

## Production hardening (out of scope for the prototype)

- Terminate TLS / mTLS at a reverse proxy in front of `api` (ADR-0017).
- Point `KAVACH_DATABASE_URL` at a managed/HA Postgres.
- Move the audit signing key to an HSM/KMS (prototype uses a software key).
- Add metrics/log shipping; the substrate already emits structured logs.
