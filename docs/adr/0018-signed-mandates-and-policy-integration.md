# ADR-0018 — Signed mandates and policy integration

**Status:** Proposed
**Date:** 2026-10-27

## Context

ADR-0012 established that every decision event carries evidence,
reasoning, confidence, and `decided_by`. That answers *who decided*
    10|and *on what basis*. It does not answer the question that NIST's
tenet 06 (*Mandates and Constraints*) foregrounds and that regulated
BFSI auditors are increasingly asking:

> Who *authorized the task* in the first place, and did they
> authorize it for *this specific scope*?

In the current substrate, an agent presents a credential whose scope
authorizes a class of actions (e.g. `account.funds.*`). Nothing
cryptographically binds a specific execution to the originator's
    20|intent for that execution. If a prompt injection convinces an agent
with broad `account.funds.*` scope to initiate a transfer the
originator never asked for, the audit chain truthfully records that
the agent did it, under its (valid) credential, through the (correct)
rule. The chain does not record that the originator never mandated
this particular action. The accountability trail is intact but the
causal chain is incomplete.

NIST's tenet 06 — and the "confused deputy" discussion in the
accompanying blog — makes the fix explicit: the task originator
    30|produces a cryptographically signed mandate statement that defines
intended outcomes and constraints; downstream services verify the
signature and use the mandate in authorization decisions.

This ADR adds that layer. It does so without disturbing the existing
decision event schema (ADR-0012), the credential verifier Protocol
(ADR-0015), the policy engine (`PolicyEngine.evaluate`), or the audit
chain (ADR-0012). Mandates are a new, orthogonal primitive that the
substrate consumes, verifies, references in evidence, and signs into
the audit chain like any other event.

    40|## Decision

**1. A mandate is a signed, bounded authorization from a task
originator to an agent.** Shape (sketched; final types land in
`kavach/events/schemas/mandate.py`):

```python
class MandateConstraint(BaseModel):
    """A single constraint on action parameters (e.g. amount <= 50000)."""
    path: str                        # dotted path into parameters
    operator: Literal["eq", "ne", "lte", "gte", "lt", "gt", "in", "matches"]
    50|    value: Any

class Mandate(BaseModel):
    schema_version: ClassVar[int] = 1
    mandate_id: str
    originator_id: str               # the principal issuing the mandate
    originator_kind: Literal["human", "service", "agent", "wallet"]
    agent_id: str                    # the agent authorized
    action_scope: list[str]          # action-type glob patterns
    constraints: list[MandateConstraint]
    issued_at: datetime
    60|    expires_at: datetime
    parent_mandate_id: str | None    # for attenuated sub-mandates
    nonce: str
```

A `Mandate` is serialized to a compact token (JWS-shaped for the
Pramana adapter; HMAC-signed opaque token for the fake verifier) and
presented alongside the agent credential at decision time.

**2. Verification lives behind a new sdk_bridge Protocol**,
mirroring ADR-0015's `CredentialVerifier`:
    70|
```python
class VerifiedMandate(BaseModel):
    mandate: Mandate
    verified: bool
    reason: str
    chain_ok: bool                   # parent-attenuation verified
    not_revoked: bool

class MandateVerifier(Protocol):
    def verify(
        self,
    80|        token: str,
        *,
        expected_agent_id: str,
        expected_action: str,
        now: datetime,
    ) -> VerifiedMandate: ...
```

Two implementations ship: a `FakeMandateVerifier` for offline / test
use (HMAC over the canonical JSON of the mandate; same key management
as the audit chain in the prototype, separate in production) and a
    90|`PramanaMandateVerifier` that wraps a Pramana verifiable-credential
presentation (originator holds a signing key; mandate is a VC with
`type: "AgentMandate"`). The substrate depends only on the Protocol.

**3. Attenuation is enforced at verification time.** A derived
sub-mandate (where `parent_mandate_id` is set) is accepted only when
its `action_scope` is a strict subset of the parent's effective scope
and every one of its `constraints` is at least as restrictive as the
parent's. This prevents sub-agents or downstream services from
claiming more authority than the originator granted, which is the
   100|exact property tenet 02 attenuation requires.

