# ADR-0012 — Decision events carry evidence, reasoning, and confidence

**Status:** Accepted
**Date:** 2026-05-24

## Context

Kavach Platform's market positioning per ADR-0005 is "Agent
Accountability for Indian BFSI." The substantive claim is: when an
agent makes a decision, Kavach records enough information that the
decision is later defensible to a compliance officer, an internal
auditor, an external regulator, or a court.

"The agent denied the transaction" is not defensible. The auditor
will ask:

- On what basis?
- Which rule fired?
- What inputs were evaluated?
- What was the confidence?
- If a model was involved, which model and which version?
- Was there evidence the rule was met, or was it inferred?
- What reasoning trace led from inputs to output?
- Could a reasonable human reviewing this trace have reached the same
  decision?

If the substrate cannot answer these questions on demand, Kavach's
accountability claim is rhetorical, not operational. BFSI partners
will not deploy a system whose accountability claim is rhetorical.

This means: every decision event the substrate emits must carry
evidence, reasoning, and confidence as first-class fields, not as
optional debug metadata.

A second concern: human feedback on decisions (operator marks
something as a false positive, supervisor confirms a true positive)
must itself be captured as events. Without this, the substrate is
deaf to its own mistakes. With it, the substrate accumulates labeled
training data through normal operation — which becomes the foundation
for ML-improved capabilities later (per ADR-0014 in Block D.4).

## Decision

**Every decision event the substrate emits carries four mandatory
embedded fields:**

1. **Evidence.** The inputs the decision was based on, as a structured
   `Evidence` object. Includes the relevant agent identity, credential
   attributes, transaction attributes, contextual signals, and
   anything else materially relevant. Stored by reference where the
   underlying records are large (e.g., reference to the original
   transaction in the storage capability); stored inline where the
   evidence is compact (e.g., key-value attribute set).

2. **Reasoning.** A structured `ReasoningTrace` describing how the
   decision was derived from the evidence. For rule-based decisions:
   which rule fired, what its conditions were, why those conditions
   were met. For probabilistic decisions: which model produced the
   output, what version of the model, what features it used, what
   the output was, what threshold was applied. For decisions
   involving both: the composition of the two reasoning paths.

3. **Confidence.** A `Confidence` value indicating how certain the
   decision is. For rule-based decisions where the conditions are
   either met or not, confidence is a categorical "rule-deterministic"
   (effectively 1.0). For probabilistic decisions, confidence is a
   numeric score with the calibration method documented (e.g.,
   "isotonic-calibrated, validated against held-out test set").

4. **Decided-by.** Which decision-making entity produced this
   decision: a specific rule_id, a specific model+version, a human
   operator (with their identity captured), or a composition of
   these. This is distinct from the agent_id that the decision
   acted on; it identifies what made the decision.

Pydantic types for these embedded fields live in
`kavach/events/schemas/decision_primitives.py`. The types are
versioned per ADR-0010; changes follow the four-phase rollout.

A sketched shape:

```python
# kavach/events/schemas/decision_primitives.py — sketch
class Evidence(BaseModel):
    """Structured evidence basis for a decision."""
    schema_version: ClassVar[int] = 1
    references: list[EvidenceReference]  # by-reference to large records
    attributes: dict[str, Any]            # inline compact evidence
    captured_at: datetime

class ReasoningTrace(BaseModel):
    """Structured reasoning from evidence to decision."""
    schema_version: ClassVar[int] = 1
    kind: Literal["rule", "model", "composite", "human"]
    rule_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    features_evaluated: list[str] | None = None
    intermediate_steps: list[ReasoningStep] | None = None
    decision_path: str  # human-readable summary

class Confidence(BaseModel):
    """Confidence indicator for a decision."""
    schema_version: ClassVar[int] = 1
    kind: Literal["rule_deterministic", "probabilistic", "human_judged"]
    score: float | None = None  # 0.0 to 1.0 for probabilistic
    calibration: str | None = None  # description if probabilistic
```

**Decision events that carry these fields include (representative,
not exhaustive):**

- `PolicyDecisionEmitted` — from the policy capability
- `AnomalyDetected` — from anomaly detection (when established)
- `TrustAssessmentEmitted` — from the trust substrate (per ADR-0014)
- `StepUpAuthenticationRequired` — when policy escalates
- `EnrichmentApplied` — when the enrichment capability adds context

Non-decision events (e.g., `AgentSessionStarted`, `EventStreamPaused`)
do not carry decision primitives; they record state transitions
without decision-grade rigor.

**Feedback events close the FP/FN loop:**

When a human operator (in the operator console experience) or a
downstream system marks a prior decision as a false positive or
confirms it as a true positive, a feedback event is emitted:

- `DecisionFeedbackRecorded` — carries the decision event's ID, the
  feedback (false positive / true positive / partial / unknown), the
  human or system that provided the feedback, and any narrative.

