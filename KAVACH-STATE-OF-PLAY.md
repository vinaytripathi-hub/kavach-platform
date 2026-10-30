# Kavach Platform — Comprehensive State of Play

> A self-contained, repo-grounded briefing for an external technical discussion.
> Every claim below is drawn from the actual artifacts in this repository — the
> 19 ADRs, the frozen `/v1` OpenAPI contract, the compliance and security packs,
> the strategy brief, the roadmap, and the git history — not from memory.
>
> It describes **what has shipped and is tested**, **how the architecture and the
> standards alignment were reasoned about**, and **where the build is heading**.
> Public technical posture only; no employer-specific or confidential content.

**Document map**

0. TL;DR snapshot
1. Thesis, problem, and market positioning
2. The Pramana relationship and the IP / licensing posture
3. How we thought about the standards (NIST, AP2, Verifiable Intent, FIDO, EU, India)
4. How we thought about the architecture (the 19-ADR reasoning)
5. The complete ADR index
6. What has been built (git-history narrative + capability/event/API surface)
7. Compliance and regulatory posture
8. Security posture (whitepaper, STRIDE threat model, DPA)
9. Testing and engineering discipline (the coverage work)
10. Current gate status
11. The phase plan ahead
12. Open questions worth discussing
13. Reference facts and repo map

---

## 0. TL;DR snapshot

- **What it is:** a proprietary, **source-available agent-accountability
  substrate for Indian BFSI** (banking, financial services, insurance). It is
  **not** an AI model. It is the deterministic governance/accountability layer
  *around* autonomous agents: it records what an agent did, on whose authority,
  within what bounds, with what evidence and outcome, and keeps a human in
  control of high-impact actions.
- **The spine of the thesis:** Kavach claims a **one-to-one mapping to the ten
  NIST/NCCoE *Design Tenets for Agent Identity Management Systems*** (blog dated
  27 October 2026). Identity vendors address 1–2 tenets; policy-guardrail
  frameworks address 1–2 more. Nobody covers the full post-identity
  accountability set (tenets 03–10) as implemented, deterministic mechanisms.
- **Repo:** `aurvia-kavach` (dist) / `kavach` (import), public at
  `github.com/vinaytripathi-hub/kavach-platform`, branch `main`, **22 commits**.
- **Latest commit:** `d34e774` — "Phase 1.5: installable Python + TypeScript
  SDKs and a Node reference agent."
- **Where we are:** **Phase 1 complete and hardened. Phase 1.5 (SDKs)
  code-complete and verified from built artifacts; gate is OPEN** pending the
  first public-registry publish (needs the `@aurvia` npm scope + PyPI Trusted
  Publishing — registry identity the agent cannot assume).
- **Test suite (measured, not recalled):** **163 tests collected; 161 pass
  locally + 2 real-Postgres integration tests that skip without a live DB;
  85.44% coverage** (CI gate 80%). mypy strict + ruff clean. GPG-signed commits,
  protected `main`.
- **NIST tenet scorecard (from `docs/compliance/nist-agentic-iam-mapping.md`):**
  6 Implemented (05, 06, 07, 08, 09, 10), 3 Partial (01, 02, 03), 1 Weak (04).
  Strategy brief's self-assessment: **~55–60% as a working prototype, ~75% as a
  design.**

---

## 1. Thesis, problem, and market positioning

Source: `docs/strategy/agent-trust-platform-brief.md`, `docs/adr/0005-accountability-positioning.md`, `README.md`.

**The problem.** Autonomous AI agents are starting to take *consequential*
actions inside regulated institutions — moving money, verifying identity,
underwriting, trading, handling customer data. The question a regulator, internal
auditor, or risk officer asks is **not** "is the model accurate?" It is: *who
authorized this action, within what bounds, and can you prove what happened?*
"The agent denied the transaction" is not defensible; "rule R fired on evidence
E with confidence C, decided by D, under mandate M, with a human approving the
step-up, on a tamper-evident chain you can verify" is.

**The positioning (ADR-0005).** Three deliberate stances:
1. **Accountability, not identity.** Identity (Microsoft Entra Agent ID, AWS
   AgentCore) is necessary but not the differentiator. Pramana provides the
   identity primitives; **Kavach supervises what identified agents *do*** — the
   post-identity accountability layer.
2. **BFSI-first, not BFSI-only.** BFSI is the wedge (compliance urgency,
   willingness to pay). The substrate is architected to generalize to other
   regulated verticals (healthcare, government, enterprise SaaS).
3. **Indian-sovereign, globally relevant.** India-first market; substrate
   reusable globally.

Brand strata: **Aurvia** = the company / trust infrastructure · **Pramana** =
the open-source identity substrate beneath · **Kavach** = the BFSI commercial
layer above. One-liner: *"Agent Accountability for Indian BFSI."* Tagline: *"The
trust substrate for AI agents deployed in banking, financial services, and
insurance."*

**The claim (strategy brief).** *"Kavach is the only architecture we are aware
of that maps one-to-one to the ten design tenets published by NIST/NCCoE."* The
platform is decomposed into **nine modules**, each owning one or more tenets
behind a stable Protocol-bounded interface, so a deployer plugs internal systems
(identity, HSM, policy store, audit lake, SIEM, notification channel, event bus)
into matching adapters without touching the core:

| Module | NIST tenets owned | State (per brief) |
|---|---|---|
| Identity | 01 Distinct ID · 02 Linking & Delegation | Prototype |
| Mandate | 06 Mandates & Constraints | **Built** (ADR-0018; brief predates it) |
| Session & Authorization | 03 Least/Zero Standing · 04 Short-lived & Revocable | Partial |
| Policy Engine | 07 Separation of Policy from Reasoning · 08 Deterministic Decisions | Built |
| Human-in-the-Loop | 05 HITL Triggers | Built |
| Audit Chain & Evidence | 10 Immutable Evidence | Built (software key) |
| Monitoring & Anomaly | 09 Continuous Monitoring | **Built** (ADR-0019; brief predates it) |
| Projections & Console | cross-cutting | Built |
| Egress & Outbox | cross-cutting | Built |