Scope-subset is defined on action-type globs: `A` is a subset of `B`
iff every string matched by `A` is matched by `B`. In practice we
restrict `action_scope` grammar to the same `fnmatch` dialect the
policy engine already uses (`PolicyEngine._match`) and compute subset
by exhaustive matching for the leaf form `foo.bar.baz` and literal
prefix check for `foo.bar.*`. Non-trivial glob subset is deferred
behind a `strict_scope` flag; mandates that fail strict subset are
rejected at verification. The grammar is documented alongside the
   110|Protocol.

**4. The policy engine takes an optional `VerifiedMandate`** and
exposes two new rule-condition operators:

- `mandate_covers_action` — true iff the mandate's `action_scope`
  covers the proposed action type.
- `mandate_constraint_satisfied` — true iff every mandate constraint
  evaluates true against the current parameters.

Rule sets gain two fields on `PolicyRule`:

   120|- `mandate_required: bool = False` — if true, absence of a verified
  mandate denies the action regardless of other conditions.
- `mandate_originator_kinds: list[str] | None = None` — if set, the
  mandate's `originator_kind` must be in the list.

Default behaviour is unchanged for rules that do not opt in; existing
customer-service rules continue to evaluate exactly as before. This
preserves ADR-0010 backward compatibility.

**5. The mandate is embedded in decision evidence.** When a mandate
   130|is presented and verified, the decision event's `Evidence` carries
a reference to the mandate (`EvidenceReference(kind="mandate",
ref_id=mandate_id, digest=mandate_digest)`) and inline attributes
`mandate_originator_id` and `mandate_originator_kind`. The full
mandate token is not inlined (data minimisation per ADR-0012); it is
stored in a separate `mandates` table and retrievable by id for
export.

**6. Three new events enter the audit chain.** All inherit from
`DomainEvent` and are versioned per ADR-0010:
   140|
- `MandateIssued(mandate_id, originator_id, agent_id, scope, constraints, expires_at, mandate_digest)` — emitted when a mandate is created and stored.
- `MandatePresented(decision_id, mandate_id, verified, reason)` — emitted when a mandate is presented at a decision; verification outcome is captured even on failure.
- `MandateRevoked(mandate_id, revoked_by, reason)` — emitted when an originator or operator revokes a mandate before expiry.

These flow through the `AuditChainWriter` like every other event, so
tampering with mandate state breaks the chain and is detectable on
export.

**7. API surface.** `/v1` gains three endpoints (contract documented
   150|in `docs/api/openapi.yaml`):

- `POST /v1/mandates` — issue a mandate. Agent principals may issue
  only sub-mandates derived from a mandate they currently hold;
  operator principals may issue root mandates on behalf of configured
  originators.
- `GET /v1/mandates/{mandate_id}` — read a mandate (operator or the
  originator / agent party to it).
- `POST /v1/mandates/{mandate_id}/revoke` — revoke before expiry.

   160|`POST /v1/agents/{agent_id}/decisions` accepts a new optional
`X-Kavach-Mandate` header. When present, the mandate is verified
against the proposed action; the `VerifiedMandate` is passed into
`PolicyEngine.evaluate` and recorded in evidence either way.

**8. The customer_service use case adopts mandates for the
transfer path.** The `transfer.initiate` rule gains
`mandate_required: true` and a condition that the mandate's
`amount` constraint is satisfied. The synthetic harness is updated
to issue a mandate, present it, and resolve the step-up. This is
   170|the end-to-end demonstration the POC targets.

## Consequences

**Positive:**

- **Closes NIST tenet 06.** The crosswalk row flips from Planned to
  Implemented with concrete code pointers.
- **Mitigates confused-deputy attacks at the architectural layer.**
  An agent with a broad credential cannot execute a mandate-required
  action without a mandate specifically covering that action.
   180|  Combined with ADR-0007 (reasoning outside the engine) and the
  deterministic policy (tenet 08), this is the complete confused-
  deputy mitigation NIST describes.
- **Downstream verifiability without trusting Kavach.** A partner
  system receiving an event from the outbox can verify the mandate
  signature independently; Kavach does not need to be in the trust
  path for mandate authenticity.
