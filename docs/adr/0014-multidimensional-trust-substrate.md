# ADR-0014 — Multidimensional trust substrate

**Status:** Accepted
**Date:** 2026-05-24

## Context

The substrate's deepest commitment, encoded in the company name and
in ADR-0005's "Accountability for Indian BFSI" positioning, is that
Kavach reasons about *trust* in agents. Every other architectural
decision in this set of ADRs serves that commitment in some way:
events as primary output makes trust observable, decision evidence
makes trust defensible, projections make trust queryable, sufficiency
bands make trust honest about its own data.

But what *is* trust, in this substrate?

The naive answer is: a number per agent. "Agent-X has trust score
0.73." This is wrong in several ways that matter:

1. **Trust is not one thing.** A retail credit underwriting agent
   that's excellent at retail decisions but has never handled
   small-business decisions is not "0.73 trustworthy" — it's
   "high-trust for retail, cold-start for SMB." Different
   workflows demand different trust facets.

2. **Trust composition is context-dependent.** A different BFSI
   use case will weight the same trust facets differently. A
   customer-service agent may weight conversational-quality and
   adherence-to-script highly; a trading agent may weight
   risk-discipline and adherence-to-mandate highly. A single
   composition rule would force false uniformity.

3. **Trust evolves across modalities.** An agent earns trust in
   credential-chain-quality faster than it earns trust in
   behavioral-baseline-stability. A scalar trust score collapses
   these distinct trajectories into one number.

4. **Trust generalizes beyond BFSI.** The substrate's long-arc
   positioning is "trust infrastructure for the agent economy"
   across regulated verticals. Healthcare agents, government
   agents, enterprise-SaaS supervisor agents — each vertical has
   trust facets specific to it (clinical-judgment-quality,
   citizen-due-process, data-access-discipline). A scalar trust
   score forces vertical-specific assumptions into the substrate.

The right answer: trust is a tensor — a structured set of
dimensions, each with its own value, sufficiency, and composition
rules. The substrate emits the full tensor; consumers project it
into whatever scalar they need for their UI or decision.

This ADR is the foundational commitment for everything that grows
from Kavach beyond its initial three BFSI use cases.

## Decision

**Trust in the Kavach substrate is multidimensional, not scalar.**

Each agent, in each use case context, has a `TrustAssessment` that
includes:

- **A set of trust dimensions**, each with its own value
- **Per-dimension data sufficiency** (per ADR-0013)
- **A composition specification** indicating how to roll up the
  dimensions for a given consumer's purpose

A sketched shape:

```python
# kavach/events/schemas/trust.py — sketch
class TrustAssessment(BaseModel):
    """Multidimensional trust assessment for an agent in a context."""
    schema_version: ClassVar[int] = 1
    agent_id: AgentID
    context: TrustContext  # use case, workflow, customer cohort, etc.
    dimensions: dict[str, TrustDimension]
    composition: CompositionSpec | None
    assessed_at: datetime

class TrustDimension(BaseModel):
    """One facet of trust."""
    schema_version: ClassVar[int] = 1
    name: str
    value: float  # 0.0 to 1.0, calibration documented per dimension
    sufficiency: DataSufficiency  # per ADR-0013
    contributors: list[str]  # references to the input modalities
    reason: str  # human-readable

class CompositionSpec(BaseModel):
    """How to compose dimensions into a scalar for a given consumer."""
    schema_version: ClassVar[int] = 1
    method: Literal["weighted_average", "min", "max", "custom"]
    weights: dict[str, float] | None
    custom_function_id: str | None  # for "custom" method
    notes: str
```

**The substrate defines core trust dimensions, use cases extend
them.** The substrate ships with a base set of dimensions that
apply across all BFSI use cases. Examples:

- `credential_integrity` — quality and unbroken-ness of the
  delegation chain (Pramana-grounded)
- `behavioral_consistency` — alignment with the agent's established
  baseline
- `policy_compliance` — track record against policy rules
- `outcome_quality` — feedback labels on prior decisions
- `peer_alignment` — how this agent compares to similar agents
  in similar contexts

Use cases extend the base set with use-case-specific dimensions.
Example: a credit underwriting use case adds:

- `risk_calibration` — does this agent's risk-acceptance match
  the desired risk profile of the credit book
- `decision_speed_appropriateness` — does this agent take
  appropriate time on appropriately-complex decisions

Use case dimensions live in the use case config (per ADR-0001),
not in the substrate. The substrate provides the type system and
composition machinery; the use case provides the dimension catalog.

**Composition is context-dependent.** When a consumer needs a
single trust scalar (e.g., the operator console wants to sort
agents by trust), the consumer supplies a `CompositionSpec`. The
substrate provides default composition specs per use case context;
consumers may override.

Different policies in the same use case may use different
compositions. The compositions themselves are decision-event-grade:
the choice of composition is part of the decision's reasoning trace
(per ADR-0012).

**The first trust assessment uses the multidimensional schema.**
We do not start with a scalar trust score and migrate later. From
the first `TrustAssessmentEmitted` event onward, the schema is the
multidimensional one. Trust dimensions may start with a single
dimension (e.g., just `credential_integrity` in W01-S03 before
other dimensions exist), but the tensor structure is in place.

This avoids a wholesale schema migration when additional dimensions
are added, and it avoids the trap of "we'll generalize later" that
typically results in never-generalizing.

**The neural-engine framing is a projection, not an architecture.**
A "neural engine that produces a trust score" is one specific
composition: a learned function (model) over the substrate's
dimensions producing a context-specific scalar. The dimensions are
the substrate; the neural engine consumes the substrate. This is
the inversion that makes the substrate generalizable: the substrate
doesn't compute trust scores — it produces the multidimensional
evidence from which trust scores can be computed.