**The ask (target = BFSI deployers).** A **6–8 week scoped POC** on one agentic
use case *inside the deployer's perimeter*: wire the Identity adapter to the
deployer's identity service; wire the Audit sink + signing adapter to the
deployer's audit lake and HSM; run the **Customer Service use case** end-to-end
(*KYC → step-up → operator resolution → signed evidence export, verified by
internal audit*); deliver a **10-tenet scorecard** plus a prioritized plan for
the remaining modules.

---

## 2. The Pramana relationship and the IP / licensing posture

Sources: `docs/adr/0003-pramana-kavach-separation.md`, `docs/adr/0015-pramana-sdk-packaging-and-agpl-posture.md`, `NOTICE`, `LICENSE`.

This is a deliberately **two-layer** story, and the boundary is the single most
load-bearing IP decision in the project.

- **Pramana** is a *separate*, **AGPL-3.0 open-source** identity/credential/
  delegation/audit/commerce substrate (repo
  `github.com/vinaysflow/pramana-protocol`). "The public version is the only
  version" — no internal fork.
- **Kavach** is **proprietary** ("All Rights Reserved", licensed-not-sold), built
  *on top of* Pramana and consuming it **only through Pramana's public Python SDK
  boundary** (`import pramana`) — never by vendoring or importing Pramana source.

**Three operational rules (ADR-0003) keep the boundary mechanically defensible:**
1. Kavach contains **no Pramana source code** — all Pramana functionality is
   reached through the public SDK (`import pramana`). The `NOTICE` file durably
   states: *"Kavach Platform contains NO Pramana Protocol source code."*
2. Pramana development happens upstream in the Pramana repo.
3. Kavach depends on a specific **published** version, declared in
   `pyproject.toml` as `aurvia-pramana>=0.3.0,<1.0.0`, pinned by lockfile in
   production. Dev uses the "Pattern B editable install" to override with a local
   checkout for fast feedback.

**The adapter mechanism (ADR-0015).** The `sdk_bridge` capability declares a
`CredentialVerifier` / `DelegationVerifier` Protocol in `contracts.py`; the
concrete adapter that calls `import pramana` lives in `sdk_bridge/_internal/`.
**No other capability imports Pramana.** Two interchangeable implementations ship
behind the Protocol: a built-in `FakeCredentialVerifier` (deterministic, no SDK —
offline demos and tests) and a `LocalPramanaAdapter` wrapping the real SDK
(real deployments), selected by configuration. Swapping the identity root for an
EUDI Wallet, a deployer IdP, or Entra Agent ID is a *new adapter behind the same
Protocol*, not a substrate rewrite.

**Why the AGPL boundary holds.** Pramana is installed like any other
OSS dependency (FastAPI, SQLAlchemy); Kavach's proprietary source contains no
AGPL-licensed code, so there is no reciprocal-licensing obligation on Kavach, and
Pramana's own source availability satisfies the AGPL network-use clause. The
`pramana` dependency is an **optional extra** — the default install and the
fake-mode prototype build without it; the interim distribution bridge is a
vendored wheel from a pinned revision (logistics, not an IP change).

**LICENSE / NOTICE specifics.** LICENSE is proprietary: *"No license granted by
mere possession,"* *"unauthorized use prohibited,"* *"no warranty,"* licensing
inquiries to `vinay@aurviaglobal.com`. NOTICE attributes foundational
dependencies, records Pramana's AGPL-3.0 license and repo, and points to
`docs/ip-provenance.md` for the full IP-separation analysis.

---

## 3. How we thought about the standards

This is the part of the story that makes the architecture *not arbitrary*: every
accountability primitive maps to a published or emerging standard, and the
compliance pack crosswalks each one.

### 3.1 NIST / NCCoE — the organizing spine

Source: `docs/compliance/nist-agentic-iam-mapping.md`. The anchor is NIST/NCCoE,
*Design Tenets for Agent Identity Management Systems* (Cybersecurity Insights
blog, **27 October 2026**; authors Harold Booth, Bill Fisher, Ryan Galluzzo, Tom
Clancy), which defines **ten design tenets**. Kavach's crosswalk:

| # | Tenet | Status | Mechanism in Kavach |
|---|---|---|---|
| 01 | Distinct Agent Identification | **Partial** | cryptographic distinctness needs the Pramana adapter; prototype default is the non-cryptographic fake verifier |
| 02 | Agent Linking, Delegation & Attenuation | **Partial** | attenuation is a Pramana property + mandate strict-subset; sub-agent chains not yet fully exercised |
| 03 | Least & Zero Standing Privilege | **Partial** | no "zero standing privilege when idle"; no formal Separation-of-Duties primitive yet |
| 04 | Short-Lived, Dynamic & Revocable Authorization | **Weak** | *the weakest link* — no token TTL enforcement, no general revocation endpoint, operator token is a static shared secret |
| 05 | Human-in-the-Loop Triggers | **Implemented** | graduated `step_up` → operator resolve (EU AI Act Art. 14) |
| 06 | Mandates and Constraints | **Implemented** | signed `Mandate` + constraints + policy integration (ADR-0018) |
| 07 | Architectural Separation of Policy from Reasoning | **Implemented** | deterministic `PolicyEngine` separate from the agent's reasoning |
| 08 | Deterministic Access Decisions | **Implemented** | rule-based, replayable decisions; probabilistic signals are advisory only |
| 09 | Continuous Monitoring | **Implemented** | `monitor` capability + four detectors (ADR-0019) |
| 10 | Immutable Evidence | **Implemented** | HMAC-SHA256 hash-chained audit records, signed export (software key today) |

