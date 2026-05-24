# ADR-0013 — Multimodal data sufficiency

**Status:** Accepted
**Date:** 2026-05-24

## Context

Per ADR-0012, every decision event the substrate emits carries
evidence, reasoning, and confidence. This commits the substrate to
honesty about *what it knows*. But there is a second class of
honesty that must be made explicit: honesty about *what it doesn't
know*.

Real BFSI agents arrive in Kavach in different states:

- **Cold-start.** A new agent just onboarded. No history. No
  behavioral baseline. No prior decisions to compare against. The
  substrate has its credential and delegation chain (from Pramana),
  but knows nothing about how this agent typically behaves.

- **Cold-context.** An agent the substrate has history on, but for
  a workflow context it has never seen before. (Agent-X has handled
  100 retail credit decisions but is now seeing its first
  small-business credit decision.)

- **Warm.** An agent with substantial history in the relevant
  context. Behavioral baselines are reliable. Decisions can be
  compared against expected patterns.

- **Stale.** An agent with history but where the history is too old
  to be reliable (no activity in >N days, or activity predating a
  significant context change — regulatory shift, model version
  change, customer cohort change).

The substrate's confidence in its outputs differs dramatically across
these states. A trust assessment for a warm agent is well-grounded;
a trust assessment for a cold-start agent is mostly priors. A
behavioral anomaly score for a stale-baseline agent may flag normal
behavior as anomalous because the baseline is wrong.

The naive failure modes:

1. **Treating cold-start as warm.** Output trust scores for new
   agents as if they were well-calibrated. The scores look
   authoritative; they aren't. Downstream consumers make decisions
   on false certainty. BFSI auditors will catch this.

2. **Hiding cold-start state.** Refusing to emit assessments for
   cold agents at all. This is honest but unhelpful — downstream
   policy still needs *something* to decide on.

3. **Ad-hoc confidence flags.** Each capability invents its own
   "data quality" indicator. Cross-capability comparison becomes
   impossible.

The substrate needs a uniform, structured way to communicate "how
much data underlies this output," composable across capabilities.

This honesty matters beyond BFSI too. The substrate's long-arc
positioning (ADR-0014) is "trust infrastructure for the agent
economy." Other regulated verticals (healthcare, government, large
enterprise SaaS) will have the same cold-start problem. Solving it
once, in the substrate, is the right place.

## Decision

**Every substrate output that depends on accumulated data carries a
`DataSufficiency` indicator.** This is a structured Pydantic type
versioned per ADR-0010.

A sketched shape:

```python
# kavach/events/schemas/data_sufficiency.py — sketch
class DataSufficiency(BaseModel):
    """Indicator of how much data underlies an output."""
    schema_version: ClassVar[int] = 1

    # Categorical band — primary consumer-facing field.
    band: Literal["cold", "thin", "warm", "warm_stale"]

    # Per-modality breakdown — fine-grained details.
    modalities: dict[str, ModalitySufficiency]

    # Overall reason, human-readable.
    summary: str

class ModalitySufficiency(BaseModel):
    """Sufficiency for one input modality."""
    schema_version: ClassVar[int] = 1
    modality: str               # e.g., "behavioral_baseline", "credential_chain"
    band: Literal["cold", "thin", "warm", "warm_stale"]
    observations: int           # how many data points contributed
    earliest: datetime | None   # oldest observation considered
    latest: datetime | None     # newest observation considered
    reason: str
```

**Four sufficiency bands, with explicit semantics:**

1. **`cold`** — Essentially no data for this modality. Outputs
   based on this modality should be treated as priors-driven,
   not data-driven. Downstream consumers should require
   additional verification (step-up authentication, human review,
   conservative policy defaults). Example: trust assessment for an
   agent on its first session.

2. **`thin`** — Some data, but below the threshold for reliable
   behavioral inference. Outputs are directional, not authoritative.
   Downstream consumers may use them with appropriate caution.
   Example: agent with 5 sessions in a new context.

3. **`warm`** — Sufficient data for reliable inference. Outputs
   can be relied on within the substrate's normal calibration.
   This is the default state for established agents in familiar
   contexts.

4. **`warm_stale`** — Historically sufficient data, but the most
   recent observations are too old to be trustworthy. Substantively
   similar to `thin` for consumer purposes, but distinguished
   because the remediation is different: cold-thin agents need
   more observations; warm_stale agents need *recent* observations.

**Per-modality bands compose into an overall band by the substrate's
composition rule:** the overall band is the worst (least confident)
modality's band, unless capability-specific composition logic
overrides. This conservative default is documented in each
capability's design notes.

**Modalities are open-ended and capability-defined.** Examples for
the trust capability:

- `behavioral_baseline` — historical activity patterns
- `credential_chain` — quality and recency of delegation evidence
- `peer_comparison` — how this agent compares to similar agents
- `outcome_feedback` — prior decisions' feedback labels
- `policy_compliance` — track record against policy rules

