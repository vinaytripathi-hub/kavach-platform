# NIST Design Tenets for Agent Identity Management — Kavach Mapping

This document maps the ten design tenets published by NIST / NCCoE in
*Design Tenets for Agent Identity Management Systems* (Cybersecurity
Insights blog, 27 October 2026 — Booth, Fisher, Galluzzo, Clancy) onto
concrete, implemented Kavach + Pramana mechanisms. It is the artifact an
auditor, a BFSI CISO, or an architecture-review board reads to see
*which running feature* satisfies *which tenet* — not an intention, a
mechanism.

    10|Scope note. Kavach is the operational accountability layer; the
cryptographic identity root is provided by the [Pramana
Protocol](https://github.com/vinaysflow/pramana-protocol), consumed
through the `CredentialVerifier` Protocol
([ADR-0003](../adr/0003-pramana-kavach-separation.md),
[ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
Tenets rooted in identity (01, 02) are satisfied jointly by Pramana and
Kavach; the remaining tenets are owned by Kavach.

Status legend: **Implemented** (in the prototype) · **Partial**
    20|(mechanism present, hardening or integration pending) · **Planned**.

## The ten tenets

| # | Tenet | Primary mechanism | Evidence in code / docs | Status |
|--:|-------|-------------------|-------------------------|--------|
| 01 | **Distinct Agent Identification** — unique, cryptographically verifiable agent identity, distinguishable from humans and service accounts; distinct IAM lifecycle | Agents authenticate via a Pramana credential verified by the `sdk_bridge`; the API models agents and operators as separate principal classes and enforces that a token can only act as its own `agent_id` | [`VerifiedAgent`](../../kavach/capabilities/sdk_bridge/contracts.py); [`AgentPrincipal` / `OperatorPrincipal`](../../kavach/api/security.py); `_ensure_same_agent` in [`app.py`](../../kavach/api/app.py) | Partial (cryptographic distinctness requires the Pramana adapter; the prototype default is a non-cryptographic fake verifier) |
| 02 | **Agent Linking, Delegation & Attenuation** — originator and agent cryptographically linked throughout execution; downstream scopes attenuate | `verify_delegation_chain` returns an `effective_scope` consumed by `VerifiedAgent.authorizes()`; every decision event carries `decided_by` and the delegation context; audit chain preserves linkage across the sequence | [`LocalPramanaAdapter`](../../kavach/capabilities/sdk_bridge/_internal/pramana_adapter.py); [`DecisionEmitted.decided_by`](../../kavach/events/schemas/decision_primitives.py); [ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md) | Partial (attenuation is a Pramana property; sub-agent chains and anonymous/pseudonymous consumer flows not yet exercised in Kavach) |
| 03 | **Least & Zero Standing Privilege** — minimum scope per task; separation of duties; no persistent rights when idle | Policy engine is **default-deny** per rule set; action-type glob + scope check gate every decision; action schema is provisioned, not discovered at runtime | [`PolicyRuleSet.default_effect`](../../kavach/capabilities/policy/_internal/rules.py); [`PolicyEngine.evaluate`](../../kavach/capabilities/policy/_internal/engine.py); [`VerifiedAgent.authorizes`](../../kavach/capabilities/sdk_bridge/contracts.py) | Partial (no "zero standing privilege when idle" model; no formal Separation-of-Duties primitive; scopes persist for credential lifetime) |
| 04 | **Short-Lived, Dynamic & Revocable Authorization** — JIT, time-bounded, audience-specific; continuous runtime verification; no long-lived bearer tokens | Agent credential is verified on every request against `expected_audience`; idempotency keys dedupe replays; operator and agent principals are separated and tenant-scoped | [`require_agent`](../../kavach/api/security.py); [`_idempotent`](../../kavach/api/app.py); [`SubstrateConfig.expected_audience`](../../kavach/composition/config.py) | Weak (no TTL enforcement, no revocation endpoint, no context-drift triggers; the operator token is a static shared secret in the prototype) |
| 05 | **Human-in-the-Loop Triggers** — risk-threshold-driven escalation with sufficient context; consent-fatigue aware | Policy engine returns `step_up` for high-impact actions; `StepUpRequested` carries reason + `required_role`; operators resolve with `StepUpResolved` whose `decided_by: operator:<id>` is signed into the audit chain | [`PolicyEngine.evaluate`](../../kavach/capabilities/policy/_internal/engine.py); [`StepUpRequested` / `StepUpResolved`](../../kavach/events/schemas/stepup.py); `POST /v1/decisions/{id}/step-up/resolve`; step-up queue projection | **Implemented** (consent-fatigue safeguards — escalation batching, context summaries, rate caps — not yet modeled) |
| 06 | **Mandates and Constraints** — cryptographically signed mandate statements defining intended outcomes and constraints; verifiable downstream | The decision substrate records intent-adjacent fields (`decided_by`, `reasoning`, matched rule) and signs them into the audit chain; action schemas are provisioned per use case | [`DecisionEmitted`](../../kavach/events/schemas/decision_primitives.py); use-case `PolicyRuleProvider` ([customer_service](../../kavach/usecases/customer_service/policy_rules.py)) | **Planned** (no `MandateIssued` artifact yet — the biggest green-field capability) |
| 07 | **Architectural Separation of Policy from Reasoning** — policy enforcement is architecturally outside the LLM; prompts cannot expand permissions | Three-layer architecture: the LLM/agent is outside the substrate and calls `POST /v1/agents/{id}/decisions`; `PolicyEngine` is a pure deterministic evaluator with no model in the loop; agent-presented tokens are verified out-of-band | [ADR-0001](../adr/0001-three-layer-architecture.md); [ADR-0007](../adr/0007-modular-capability-architecture.md); [`PolicyEngine`](../../kavach/capabilities/policy/_internal/engine.py); [`require_agent`](../../kavach/api/security.py) | **Implemented** |
| 08 | **Deterministic Access Decisions** — deterministic primary mechanism; probabilistic signals are inputs, not primary deciders | Decision confidence is `Confidence(kind="rule_deterministic", score=1.0)` for policy outcomes; trust (`TrustAssessment`) and data sufficiency (`DataSufficiency`) are modeled as *inputs* with explicit sufficiency bands | [`rule_deterministic`](../../kavach/events/schemas/decision_primitives.py); [`TrustAssessment`](../../kavach/events/schemas/trust.py); [ADR-0013](../adr/0013-multimodal-data-sufficiency.md); [ADR-0014](../adr/0014-multidimensional-trust-substrate.md) | **Implemented** |
| 09 | **Continuous Monitoring** — agent-specific metrics, thresholds, anomaly detection at agent scale and velocity | Read-side projections (timeline, trust, step-up queue) materialise agent behaviour; `TrustAssessmentEmitted` emits every decision; `DecisionFeedbackRecorded` closes the FP/FN loop; signed webhooks exfiltrate events to partner SIEM | [`query/projections`](../../kavach/query/projections/); [`TrustAssessmentEmitted`](../../kavach/events/schemas/trust_events.py); [`DecisionFeedbackRecorded`](../../kavach/events/schemas/feedback.py); [ADR-0009](../adr/0009-read-side-projections.md) | Partial (no anomaly detector in substrate; `AnomalyDetected` is named as planned in [ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md)) |
| 10 | **Immutable Evidence** — unbroken, tamper-evident, append-only chain of custody; logging infrastructure independent of the agent | HMAC-SHA256 hash chain written **in the same transaction** as every event append; `AuditExporter` produces time-bounded, agent-scoped evidence packs with a detached `SignatureManifest` that any holder of the signing key can independently verify | [`AuditChainWriter`](../../kavach/capabilities/audit/_internal/chain.py); [`AuditExporter`](../../kavach/capabilities/audit/_internal/exporter.py); `POST /v1/audit/exports`; [ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md) | **Implemented** (software-held key; HSM/KMS and per-tenant chain-head lock are the stated hardening items) |

## How the tenets layer

NIST notes that most real attacks are mitigated by a combination of
    40|tenets, not a single one. The Kavach substrate implements several of
these combinations as design properties:

- **Confused-deputy attacks** (prompt injection convinces a broadly-
  scoped agent to execute an action it otherwise would not) are
  mitigated by the combination of tenet 02 (`effective_scope` from the
  verified delegation), 03 (default-deny policy), 07 (reasoning outside
  the decision engine), and 08 (deterministic enforcement). All four
  are mechanisms in Kavach today.
- **Credential compromise** (stolen bearer token used for persistent
    50|  unauthorised access) is mitigated by 01 (distinct agent identity so
  compromise is bounded to one agent), 04 (short-lived, revocable
  authorization — **the weakest link in the current prototype**), and
  10 (every subsequent action is signed into an append-only chain, so
  the blast radius is reconstructable).
- **Silent high-impact action** (a malfunctioning agent executes an
  irreversible transaction) is mitigated by 05 (step-up triggers) and
  10 (immutable evidence). Both are implemented.
- **Audit tampering by a compromised agent** is mitigated by 10
  (logging infrastructure independent of the agent, chained and signed)
    60|  and 06 (originator intent cryptographically signed and preserved).
  Tenet 10 is implemented; tenet 06 is the second-most-material gap.

## Gaps and roadmap

Ranked by distance to a credible BFSI claim across all ten tenets:

1. **Tenet 06 — Signed mandates.** New `MandateIssued` event (signed by
   the task originator), presentation and verification at decision
   time, propagation to downstream calls. Reuses Pramana VC primitives.
   Natural next ADR.
    70|2. **Tenet 04 — Short-lived, revocable authorization.** Enforced
   token `exp` / `nbf` at the API boundary, revocation endpoint,
   context-drift triggers that can revoke in-flight. Replace the shared
   operator token with an IdP integration.
3. **Tenet 09 — Continuous monitoring with anomaly detection.** New
   `monitor` capability that computes agent-specific baselines over the
   existing projections and emits `AnomalyDetected` back into the
   policy engine as a step-up input.
4. **Tenet 03 — Zero standing privilege & Separation of Duties.**
   Session-scoped task tickets that attenuate the credential; a
    80|   declarative SoD check in `PolicyRuleSet`.
5. **Tenets 01 / 02 — Cryptographic maturity.** Default deployments
   should run on the Pramana adapter (or an equivalent EUDIW / IdP
   adapter), not the fake verifier.

Hardening already called out in [the security
whitepaper](../security/security-whitepaper.md) also applies: HSM/KMS
custody of the audit signing key (tenet 10), operator IdP + RBAC
(tenets 01, 04), chain-head lock for concurrent writers (tenet 10),
edge TLS/mTLS and rate limiting (tenet 04 blast-radius control).

    90|## Reference

- NIST / NCCoE, *Design Tenets for Agent Identity Management Systems*,
  Cybersecurity Insights blog, 27 October 2026. Harold Booth, Bill
  Fisher, Ryan Galluzzo, Tom Clancy.
- Companion mappings:
  [EU AI Act + eIDAS/EUDIW](./eu-regulatory-mapping.md);
  [India RBI/SEBI/IRDAI/DPDP](./india-regulatory-mapping.md).