**How the tenets layer into attack mitigations:** confused-deputy → 02+03+07+08;
credential compromise → 01+04(weak)+10; silent high-impact action → 05+10; audit
tampering by a compromised agent → 10+06. The ranked gap list is explicit:
(1) tenet 04 — enforce `exp`/`nbf` at the API boundary, add a general revocation
endpoint, replace the shared operator token with an IdP; (2) tenet 03 —
session-scoped task tickets + declarative SoD in `PolicyRuleSet`; (3) tenets
01/02 — run on the Pramana (or EUDIW/IdP) adapter, not the fake verifier.

### 3.2 The payments/mandate standards — AP2, Verifiable Intent, FIDO

Source: `docs/compliance/fido-agentic-standards-mapping.md` and the ADR-0018
addendum. The key insight, stated in the mapping: the specs define the *credential
shape*, but they **leave the runtime to the deployer** (transport/API, key
custody, enrollment/lifecycle, dispute workflow, regulatory evidence export for
PCI DSS / PSD2 / EU AI Act / DPDP / RBI). **Kavach is that runtime.** All three
efforts converge on the same shape: *a signed, bounded, originator-issued mandate
verified by deterministic code outside the agent's reasoning path.*

| Source | Version / date | What it specifies |
|---|---|---|
| **Google Agent Payments Protocol (AP2)** | **v0.2, 28 Apr 2026** | `mandate.checkout` + `mandate.payment` as SD-JWT; constraint vocabulary (`amount_range`, `allowed_payee`, `allowed_payment_instrument`, `budget`, `agent_recurrence`); a non-agentic **Trusted Surface** |
| **Mastercard Verifiable Intent** | **v0.1-draft, 18 Feb 2026** | layered SD-JWT: L1 identity → L2 user authorization → L3 agent execution, with **normative attenuation** (L3 must satisfy disclosed L2 constraints) |
| **FIDO Agentic Authentication TWG (AATWG)** | work commenced **28 Apr 2026** | verifiable user instructions, agent authentication, trusted delegation for commerce |

Kavach keeps `MandateVerifier` as the substrate Protocol with a family of
adapters: `FakeMandateVerifier` (offline), `AP2MandateVerifier` (ships today,
parses a Google AP2 SD-JWT payment chain), and planned `VIMandateVerifier` /
`PramanaMandateVerifier`. `MandateConstraint` keeps a `path`/`operator`/`value`
shape but registers AP2/VI constraint names; unknown constraint types **fail
closed** when a rule sets `mandate_required`.

### 3.3 EU — AI Act and eIDAS 2.0 / EUDI Wallet

Source: `docs/compliance/eu-regulatory-mapping.md`. Article-by-article:

| Article | Obligation | Kavach mechanism | Status |
|---|---|---|---|
| Art. 9 | Continuous risk management | default-deny policy + feedback events | Implemented |
| Art. 12 | Automatic logging / record-keeping | append-only event log + HMAC chain | Implemented |
| Art. 13 | Transparency / interpretability | evidence + reasoning + confidence + `decided_by` | Implemented |
| Art. 14 | Human oversight / intervention | graduated `step_up` → operator resolve | Implemented |
| Art. 17 | Quality management system | ADR process + TDD + versioned schemas | Implemented |
| Art. 25 | Responsibilities along the value chain | provisioned action schema + `decided_by` | Implemented |
| Art. 26 | Deployer obligations | operator console surfaces step-up + evidence | Partial |
| Art. 72 | Post-market monitoring | FP/TP feedback loop | Partial |

**eIDAS 2.0 / EUDIW:** agent identity root is pluggable behind the
`CredentialVerifier` Protocol; a `EudiwCredentialVerifier` is *Planned* and would
substitute for the Pramana adapter with no substrate change. Selective disclosure
/ data-minimisation (evidence by reference) is Implemented.

### 3.4 India — RBI / SEBI / IRDAI / DPDP

Source: `docs/compliance/india-regulatory-mapping.md`. The cross-cutting enabler
is **data residency**: self-hosted PostgreSQL 16 deployable on Yotta Yntraa or
any in-perimeter host (ADR-0004, ADR-0017); *no data leaves the partner's
perimeter; no Kavach SaaS callback*. Highlights:

- **RBI (banking/NBFC):** HMAC-chained audit for every money/credit decision
  (Implemented), maker-checker via step-up (Implemented), data localisation via
  self-hosted in-perimeter Postgres (Implemented), incident-reporting workflow
  (Partial).
- **SEBI (markets):** pre-trade controls gate `trading.*` (Planned — Trading
  use-case skeleton); audit/surveillance trail (Implemented).
- **IRDAI (insurance):** auditability of automated underwriting/claims
  (substrate Implemented; use case Planned); human oversight of high-impact
  decisions (Implemented).
- **DPDP Act 2023:** data minimisation by reference (Implemented), records of
  processing = the event log (Implemented), purpose limitation / tenant-scoped
  access (Partial), data-principal-rights workflows (Planned).

> **Note on MCP:** MCP (Model Context Protocol) is **not** a compliance standard
> and does not appear in the compliance pack. It is an *access surface* — Kavach
> ships an MCP server (§6.5) so agent hosts can reach the same operations as the
> REST API. It belongs to the architecture, not the standards crosswalk.

---

## 4. How we thought about the architecture (the 19-ADR reasoning)

The architecture is not incidental; it is 19 Accepted ADRs, each recording a
decision *and the rationale and the alternatives rejected*. This section captures
the reasoning, grouped by theme. (§5 is the flat index.)

### 4.1 Shape of the system

- **ADR-0001 — Three layers.** *Substrate* (the shared engine: events,
  capabilities, composition, query/projections — "what makes Kavach Kavach") ·
  *Use-case configs* (declarative rule sets/endpoints/projections that
  *configure* the substrate, not duplicate it) · *Experiences* (console,
  inspector, regulator export, customer views that read projections, never
  internal state). A middle path between a naive monolith and premature
  microservices. **Tests mirror the source tree exactly.**