Each capability documents its modalities and the thresholds that
determine bands. Thresholds are configuration, not code, and live
in the use case config layer (ADR-0001) so different use cases
can tune them.

**Downstream consumers must read `DataSufficiency`.** Policy
capability, anomaly detection, the operator console, and customer-
facing transparency views all read the sufficiency indicator. None
silently treats a `cold` output as warm.

**Decision events (per ADR-0012) include the data sufficiency of
their inputs.** When a policy decision is based on a trust
assessment, the decision event's evidence references the trust
assessment AND records the trust assessment's `DataSufficiency`.
This way the audit trail captures not just "what was decided" but
"how much data underlay it."

## Consequences

**Positive:**

- **Cold-start is handled honestly.** The substrate emits outputs
  for new agents, but the outputs carry an explicit "cold" band.
  Downstream policy can require step-up authentication, human
  review, or conservative defaults without each capability having
  to special-case "what if this is a new agent."

- **Audit defensibility improves.** A regulator reviewing a
  decision sees not just the decision but the sufficiency of the
  data behind it. "The agent's trust score was 0.42 (cold-start,
  priors-driven)" is dramatically more defensible than "The agent's
  trust score was 0.42."

- **Cross-capability comparison becomes possible.** All
  capabilities use the same `DataSufficiency` type and the same
  four bands. The operator console can show "data sufficiency"
  uniformly across the dashboard.

- **Onboarding workflows have a clear handle.** "How does an agent
  get from cold to warm?" becomes a concrete substrate question:
  the substrate exposes thresholds, the use case config tunes them,
  the operator console shows progress.

- **Substrate honesty supports the long-arc positioning.** ADR-0014's
  "trust infrastructure for the agent economy" depends on the
  substrate being honest about its own confidence. Sufficiency
  bands are the technical mechanism for that honesty.

**Negative:**

- **Every data-driven output must compute sufficiency.** This is
  extra work per capability emit. Mitigation: shared helpers in
  `kavach/events/sufficiency_helpers.py` so capabilities aren't
  reimplementing the band-computation logic.

- **Sufficiency thresholds are tuning surface.** Different
  customers may want different thresholds (a conservative bank may
  want "warm" to require 100 observations; a more permissive
  fintech may accept 20). This is right — different use cases
  should tune — but it's also a configuration management
  responsibility. The use case config layer handles it.

- **"Composition by worst" can be too conservative.** A capability
  with one weak modality and four strong modalities gets a
  combined-band of the weak one. Mitigation: capabilities can
  override composition logic with explicit rules; the default
  is a conservative starting point, not a forced ceiling.

- **Sufficiency is one more thing for engineers to remember.**
  PR review must check that data-driven outputs include
  sufficiency. Mitigation: code review checklist in the
  engineering handbook; ruff custom rule (longer arc) that flags
  decision events without sufficiency references where they're
  expected.

## Alternatives Considered

- **No explicit sufficiency; let confidence (per ADR-0012) carry
  it.** Considered. Rejected because confidence and sufficiency are
  distinct concepts. A rule-based decision can be confidence-1.0
  (rule deterministic) but operate on cold data (sufficiency-cold).
  Conflating them obscures the distinction; auditors need both.

- **Single numeric "data quality score" instead of bands.**
  Considered. Rejected because the categorical bands are easier
  for downstream consumers to reason about than a continuous score.
  Per-modality observations counts are present for those who want
  the raw numbers.

- **Per-capability sufficiency types (no shared `DataSufficiency`).**
  Considered. Rejected because cross-capability composition is
  the whole point; the operator console must be able to show
  uniform sufficiency across capabilities.

- **Refuse to emit outputs for cold-start.** Considered. Rejected
  because downstream policy still needs *something* to act on
  during onboarding. Better to emit honest cold-start outputs than
  to leave downstream systems blind.

- **Use Bayesian credible intervals instead of bands.** Considered
  for the long arc — credible intervals are more theoretically
  precise. Rejected for v1 because the operational machinery
  (interval composition across capabilities, UI presentation,
  threshold-based policy) is substantially more complex than bands.
  Bands are the right starting point; intervals are revisitable
  when the use cases demand them.

## References

- ADR-0008 — Events as primary output (sufficiency is a field on
  outputs that capabilities emit)
- ADR-0010 — Event schema versioning (DataSufficiency is versioned)
- ADR-0012 — Decision events with evidence and reasoning
  (decisions reference their inputs' sufficiency in evidence)
- ADR-0014 — Multidimensional trust substrate (uses
  DataSufficiency per-dimension to communicate honesty about each
  trust facet)
- `kavach/events/schemas/data_sufficiency.py` — established in
  W01-S02 Block E
- `kavach/events/sufficiency_helpers.py` — established in W01-S03+
  when the first sufficiency-emitting capability lands
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) — PR
  review checklist; modality and threshold documentation guidance
