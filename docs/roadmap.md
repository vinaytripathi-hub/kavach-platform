# Kavach Platform — Working Prototype Roadmap

This roadmap tracks the build from the W01-S02 foundation (ADRs +
skeleton) to a complete working prototype deployable on-prem via Docker
Compose. It complements, and does not supersede, the substrate-first
build order of [ADR-0002](adr/0002-substrate-first-build-order.md).

## Target

A partner-deployable prototype in which a synthetic agent runs a
Customer Service flow end-to-end: Kavach records cryptographically
chained evidence, evaluates policy with step-up escalation, emits
multidimensional trust assessments, and an operator console shows it
all — installed on a single host via Docker Compose, inside the
partner's perimeter (data residency per
[ADR-0004](adr/0004-self-hosted-postgres-on-yotta.md)).

## Locked decisions

- **Pramana SDK** — consumed behind a Protocol; offline fake plus real
  adapter; published to a private index or vendored wheel for on-prem
  ([ADR-0015](adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
- **API** — REST + OpenAPI 3.1, `/v1` URL versioning composed with
  per-event schema versioning
  ([ADR-0016](adr/0016-external-api-surface-and-versioning.md)).
- **Deployment** — single-host Docker Compose first; Helm deferred
  ([ADR-0017](adr/0017-on-prem-deployment-posture.md)).
- **Stubbed for prototype** — `enrichment` and `dpi` capabilities,
  Credit Underwriting and Trading use cases (skeletons), HSM key
  custody (software keys).

## Phases and gates

| Phase | Scope | Gate |
|------:|-------|------|
| 1 | ADRs 0015-0017, `docs/api/openapi.yaml` v1, versioned event schemas, this roadmap | OpenAPI parses; event round-trip replay tests green |
| 2 | `storage` capability, Alembic migrations, event bus with transactional outbox | Append + replay an event stream against Postgres and SQLite |
| 3 | `audit`, `policy`, `sdk_bridge` capabilities; `composition`; `query` projections | Synthetic end-to-end decision; evidence chain verifies cryptographically |
| 4 | FastAPI service, auth middleware, idempotency, webhook dispatcher, reference client | API serves the frozen contract; integration tests green |
| 5 | `customer_service` use case, operator console, synthetic agent harness | Live demo: KYC -> step-up -> resolve -> signed evidence export verifies |
| 6 | Docker Compose, Dockerfile, runbook, smoke script, compliance + security pack | `docker compose up` then smoke script passes end-to-end |

## Event vocabulary (frozen v1)

Eight core events, all versioned per
[ADR-0010](adr/0010-event-schema-versioning.md) and registered for
replay:

- `ActionExecuted` — ingress record of an executed action
- `PolicyEvaluated` — a rule set was run for a proposed action
- `DecisionEmitted` — decision-grade event with evidence, reasoning,
  confidence, decided_by ([ADR-0012](adr/0012-decision-events-with-evidence-and-reasoning.md))
- `EvidenceRecorded` — evidence captured against an agent/decision
- `TrustAssessmentEmitted` — multidimensional trust tensor
  ([ADR-0014](adr/0014-multidimensional-trust-substrate.md))
- `DecisionFeedbackRecorded` — FP/FN feedback loop
- `StepUpRequested` — policy escalates to a human (Article 14)
- `StepUpResolved` — operator approves/rejects a step-up

## Runtime topology

```
agent ──▶ FastAPI (/v1) ──▶ policy ──▶ decision (allow/deny/step_up)
                       └──▶ audit  ──▶ HMAC-chained evidence
                                  ──▶ event bus + outbox ──▶ projections ──▶ console
                                                          └─▶ webhooks ──▶ partner
```

## Status

- Phase 1: in progress (ADRs and contracts landed; event schemas
  implemented and tested).
- Phases 2-6: pending.

Cross-repo dependency: publishing `aurvia-pramana` to a private index
happens in the Pramana repository and is tracked there
([ADR-0015](adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