- **ADR-0002 — Substrate-first build order.** Build the substrate before any use
  case, because *the moat is the substrate*. Guard against "a substrate that's
  just one use case's leftovers": every early capability must be justified by an
  anticipated use-case need.
- **ADR-0007 — Modular capabilities with formal extension points.** Every
  capability is `__init__.py` (the *only* public surface) + `_internal/` +
  `events.py` + `contracts.py` (dependencies declared as `typing.Protocol`) +
  optional `extension_points.py`. The **composition layer** (`build_substrate(…)`)
  wires concrete implementations to Protocols at startup; capabilities never
  instantiate their own dependencies. Costs ~15–20% more code; buys independent
  testability and *mechanical* sub-product extraction.
- **ADR-0011 — Sub-product extraction posture.** Capabilities are classified by
  extraction potential: **high** (Audit, Policy, Operator Console — designed to
  be standalone "Audit-as-a-Service" / "Policy-as-a-Service" products, held to
  stricter boundary discipline: no implicit cross-capability deps, self-contained
  data model and event vocabulary, independent versioning) vs **low** (enrichment,
  DPI bridge, sdk_bridge — Kavach-only) vs **mixed** (storage, composition,
  events). Pay the discipline cost only where it earns optionality.

### 4.2 How information flows

- **ADR-0008 — Domain events are the substrate's *primary output*.**
  Capabilities are event transformers; internal DB state is a private convenience,
  the event *schema* is the external contract. Pragmatic event-driven (state in
  Postgres for queryability, events emitted alongside), not pure event sourcing.
  Correctness is required at three layers: logic (inside a capability), event
  (at the boundary), system (across capabilities).
- **ADR-0009 — Read-side projections.** Experiences read materialized views under
  `kavach/query/projections/` — a top-level substrate concern, *not* inside any
  capability (projections are cross-capability views). Each ships a `handle()`
  and a `rebuild()`. **Hard rule: the event log is the source of truth; if a
  projection disagrees with the log, the projection is wrong — fix the handler
  and `rebuild()`, never edit the projection table.**
- **ADR-0010 — Event schema versioning.** Event schemas are *public API*. Each
  event has a stable name + integer `schema_version`. Three change classes:
  additive (no bump), compatible (no bump, changelog), breaking (new version,
  e.g. `AgentSessionStartedV2`, four-phase rollout, old versions archived but
  importable for replay). Breaking changes require an ADR before merge.

### 4.3 What makes a decision defensible

- **ADR-0012 — Decision events carry evidence, reasoning, confidence,
  decided-by.** Every decision event embeds four mandatory fields: `Evidence`
  (by reference for large/sensitive records, inline for compact), `ReasoningTrace`
  (kind = rule/model/composite/human; rule_id/model_id+version/features/steps),
  `Confidence` (rule-deterministic vs probabilistic-with-calibration vs
  human-judged), and `decided_by` (which entity produced the decision, distinct
  from the agent acted on). `DecisionFeedbackRecorded` closes the FP/TP loop and
  *accumulates labeled training data* through normal operation.
- **ADR-0013 — Multimodal data sufficiency.** Every data-dependent output carries
  a `DataSufficiency` band — **`cold` / `thin` / `warm` / `warm_stale`** — with a
  per-modality breakdown (observations, earliest/latest). The substrate is honest
  about *what it doesn't know*: a cold-start agent's trust is priors-driven, not
  authoritative, and downstream policy can require step-up/conservative defaults.
  Confidence and sufficiency are deliberately *distinct* (a rule can be
  confidence-1.0 on cold data). Default composition = worst modality's band.
- **ADR-0014 — Multidimensional trust substrate.** Trust is **a tensor, not a
  scalar.** A `TrustAssessment` holds a set of `TrustDimension`s (each with
  value, sufficiency, contributors, reason) plus a `CompositionSpec` (how a
  consumer rolls them into a scalar). Core substrate dimensions:
  `credential_integrity`, `behavioral_consistency`, `policy_compliance`,
  `outcome_quality`, `peer_alignment`; use cases extend with their own (e.g.
  `risk_calibration`). The multidimensional schema is used from the *first*
  assessment (may start one-dimensional) to avoid a later migration. "A neural
  trust score" is one *composition* over the substrate, not the architecture.

### 4.4 The accountability primitives (the newer ADRs)

- **ADR-0018 — Signed mandates and policy integration** (2026-10-27). A
  `Mandate` is a signed, bounded authorization from a task *originator*
  (human/service/agent/wallet) to an agent, with `action_scope`,
  `constraints[]` (`path`/`operator`/`value`), `issued_at`/`expires_at`,
  `nonce`, and optional `parent_mandate_id`. Verification lives behind a new
  `MandateVerifier` Protocol (mirroring ADR-0015). **Attenuation is enforced at
  verify time**: a sub-mandate's scope must be a strict subset and its
  constraints at least as tight as the parent's. The policy engine gains
  `mandate_covers_action` / `mandate_constraint_satisfied` operators and per-rule
  `mandate_required` + `mandate_originator_kinds`. Three audit events —
  `MandateIssued` / `MandatePresented` / `MandateRevoked` — and three endpoints
  (`POST /v1/mandates`, `GET /v1/mandates/{id}`, `POST /v1/mandates/{id}/revoke`)
  plus the `X-Kavach-Mandate` header on decisions. This **closes NIST tenet 06**
  and mitigates the confused-deputy attack: a broad credential cannot execute a
  mandate-required action without a mandate specifically covering it. Mandates are
  *not* in-prompt (that would be injectable — the exact failure mode this prevents).