This positioning also informs the W01-S03+ build order: the
substrate's first trust capability emits the multidimensional
assessment with rule-based dimension values. A learned composition
(neural or otherwise) is added later when sufficient labeled data
exists per ADR-0012's feedback loop.

## Consequences

**Positive:**

- **Trust is context-honest.** "Agent-X has high credential
  integrity but cold-start behavioral consistency" is sayable. The
  operator console can show this directly. The substrate doesn't
  collapse meaningful distinctions into a misleading scalar.

- **Use cases own their composition.** A customer-service use case
  weights conversational dimensions; a trading use case weights
  risk dimensions. Same substrate, different compositions. No
  substrate code change required to support a new use case's
  composition needs.

- **The substrate generalizes beyond BFSI.** Healthcare,
  government, enterprise SaaS — each vertical brings its own
  dimensions, composes them according to its own logic. The
  substrate provides the type system, the storage, the projection
  patterns, the audit-grade decision discipline. Verticals plug
  into it.

- **The accumulating labeled data (per ADR-0012) trains
  dimension-specific models.** Eventually some dimensions move
  from rule-based to model-based; the substrate's tensor shape
  is unchanged. Models replace specific dimension producers
  without disrupting consumers.

- **The investor and partner narrative gets a concrete substantive
  spine.** "Multidimensional trust substrate for the agent economy"
  is what Aurvia is, not what Aurvia hopes to become. The first
  customers exercise it; subsequent verticals extend it.

- **The "Aurvia" naming makes sense.** Aurvia is the trust
  infrastructure; Pramana is the identity substrate beneath it;
  Kavach is the BFSI commercial layer above it. The three names
  occupy distinct strata in a coherent architecture.

**Negative:**

- **The schema is more complex than a scalar.** Producers must
  construct multidimensional assessments; consumers must
  understand composition. Mitigation: helper builders for common
  cases (single-dimension assessment, default-weighted composition);
  examples in `docs/capabilities/trust/` (longer arc).

- **Composition mistakes are a real bug class.** Picking the wrong
  composition spec produces misleading trust scores. Mitigation:
  composition specs are decision-grade (per ADR-0012); the choice
  is auditable and reviewable.

- **Some BFSI partners will initially want a single trust score.**
  We provide one (the default composition produces a scalar) but
  insist on the substrate retaining the multidimensional underlying
  representation. Partners can use the scalar; the underlying
  dimensions remain available for drill-down.

- **Dimension proliferation risk.** Each use case adds dimensions;
  without discipline, the dimension catalog could become unwieldy.
  Mitigation: the substrate's core dimension set is small and
  stable; use case dimensions live in use case configs and are
  reviewed at the use case design phase.

- **Models that consume dimensions need to handle missing
  dimensions gracefully.** A use case that doesn't define
  `behavioral_consistency` produces assessments without that
  dimension; consumers must handle the absence. The Pydantic
  schema makes this explicit; the discipline is "no consumer
  assumes a dimension is present unless it's required by that
  consumer's use case."

## Alternatives Considered

- **Scalar trust score, multidimensional metadata.** A single
  scalar trust score with optional per-dimension breakdowns.
  Considered seriously. Rejected because it embeds a default
  composition in the substrate, which forces uniform composition
  across use cases — exactly what this ADR is designed to avoid.

- **Trust as a confidence-rated category.** "Trusted / suspect /
  cold." Considered for simplicity. Rejected because BFSI use
  cases need finer granularity, and reducing to categories loses
  the composition flexibility multidimensional trust provides.

- **Per-use-case trust types (no shared substrate type).** Each
  use case defines its own trust schema. Considered. Rejected
  because cross-use-case operations (a single dashboard showing
  trust across all agents in the customer's deployment) become
  impossible without a shared substrate type.

- **Defer multidimensional trust to V2.** Start with scalar trust;
  refactor to multidimensional later when use cases demand it.
  Considered. Rejected for the standard reason: schema migration
  later is expensive, schema discipline now is cheap. The
  multidimensional schema accommodates a one-dimension starting
  point (single dimension `credential_integrity` for the first
  capability) without architectural change.

- **Use a standardized trust ontology (e.g., from academic trust
  literature or NIST AI RMF).** Considered. Rejected as a
  prescriptive default because BFSI-specific dimensions don't map
  cleanly to general-purpose trust ontologies, and forcing the
  mapping would make our trust dimensions less useful to BFSI
  partners. Substrate dimensions are pragmatic, not normative.
  Mapping to external ontologies is a per-use-case concern.

## References

- ADR-0001 — Three-layer architecture (use cases define their
  dimensions; the substrate provides the type system)
- ADR-0005 — Accountability positioning (the multidimensional
  substrate is what makes "trust infrastructure for the agent
  economy" technically substantive)
- ADR-0008 — Events as primary output (`TrustAssessmentEmitted`
  is the event)
- ADR-0010 — Event schema versioning (TrustAssessment, TrustDimension,
  CompositionSpec are all versioned)
- ADR-0011 — Sub-product extraction (the trust capability is a
  candidate for high-extractability classification in the longer
  arc; revisit when the trust capability's standalone value
  becomes concrete)
- ADR-0012 — Decision events with evidence and reasoning (trust
  assessments are decision events; composition choices are part of
  reasoning traces)
- ADR-0013 — Multimodal data sufficiency (each trust dimension
  carries its own DataSufficiency)
- `kavach/events/schemas/trust.py` — established in W01-S02 Block E
- `kavach/capabilities/trust/` — first trust capability lands in
  W01-S03+ with a single-dimension implementation (`credential_integrity`)
- `docs/capabilities/trust/` — full capability documentation
  including dimension catalog and composition cookbook (longer arc)
