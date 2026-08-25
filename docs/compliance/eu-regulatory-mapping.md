# EU Regulatory Mapping — EU AI Act & eIDAS 2.0 / EUDI Wallet

This document maps the obligations most relevant to agentic systems onto
concrete, implemented Kavach mechanisms. It is the artifact a compliance
officer or auditor reads to see *which running feature* satisfies *which
obligation* — not an intention, a mechanism.

Status legend: **Implemented** (in the prototype) · **Partial** (mechanism
present, hardening pending) · **Planned**.

## EU AI Act

| Article | Obligation (paraphrased) | Kavach mechanism | Evidence | Status |
|--------:|--------------------------|------------------|----------|--------|
| Art. 9 | Continuous risk management across the lifecycle | Policy capability evaluates every proposed action against a versioned rule set; default-deny outside the action schema; feedback events feed risk review | `PolicyEvaluated`, `DecisionEmitted`, `DecisionFeedbackRecorded` events; [ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md) | Implemented |
| Art. 12 | Automatic logging / record-keeping | Append-only event log; HMAC-SHA256 hash-chained audit records written transactionally per event | `events` table, `audit_records` chain, `GET /v1/audit/exports/{id}` | Implemented |
| Art. 13 | Transparency & interpretability of outputs | Every decision carries structured evidence, reasoning trace, confidence, and `decided_by` | `DecisionEmitted.evidence/reasoning/confidence`; decision log projection | Implemented |
| Art. 14 | Human oversight; ability to intervene | Graduated authority: routine actions auto-execute, high-impact actions return `step_up` to a human-in-the-loop who approves/rejects; rejections logged | `StepUpRequested`/`StepUpResolved`, `POST /v1/decisions/{id}/step-up/resolve`, step-up queue projection | Implemented |
| Art. 17 | Quality management system; documented processes | ADR-governed change process; TDD discipline; versioned event schemas; explicit migrations | `docs/adr/`, [ADR-0006](../adr/0006-tdd-discipline.md), [ADR-0010](../adr/0010-event-schema-versioning.md) | Implemented |
| Art. 25 | Responsibilities along the value chain (provider/deployer) | Accountability is a design decision: each action type maps to a process-owner model in the use-case rule set; the agent acts only within its provisioned action schema | Use-case `PolicyRuleProvider` ([customer_service](../../kavach/usecases/customer_service/policy_rules.py)); [ADR-0007](../adr/0007-modular-capability-architecture.md) | Implemented |
| Art. 26 | Deployer obligations (human oversight, logs) | Operator console surfaces the step-up queue and evidence; logs retained in the event log | Operator console; audit export | Partial |
| Art. 72 | Post-market monitoring | Feedback loop converts operator labels into monitored signals (FP/TP) | `DecisionFeedbackRecorded`; [ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md) | Partial |

### The four common objections, answered by mechanism

1. *"Accountability collapses in multi-agent systems."* The action schema
   is provisioned, not discovered at runtime; each decision records
   `decided_by` and the agent's delegation context. Accountability is a
   design property (ADR-0007 + ADR-0012), not a runtime accident.
2. *"Art. 14 oversight contradicts autonomy."* The system is designed so
   intervention is possible: actions within schema execute, defined
   classes escalate (`step_up`), everything else is denied and logged.
3. *"Agents are an unauditable black box."* Each interaction is an
   HMAC-chained, signed record (`audit_records` + signature manifest),
   independently verifiable.
4. *"The Act is an entirely new framework."* It maps onto existing
   SDLC/governance: risk management (Art. 9), QMS (Art. 17), logging
   (Art. 12) — all realized by the substrate's existing primitives.

## eIDAS 2.0 / EU Digital Identity Wallet (EUDIW)

The substrate's agent identity root is pluggable behind the `sdk_bridge`
`CredentialVerifier` Protocol ([ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
For EU deployments, an EUDIW-attested credential adapter substitutes for
the Pramana adapter without substrate changes.

| eIDAS 2.0 / EUDIW concern | Kavach mechanism | Status |
|---------------------------|------------------|--------|
| Verifiable attestations (PID / EAA) as the identity root | `CredentialVerifier` Protocol; verification result becomes `credential_integrity` trust input | Partial (Pramana adapter today; EUDIW adapter Planned) |
| Selective disclosure / data minimisation | Evidence stored by reference for sensitive records; only minimal attributes inline ([ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md)) | Implemented |
| Relying-party verification & audit | Verification outcome recorded as evidence on the gated decision | Implemented |
| Wallet-attested delegation chains | `verify_delegation_chain` via the bridge; `effective_scope` feeds authorization | Partial |

### EUDIW adapter (Planned)

A `EudiwCredentialVerifier` implementing the same `CredentialVerifier`
Protocol would verify an EUDIW presentation (PID + EAA), map the holder to
`agent_id`, and derive scopes from wallet-attested delegation. Because the
substrate depends only on the Protocol, this is a new adapter plus
composition wiring — no change to policy, audit, events, or projections.

## Gaps and next steps

- HSM/KMS-backed audit signing key (prototype uses a software key).
- Full post-market monitoring dashboards over the feedback loop.
- EUDIW adapter and conformance against a reference wallet.
- DPIA / records of processing alignment with the partner's DPO.