- **ADR-0019 — Monitor capability and anomaly feedback loop** (2026-10-27). A new
  `monitor` capability reads the event stream, maintains per-tenant/per-agent
  baselines, and emits `AnomalyDetected` as a decision-grade signal under two
  non-negotiable constraints: **policy stays deterministic (tenet 08)** — a
  detector may be probabilistic internally but emits a *bounded* `severity`
  label (`info`/`warn`/`critical`); and **monitoring lives outside the policy
  engine (tenet 07)**. Four first-cut detectors: **rate** (decisions/min vs
  rolling mean, warn 3σ / critical 5σ), **outcome drift** (deny-rate shift),
  **scope expansion** (first appearance of a new action type), **confidence
  drop**. New events `AgentMetricSnapshot` / `AnomalyDetected` /
  `AnomalyAcknowledged`; a projection `AgentAnomalyCurrentRow` the policy engine
  reads as `agent.anomaly_severity`; endpoints
  `GET /v1/agents/{id}/anomalies`, `POST /v1/anomalies/{id}/acknowledge`,
  `GET /v1/agents/{id}/metrics`. **Closes NIST tenet 09.** Acknowledgement feeds
  `DecisionFeedbackRecorded` (ADR-0012's labeled-data pipeline).

### 4.5 Boundary, deployment, and discipline

- **ADR-0016 — External API surface** (2026-06-12). REST/HTTP described by a
  single **OpenAPI 3.1** doc (`docs/api/openapi.yaml`) = the contract. **URL
  major versioning `/v1`** (composed with per-event `schema_version`). RFC 7807
  `application/problem+json` errors with stable `type`/`code`. Idempotency via
  `Idempotency-Key` deduped by `(tenant, key)`. Two principal classes: agents
  (Pramana-issued credential presentation, bearer) and operators/admins
  (Kavach-issued token, tenant-scoped). Payloads echo the event schemas so HTTP
  and substrate shapes can't drift.
- **ADR-0004 — Self-hosted Postgres 16 on Yotta Yntraa.** Production store is
  self-hosted (not managed) PostgreSQL 16 on a sovereign Indian cloud, for RBI
  data-residency + DPDP + operational control (backups, PITR, archival). Avoid
  Yotta-specific extensions to prevent lock-in.
- **ADR-0017 — On-prem deployment posture.** Single-host Docker Compose
  (db / api / worker / console); explicit Alembic migration step; secrets via env
  at deploy time; TLS/mTLS/WAF are reverse-proxy edge concerns, not app code;
  Helm deferred.
- **ADR-0005 — Accountability positioning** (see §1). **ADR-0006 — TDD as the
  engineering default:** test-first for every capability/schema/rule/audit
  primitive; coverage floors in CI; **`main` is protected, every commit is
  GPG-signed, no `Co-authored-by:` trailers** — discipline sustained by external
  enforcement (CI + hooks), not willpower.
- **ADR-0015 — Pramana SDK packaging and AGPL posture** (see §2).

---

## 5. The complete ADR index

All ADRs are **Accepted**. 0001–0014 dated 2026-05-24; 0016 dated 2026-06-12;
0018/0019 dated 2026-10-27. The ADR process (per `docs/adr/README.md`) is:
immutable once accepted (supersede, don't rewrite), sequential numbering, a fixed
section format, landed via GPG-signed commits.

| ADR | Title | Theme |
|---|---|---|
| 0001 | Three-layer architecture | system shape |
| 0002 | Substrate-first build order | build order |
| 0003 | Pramana–Kavach IP separation | IP boundary |
| 0004 | Self-hosted Postgres 16 on Yotta Yntraa | data residency |
| 0005 | Accountability-for-BFSI positioning | positioning |
| 0006 | TDD discipline | engineering discipline |
| 0007 | Modular capability architecture | extensibility |
| 0008 | Events as the substrate's primary output | information flow |
| 0009 | Read-side projections | read model |
| 0010 | Event schema versioning | contract stability |
| 0011 | Sub-product extraction posture | optionality |
| 0012 | Decision events with evidence + reasoning | defensibility |
| 0013 | Multimodal data sufficiency | honesty about data |
| 0014 | Multidimensional trust substrate | trust model |
| 0015 | Pramana SDK packaging + AGPL posture | IP/distribution |
| 0016 | External API surface + versioning | boundary |
| 0017 | On-prem deployment posture | deployment |
| 0018 | Signed mandates + policy integration | NIST tenet 06 |
| 0019 | Monitor capability + anomaly feedback loop | NIST tenet 09 |

---

## 6. What has been built

### 6.1 Git-history narrative (22 commits, `e5e1cf6` → `d34e774`)

The build is traceable commit-by-commit, grouped into milestones:

1. **Legal & identity foundation** (`e5e1cf6`) — LICENSE, NOTICE, README,
   CONTRIBUTING, SECURITY, CODE_OF_CONDUCT: the proprietary-but-source-available
   posture and the Pramana AGPL attribution, up front.
2. **Skeleton & engineering harness** (`3b02642` → `5d9bf6f`) — the three-layer
   tree mirrored by `tests/`; `pyproject.toml` + Python 3.12 pin; CI (`ci.yml`),
   CodeQL, pre-commit hooks, `dev-setup.sh`, the GPG-signature check; the
   `aurvia-pramana 0.3.0` dependency + Pramana resolution smoke test.
3. **Foundational ADRs** (`1c9c0e7`) — ADRs 0001–0006.
4. **Advanced architectural ADRs** (`fd007dd` → `0963481`) — ADRs 0007–0014, a
   pure design phase (docs only, no source yet).
5. **W01-S03 contracts & public README** (`9c0f813`) — ADRs 0015–0017, the frozen
   `openapi.yaml` (/v1), the roadmap, EU + India compliance mappings, the on-prem
   runbook, security whitepaper/threat-model/DPA, and the public README.
6. **W01-S03 implementation** (`8c4f5b2`, the big one — 89 files) — the full
   substrate and app: `kavach/api/`, `capabilities/{audit,storage,policy,
   sdk_bridge}`, `composition`, `query/projections`, Alembic initial migration,
   the Customer Service use case, the operator console, and a large test suite.
7. **On-prem packaging** (`c251f74`) — Dockerfile, docker-compose, `.env.example`,
   `smoke-onprem.sh`, vendor bridge.
8. **Strategy + NIST crosswalk** (`a00241c`) — the positioning brief + the NIST
   agentic-IAM tenets mapping.
9. **Signed mandates, AP2, monitoring** (`727c3d3`, `195e528`, `665b564`) — ADRs
   0018/0019 + the `mandate`, `monitor`, `egress`, `notify` capabilities, the MCP
   server scaffold, the console anomalies view, migration 0002, FIDO + NIST
   mapping updates.
10. **Phase 1 gate + hardening** (`906f9a7`, `29360f0`) — real AP2 SD-JWT, the
    byte-oriented `Signer`, MCP stdio + streamable-http transports; then the
    hardening pass (the 409 fix + the coverage work, §9).
11. **Phase-gate guides + installable SDKs** (`338ed28`, `d34e774`) — the two
    living user guides, then the Python + TypeScript SDKs and the Node reference
    agent (Phase 1.5).

### 6.2 Capability stack (shipped)

`events` · `storage` · `audit` (hash chain + exporter + byte `Signer`) · `policy`
(default-deny engine) · `mandate` (ADR-0018) · `sdk_bridge` (Pramana boundary) ·
`monitor` (ADR-0019) · `egress` · `notify` · plus `composition` (wiring) and
`query` (projections). Protocols in place: `CredentialVerifier` /
`DelegationVerifier`, `MandateVerifier`, `Signer`, `AnomalyDetector`,
`PolicyRuleProvider`. `enrichment` and `dpi` are Planned.

### 6.3 Frozen v1 event vocabulary (ADR-0010)

Core: `ActionExecuted`, `PolicyEvaluated`, `DecisionEmitted` (evidence +
reasoning + confidence + decided_by), `EvidenceRecorded`,
`TrustAssessmentEmitted` (multidimensional tensor), `DecisionFeedbackRecorded`,
`StepUpRequested`, `StepUpResolved`. Mandate lifecycle: `MandateIssued`,
`MandatePresented`, `MandateRevoked`. Monitor: `AgentMetricSnapshot`,
`AnomalyDetected`, `AnomalyAcknowledged`.

### 6.4 The frozen `/v1` REST surface (ADR-0016 + ADR-0018/0019)

Contract in `docs/api/openapi.yaml`. Core: `POST /v1/agents/{id}/actions`,
`POST /v1/agents/{id}/decisions`, `POST /v1/decisions/{id}/step-up/resolve`,
`GET /v1/step-ups`, `GET /v1/agents/{id}/trust`, `GET /v1/agents/{id}/timeline`,
`POST /v1/audit/exports` + `GET /v1/audit/exports/{id}`,
`POST /v1/webhooks/subscriptions`, `POST /v1/admin/agents`,
`POST /v1/admin/policies`, `GET /v1/health`. Mandates:
`POST /v1/mandates`, `GET /v1/mandates/{id}`, `POST /v1/mandates/{id}/revoke`.
Monitor: `GET /v1/agents/{id}/anomalies`, `POST /v1/anomalies/{id}/acknowledge`,
`GET /v1/agents/{id}/metrics`. (The monitor endpoints exist in `app.py` but are
not yet reflected in the committed `openapi.yaml` — see §12.)

### 6.5 Three access surfaces (same operations, three doors)

1. **REST** — the frozen `/v1` contract above.
2. **MCP** — `kavach.experiences.mcp_server` on the official MCP SDK, speaking
   both `stdio` and `streamable-http`, conformance-tested with the official MCP
   client over in-memory and HTTP transports.
3. **SDKs** — Python (`aurvia-kavach`, import `kavach`) + TypeScript
   (`@aurvia/kavach`), kept 1:1 by a cross-SDK contract test.

### 6.6 Runtime topology

```
agent ──▶ FastAPI (/v1) ──▶ policy ──▶ decision (allow / deny / step_up)
                       └──▶ audit  ──▶ HMAC-chained evidence
                                  ──▶ event bus + outbox ──▶ projections ──▶ console
                                                          └─▶ signed webhooks ──▶ partner
```

### 6.7 On-prem deployment (runbook)

Single Linux host, Docker Engine 24+, 2 vCPU / 4 GB. Four Compose services:
`db` (postgres:16), `api` (FastAPI), `worker` (outbox → webhook dispatcher),
`console` (nginx SPA). Bring-up: set secrets in `.env`
(`openssl rand -hex 32`), `docker compose up -d --build`,
`alembic upgrade head`, `curl /v1/health`, then `./scripts/smoke-onprem.sh`
(drives the Customer Service flow and asserts a signed evidence pack verifies —
ends with `SMOKE TEST PASSED`). Backups: the event log is the source of truth;
back up the `kavach_pgdata` volume — restore + projection `rebuild()` fully
reconstitutes the read side.

---

## 7. Compliance and regulatory posture

Covered in depth in §3. In short, the compliance pack is a genuine artifact set,
not a claim: `docs/compliance/` holds the **EU AI Act + eIDAS**, **India
RBI/SEBI/IRDAI/DPDP**, **FIDO agentic (AP2 / Verifiable Intent / AATWG)**, and
**NIST agentic-IAM** mappings, each crosswalking obligations to concrete
mechanisms with Implemented / Partial / Planned status. The honest gaps are
stated in each file (e.g. HSM/KMS-backed signing, operator IdP + RBAC, the
Trading/Credit/Insurance use-case rule sets, DPDP data-principal-rights
workflows, and a formal DPA per partner).

---

## 8. Security posture

Sources: `docs/security/security-whitepaper.md`, `docs/security/threat-model.md`,
`docs/security/data-processing-agreement-template.md`.

**Security model (whitepaper).** Everything runs in the partner's perimeter.
Events are the source of truth; read models are derived. **Auth:** agents present
a bearer credential verified via `CredentialVerifier` (fake offline verifier by
default, Pramana adapter for real), and may act only as their own `agent_id`;
operators present a Kavach-issued, tenant-scoped token. **Signed mandates** are
verified outside the agent's reasoning path; evidence stores the *mandate digest*
+ originator, not the raw token; revocation is checked before the policy effect.
**Tamper-evident audit:** every event is appended and, *in the same transaction*,
chained into an HMAC-SHA256 record linking to its predecessor; exports carry a
detached signature manifest over the chain head, so any change/reorder/insert/
delete breaks the chain and is detectable by recomputation. **Data minimisation:**
PII/credit data referenced by id, not inlined. **Idempotency + transactional
webhook outbox** with HMAC-signed payloads. **Secrets** via env at deploy time,
never baked into the image. **Supply chain:** pinned deps, `pip-audit` + CodeQL
in CI, no Pramana source in-tree.

**Stated prototype limitations / hardening backlog:** software-held HMAC signing
key → HSM/KMS with rotation; shared operator token → operator IdP + RBAC;
per-tenant audit chain advances without an explicit row lock → chain-head lock for
concurrent writers; TLS/mTLS + edge rate-limiting + WAF are deployment-edge
concerns; multi-tenant isolation review; reference-store access controls; a DPIA
with the partner DPO.

**Threat model (STRIDE).** Scope: the on-prem stack (API, worker, Postgres,
console). Assets: the event log + HMAC chain, the signing key + operator/JWT
secrets, agent credentials, referenced personal/financial data. The STRIDE table
enumerates Spoofing (forged agent / forged operator), Tampering (alter events /
replay), Repudiation, Information disclosure (PII in events / secrets in image),
DoS (API flood), and Elevation (scope escape / cross-tenant), each with a
mitigation and the residual prototype risk. Agentic-specific abuse cases —
**tool/scope escalation at runtime** (mitigated by provisioned action schema +
default-deny + `effective_scope`), **silent high-impact action** (mitigated by
step-up, EU Art. 14), and **audit gap during an incident** (mitigated by
transactional chaining) — are called out explicitly.

**DPA template.** Controller = the partner BFSI entity; Processor = Aurvia
Global, processing only on documented instructions. All processing within
India / the partner perimeter; **self-hosted, no Processor SaaS**; sensitive
records referenced by id, not inlined. Breach notice without undue delay (within
[N] hours); DPDP data-subject-rights assistance; audit rights over the evidence
chain and ADR-documented controls.

---

## 9. Testing and engineering discipline (the coverage work)

**Current measured state:** `163 tests collected; 161 pass locally + 2 real-Postgres
integration tests skip without a live DB; 85.44% total coverage` (CI gate 80%),
mypy strict + ruff clean. Tests are auto-marked by directory
(`tests/integration/` → `integration`, `tests/e2e/` → `e2e`, else `unit`).

**The Phase 1 hardening pass** (commit `29360f0`) deliberately treated "done" as
*happy + unhappy + edge + regression*, not the narrow smoke path:
- **Fixed a real defect:** duplicate mandate issuance returned a raw DB
  `IntegrityError` as **500**; a pre-check now returns **409
  `mandate_already_exists`** (RFC 7807). TDD: red test first.
- **AP2 SD-JWT unhappy/edge matrix** to parity with the fake verifier — expired,
  wrong agent, scope mismatch, revoked, wrong nonce, amount-over-range,
  disallowed payee, malformed chain — **all fail closed**.
- **Real Postgres integration tests** (`tests/integration/`): full issue →
  duplicate-409 → decide and revoke → deny flows against the production DB target,
  with the 409 verified against the *real* unique constraint (the path that used
  to 500). These skip locally unless `KAVACH_DATABASE_URL` is set, and run in CI
  against `postgres:16`.
- **API edge cases:** malformed `X-Kavach-Mandate` never trusted and never 500s;
  tenant-isolated timelines; 404s for unknown mandate/step-up; step-up queue;
  trust 404; agent self-scoped metrics.
- **Authorization-core coverage:** policy-engine mandate paths (originator-kind
  gating, constraint satisfy/violate, payee fallback, unsupported/typed
  operators) + direct attenuation tests.

Coverage deltas from the pass: `attenuation.py` 62% → **100%**;
policy `engine.py` 74% → **90%**; suite total 83% → **85.44%**.

**Testing strategy across phases:** (1) schema round-trip, (2) capability unit,
(3) policy integration, (4) audit chain incl. Signer-swap zero-regression,
(5) API, (6) end-to-end, (7) property-based (Hypothesis), (8) replay/audit
integrity, (9) reference-vector conformance (AP2 example credentials), (10) SDK
contract tests, (11) MCP conformance (official client), (12) framework-integration
e2e (Phase 2). **Gates:** CI coverage fail-under 80; pre-push 70 + GPG-signature
check on `main`; mypy strict; ruff lint + format; pre-commit hooks;
`filterwarnings = error`.

---

## 10. Current gate status

**Phase 1 — CLOSED.** The gate (synthetic agent runs Customer Service end-to-end:
KYC → high-value transfer step-up → operator resolve → signed evidence export
that verifies) is met and verified via `docker compose up`, plus AP2-mode chain
and the networked MCP container answering the official client.

**Phase 1.5 — OPEN.** Gate (from the plan): *`pip install aurvia-kavach` and
`npm install @aurvia/kavach` both work end-to-end against the Phase 1 demo API;
the Node reference app runs the same flow as the Python harness.*
- ✅ Everything technically closable is verified **from the built, distributable
  artifacts** — the real wheel installs into a clean venv and drives the demo
  (`step_up → allow → 7 signed records`); the real `npm pack` tarball installs
  via `npm install` and the Node agent passes end-to-end.
- ⏳ **The single remaining action** is the first publish to the public
  registries, which needs registry identity the agent cannot assume:
  - **npm:** claim the `@aurvia` scope (org) + add an `NPM_TOKEN` GitHub secret.
  - **PyPI:** configure Trusted Publishing for the repo (+ TestPyPI for the
    dry-run), using environments `pypi` / `testpypi`.
- **Standing policy (project rule):** the next phase will **not** be started or
  recommended until this gate is verifiably CLOSED (install from the live
  registries + demo passes).

---

## 11. The phase plan ahead

```
Phase 0   Standards alignment + docs + ADRs                        ✅
Phase 1   Mandate + AP2 + MCP + Signer + Monitor → running demo    ✅  [GATE CLOSED]
Phase 1.5 Installable Python + TS SDKs + Node reference agent      ⏳  [GATE OPEN — publish pending]
Phase 2   Monitor hardening + Egress/Notify + framework middleware + swarm scorecard
Phase 3   CLI + docs site + sandbox tenant + reference apps + API ergonomics
```

**Phase 2 (sketch):** `EgressChannel` + `NotificationChannel` Protocols
(webhook / Kafka / SNS egress; Slack / PagerDuty / email / Teams notifiers off
`StepUpRequested`, opt-in); OpenAI + Anthropic middleware (`wrap_tools(…)` routes
every tool call through Kavach decide); LangChain callback handler + LangGraph.js
adapter; a multi-agent adversarial **swarm scorecard** (scope expansion, mandate
forgery, replay, rate flood → JSON + one-page scorecard).

**Phase 3 (sketch):** a `kavach` CLI; a docs site; a sandbox tenant
(`KAVACH_MODE=sandbox`, test-vs-live keys); ~100-line reference apps per
framework; API ergonomics (cursor pagination, `RateLimit-*`/`Request-Id`
headers, Postman collection, API changelog).

---

## 12. Open questions worth discussing

1. **Two phase-numbering schemes.** `docs/roadmap.md` numbers the substrate build
   as Phases 1–6; the working build plan uses "Phase 1 = substrate / 1.5 = SDKs /
   2 = adapters…". Pick one canonical scheme to avoid confusing readers.
2. **Contract ↔ implementation drift.** The monitor endpoints
   (`…/anomalies`, `/v1/anomalies/{id}/acknowledge`, `…/metrics`) exist in
   `app.py` (ADR-0019) but are **not yet in the committed `openapi.yaml`**.
   Reconcile the frozen contract.
3. **`requires-python` widened to 3.11–3.13** for the SDK matrix, but 3.11/3.13
   are only exercised in CI (dev is 3.12). Confirm that's the real support
   commitment.
4. **npm scope.** `@aurvia` is unclaimed; fallback is an unscoped `aurvia-kavach`
   npm package to mirror PyPI if the org step is friction.
5. **Idempotency scope.** OpenAPI advertises `Idempotency-Key` broadly, but only
   `…/actions` and `…/decisions` actually dedupe. Tighten contract or impl.
6. **Publishing a "proprietary, source-available" package** to PyPI/npm — confirm
   the intended distribution model and whether the license needs a dedicated
   `LicenseRef`.
7. **Roadmap status lag.** `docs/roadmap.md` still says "Phase 1 in progress /
   Phases 2–6 pending" though the substrate/API/use-case/console/on-prem all
   shipped in `8c4f5b2`/`c251f74` — the file was intentionally not edited (plan
   is immutable). The README's "17 ADRs" likewise predates 0018/0019 (now 19).

---

## 13. Reference facts and repo map

- **Stack:** Python 3.12 (dev); FastAPI + Starlette (pinned `<0.49`); SQLAlchemy
  async + asyncpg/psycopg; Pydantic 2; httpx; Node ≥18 / TypeScript for the TS
  SDK; Postgres 16 target with SQLite for fast tests.
- **Optional extras:** `ap2` (Google AP2 SDK, git-pinned — not on PyPI),
  `mcp` (official MCP SDK `>=2.3.0`), `pramana` (`aurvia-pramana>=0.3.0,<1.0.0`),
  `dev`.
- **Key config (`KAVACH_*`):** `database_url`, `operator_token`,
  `mandate_verifier_mode` (fake|ap2), `audit_signer_mode` (hmac|kms_stub),
  `audit_hmac_key`, `jwt_secret`.
- **Governance:** LICENSE proprietary (All Rights Reserved); NOTICE records the
  Pramana AGPL-3.0 boundary; SECURITY.md = email-first disclosure (PGP
  `6CCE4C0CF8685C7F54F16ACFA436F76F7A323EE4`, ack within 72h); CONTRIBUTING =
  no external contributions, GPG-signed sole-authored commits on protected
  `main`; CODE_OF_CONDUCT = Contributor Covenant v2.1.
- **Repo map (selected):**
  - `kavach/` — the substrate (events, capabilities, composition, query,
    usecases, experiences, api, client.py, server.py, worker.py)
  - `sdks/typescript/` — the `@aurvia/kavach` SDK
  - `examples/node/minimal-agent/` — the runnable Node reference agent
  - `tests/` — layered suite (unit, integration, e2e, sdk)
  - `docs/adr/` — the 19 ADRs · `docs/api/openapi.yaml` — the frozen contract ·
    `docs/compliance/` — EU/India/FIDO/NIST mappings ·
    `docs/security/` — whitepaper, threat model, DPA template ·
    `docs/strategy/` — the positioning brief · `docs/deployment/` — the runbook ·
    `docs/guides/` — the business + technical user guides · `docs/roadmap.md`
  - `.github/workflows/` — CI, CodeQL, and the three publish workflows

---

*Document scope: public technical posture only. No employer-specific or
confidential content is included. Grounded in the repository as of commit
`d34e774`.*