- **Consumer-facing scenarios become natural.** A customer's wallet
  signs a mandate ("agent X may transfer up to ₹50,000 to IFSC Y
  before 15:00"); the agent presents it; the decision evidence
   190|  carries the customer's cryptographic consent. This is the shape
  NIST calls out for consumer agentic transactions.
- **Attenuation addresses tenet 02 at the same stroke.** Sub-agent
  delegation becomes a sub-mandate with a strict-subset scope; the
  chain is auditable.

**Negative:**

- **Originator burden.** Issuing a mandate is work the task
  originator (or the service orchestrating them) must do. Mitigation:
  SDK helpers; operator console wizards; mandate templates per use
   200|  case to reduce the per-task work to filling in parameters.
- **Mandate issuance UX work.** The operator console gains a
  mandate-issuance screen and a mandate-registry view. Non-trivial.
- **Scope-subset verification is subtle.** Full glob-subset is a
  known-hard problem; we restrict the grammar initially and document
  the restriction. A future ADR may lift this once the restriction
  bites real use cases.
- **Key management for mandate signing is new scope.** For the
  prototype we reuse the audit HMAC key with a domain separation
  tag; production will use a separate HSM-held key per originator
   210|  (or wallet-held keys for consumer scenarios). Documented in the
  security whitepaper's hardening backlog.
- **A new table and migration.** `mandates` + `mandate_revocations`
  land as an Alembic migration (ADR-0017 explicit-migration
  discipline).

## Alternatives Considered

- **Rely on `decided_by` and credential scope alone.** Rejected.
  `decided_by` identifies what made the decision; credential scope
   220|  bounds what the agent *may* do. Neither binds a specific
  execution to the originator's intent. The confused-deputy case
  demonstrates the gap.
- **Overload the credential to carry mandate scope.** Rejected.
  Credentials and mandates have different lifetimes (credential
  outlives any single task), different originators (identity issuer
  vs task originator), and different revocation semantics.
  Conflating them makes both weaker.
- **Store mandates server-side only, no cryptographic artifact.**
  Rejected. Downstream services would have to trust Kavach for
   230|  mandate authenticity. That is exactly the dependency NIST
  tenet 06 ("downstream applications can verify the signature")
  rules out.
- **Model mandates as a prompt / instruction captured in the agent
  context.** Rejected. The tenet explicitly separates mandate
  (verifiable, deterministic) from reasoning (prompt, probabilistic).
  Mandates in-prompt are vulnerable to prompt injection — the
  exact failure mode this ADR is here to prevent.
- **Delegate mandates entirely to Pramana (no substrate primitives).**
  Rejected. Mandates must be first-class in the policy engine, in
   240|  decision evidence, and in the audit chain. Pramana supplies the
  cryptographic verifier behind the Protocol; the substrate owns
  the semantic integration.
- **Make `mandate_required` global instead of per-rule.** Rejected.
  Blanket global enforcement breaks the existing low-impact
  decision paths (e.g. `account.read.balance`) and raises originator
  burden without proportional benefit. Per-rule opt-in matches the
  graduated-authority model that step-up (tenet 05) already uses.

## References
   250|
- NIST / NCCoE, *Design Tenets for Agent Identity Management
  Systems*, Cybersecurity Insights blog, 27 October 2026 — tenet 06
  (*Mandates and Constraints*) and the confused-deputy discussion.
- [docs/compliance/nist-agentic-iam-mapping.md](../compliance/nist-agentic-iam-mapping.md) —
  the crosswalk row this ADR targets.
- [ADR-0007](./0007-modular-capability-architecture.md) — the
  extension-point pattern used for the new `MandateVerifier`.
- [ADR-0010](./0010-event-schema-versioning.md) — the three new
  events are versioned under this discipline.
   260|- [ADR-0012](./0012-decision-events-with-evidence-and-reasoning.md) —
  the decision event into which mandate evidence is embedded.
- [ADR-0015](./0015-pramana-sdk-packaging-and-agpl-posture.md) — the
  Pramana adapter pattern that `PramanaMandateVerifier` follows.
- [ADR-0016](./0016-external-api-surface-and-versioning.md) — the
  `/v1` surface the three new endpoints extend.
- [ADR-0017](./0017-on-prem-deployment-posture.md) — the migration
  discipline the new tables follow.
