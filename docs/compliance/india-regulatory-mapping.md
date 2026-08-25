# India Regulatory Mapping — RBI / SEBI / IRDAI / DPDP

Kavach's primary market is Indian BFSI ([ADR-0005](../adr/0005-accountability-positioning.md)).
This document maps the supervisory expectations most relevant to
agent accountability onto implemented Kavach mechanisms.

Status legend: **Implemented** · **Partial** · **Planned**.

## Cross-cutting: data residency

Self-hosted PostgreSQL 16, deployable on Yotta Yntraa or any in-perimeter
host ([ADR-0004](../adr/0004-self-hosted-postgres-on-yotta.md),
[ADR-0017](../adr/0017-on-prem-deployment-posture.md)). No data leaves the
partner's perimeter; there is no Kavach SaaS callback.

## RBI (banking / NBFC)

| Expectation | Kavach mechanism | Status |
|-------------|------------------|--------|
| Audit trail for every decision touching money/credit | HMAC-chained `audit_records`; signed evidence export | Implemented |
| Maker-checker / human authorization on sensitive actions | Graduated step-up to a human operator (Art. 14 analogue) | Implemented |
| Accountability of automated decisions | `DecisionEmitted` with evidence/reasoning/confidence/`decided_by` | Implemented |
| IT governance / change control | ADR-governed change process; versioned schemas; explicit migrations | Implemented |
| Data localisation (RBI storage directions) | Self-hosted Postgres in-perimeter | Implemented |
| Incident reporting | Event log + feedback loop provide the substrate; reporting workflow Planned | Partial |

## SEBI (markets / brokers / PMS)

| Expectation | Kavach mechanism | Status |
|-------------|------------------|--------|
| Pre-trade controls / supervision of automated order flow | Policy capability gates `trading.*` actions (Trading use case rule set) | Planned (Trading use case skeleton) |
| Audit and surveillance trail | Event log + audit chain | Implemented |
| Accountability for advice/decisions | Decision events with reasoning | Implemented |

## IRDAI (insurance)

| Expectation | Kavach mechanism | Status |
|-------------|------------------|--------|
| Auditability of automated underwriting/claims decisions | Decision events + evidence export | Implemented (substrate); use case Planned |
| Human oversight of high-impact decisions | Step-up escalation | Implemented |

## DPDP Act 2023 (data protection)

| Expectation | Kavach mechanism | Status |
|-------------|------------------|--------|
| Data minimisation | Sensitive records referenced by id, not inlined in events ([ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md)) | Implemented |
| Purpose limitation / access control | Tenant-scoped access; operator vs agent principals ([ADR-0016](../adr/0016-external-api-surface-and-versioning.md)) | Partial |
| Records of processing | Event log is an inherent record of processing | Implemented |
| Data principal rights workflows (erasure, access) | Planned (requires reference-record lifecycle tooling) | Planned |

## Gaps and next steps

- Trading (SEBI) and Credit/Insurance (RBI/IRDAI) use case rule sets.
- Incident reporting and DPDP data-principal-rights workflows.
- Formal DPA with each partner (template in `docs/security/`).