Feedback events are themselves decision events: they have evidence
(why the operator believes the original decision was wrong/right),
reasoning (the operator's rationale), and confidence (how sure the
operator is). The decision-grade discipline applies recursively.

**The feedback loop becomes labeled training data:**

Once feedback events accumulate, the pair (original decision event +
feedback event) is a labeled example for any future ML model that
wants to improve the decision logic. The substrate's value is not
just supervising agents; it's accumulating the supervised data that
makes the supervision better over time. This is documented further
in ADR-0014 in Block D.4 (multidimensional trust substrate).

**Privacy and minimization:**

Evidence stored inline must respect data minimization. Sensitive
attributes (PII, credit scores, medical info) are referenced by ID,
not stored inline in the event. The storage capability holds the
underlying records with appropriate access controls; the event holds
the reference. This is also required by DPDP Act 2023 compliance.

## Consequences

**Positive:**

- **Kavach's accountability claim becomes operational.** Every decision
  is defensible because every decision has its evidence, reasoning,
  confidence, and producer captured at emission time. A compliance
  audit becomes a SQL query over decision events, not an
  archaeological excavation.

- **The substrate accumulates labeled training data.** Every
  false-positive flag, every true-positive confirmation, every
  partial-correction becomes ML-ready data. Competitors building
  similar substrates from scratch have to bootstrap their data; we
  accumulate ours through normal customer operation.

- **Decision quality improves continuously.** With feedback events,
  the system can detect drift ("recent decisions from this rule have
  high false-positive rates"), surface candidates for rule refinement,
  and (eventually) automatically suggest improvements.

- **Cross-customer learning becomes possible (with consent).** Aurvia
  can offer "your decisions are X% more conservative than the median
  customer in your segment" insights without exposing individual
  customer data, because the substrate has uniform decision
  vocabulary across customers.

- **Regulatory defense is concrete.** When a regulator asks "why did
  the agent deny this customer?", the answer is a single event with
  every relevant field. No interpretation required.

**Negative:**

- **Decision events are larger than minimal events.** Storage cost
  is higher. At BFSI Tier-A scale (millions of decisions per day per
  customer), this is non-trivial. Mitigation: evidence references
  rather than inline storage where evidence is large; periodic
  archival of resolved old decisions.

- **Discipline cost on every decision-emitting capability.** Every
  capability emitting a decision must construct the four embedded
  fields correctly. Mitigation: helper builders in
  `kavach/events/decision_helpers.py`; PR review checklist for
  decision events.

- **Reasoning trace quality depends on the producing capability.**
  A capability with a poorly-articulated rule engine produces poor
  reasoning traces. The discipline forces the engine to articulate
  its reasoning, which is itself good; but bad engines cannot hide.

- **Feedback collection requires UX work.** The operator console
  must make it easy for operators to mark FPs and TPs. This is real
  work in the experience layer.

- **Cross-customer learning requires explicit data agreements.**
  We don't get cross-customer learning for free; customer contracts
  must permit it (typically as aggregated, anonymized, opt-in
  insights). This is a sales conversation per customer.

## Alternatives Considered

- **Carry only evidence; reasoning and confidence are optional.**
  Considered. Rejected because reasoning is the field auditors care
  about most ("on what basis"); making it optional means it gets
  omitted under pressure, defeating the discipline.

- **Carry evidence as opaque blobs; structure later if needed.**
  Considered. Rejected because retrofitting structure onto historical
  events is expensive; structured-from-day-one is much cheaper
  long-term.

- **Skip feedback events; treat the operator console UI as the
  source of truth for FP/TP labels.** Considered. Rejected because
  UI-only state is not auditable, not exportable, not training-data
  ready, and not consistent with ADR-0008's "events are primary
  output" stance.

- **Generic JSON payload for decision details (no Pydantic types).**
  Considered. Rejected because mypy strict + Pydantic models catch
  decision-construction bugs at type-check time. Generic JSON is
  one source of "decision emitted but reasoning trace empty" bugs.

- **Tie reasoning trace shape to a specific reasoning framework
  (e.g., Drools, ELI, formal CNF).** Considered. Rejected because
  the substrate must accommodate rule engines, model-based
  reasoners, and human decisions uniformly. A common
  reasoning-trace schema with kind-discriminator (rule / model /
  composite / human) is more flexible than framework-specific
  schemas.

## References

- ADR-0005 — Accountability positioning (the claim this ADR makes
  operational)
- ADR-0008 — Events as primary output (decision events are the
  substantive content of accountability)
- ADR-0010 — Event schema versioning (embedded decision-primitive
  types are versioned per the same rules)
- ADR-0011 — Sub-product extraction (audit and policy sub-products
  inherit this discipline)
- ADR-0014 (Block D.4) — Multidimensional trust substrate
  (uses these decision events as input)
- `kavach/events/schemas/decision_primitives.py` — established in
  W01-S02 Block E
- `kavach/events/decision_helpers.py` — established in W01-S03+
  when the first decision-emitting capability lands
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) — PR
  checklist for decision events
