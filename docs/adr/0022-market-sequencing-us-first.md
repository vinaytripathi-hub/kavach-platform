# ADR-0022 — Market sequencing: US-first regulated finance

**Status:** Accepted
**Date:** 2026-11-02
**Supersedes (in part):** ADR-0005 — the market-choice sections only (the
`§ "Indian-sovereign, globally-relevant"` section of its Decision, the
external one-liner, and the tagline). ADR-0005's accountability-not-identity
thesis, its BFSI-domain rationale, and the Aurvia / Pramana / Kavach brand
strata remain in force.

## Context

ADR-0005 positioned Kavach as **"Agent Accountability for Indian BFSI,"**
with India as the first go-to-market. That choice was sound for the
infrastructure and compliance thesis, but three developments since then have
moved the place where the *vocabulary* and the *first design partners* are:

- **NIST/NCCoE Design Tenets for Agent Identity Management Systems**
  (blog dated 27 October 2026). These ten tenets are fast becoming the
  reference vocabulary that buyers, auditors, and security teams use to talk
  about agent accountability. They are US-originated, and the conversations
  that cite them are concentrated in the US.
- **FIDO's agentic-payments work** — Google's **Agent Payments Protocol
  (AP2)** and Mastercard's **Verifiable Intent** — is centered on US payment
  rails and participants. The payment-mandate primitives Kavach already
  verifies (ADR-0018) are being standardized in that US-centered forum.
- **Regulation E** (the US Electronic Fund Transfer Act / Reg E) liability
  questions for agent-initiated payments give US banks and payment providers
  the sharpest, nearest-term accountability need. "The agent did it" is not
  an answer a US institution can give a regulator or a disputing consumer.

The substrate is already **deployment-pluggable for data residency** (ADR-0004
self-hosted Postgres; ADR-0017 on-prem Compose-first posture). Where the stack
runs is a deployment decision, not a market-sequencing one, so re-sequencing
the go-to-market does not require any infrastructure change.

## Decision

Sequence the go-to-market **US-first**:

1. **US regulated finance (banking and payments)** is the first market. It is
   where the accountability vocabulary (NIST tenets), the emerging
   payment-mandate standards (AP2, Verifiable Intent), and the liability
   pressure (Reg E) concentrate — and therefore where the first design
   partners are.
2. **EU second** — the EU AI Act and eIDAS/EUDIW make it the most prescriptive
   regime and a strong second market.
3. **India third** — RBI / SEBI / IRDAI and the DPDP Act remain a target
   market; the India regulatory crosswalk already written retains its value.

The public positioning strings change accordingly:

- **One-liner:** "Agent Accountability for Regulated Finance."
- **Tagline:** "The accountability runtime for AI agents in banking and
  payments — mapped to the NIST agentic-IAM tenets, the EU AI Act, and India's
  RBI/DPDP."

**Data residency remains deployment-pluggable** per ADR-0004 and ADR-0017.
US-first is a sequencing-and-positioning decision, not an infrastructure one; a
deployment can still run entirely in India (or the EU, or on-prem) under the
same substrate.

### What this supersedes in ADR-0005

Only the **market-choice sections**: the `§ "Indian-sovereign,
globally-relevant"` component (item 3 of ADR-0005's Decision), the external
one-liner, and the tagline. Everything else in ADR-0005 — accountability as
the differentiator rather than identity, BFSI-first-not-only as the domain
framing, and all consequences unrelated to country sequencing — stands.

## Consequences

**Positive:**

- The pitch now aligns with the standards and vocabulary buyers actually cite
  (NIST tenets, AP2), shortening the distance between a conversation and a
  design-partner commitment.
- The first design-partner motion lands where the regulatory urgency is
  nearest-term (Reg E, agentic payments), rather than where the sales cycle is
  longest.
- EU and India stay explicitly on the roadmap, so the EU AI Act and RBI/DPDP
  crosswalks already written keep their value; this is a re-ordering, not a
  deletion.

**Negative:**

- The sovereign-Indian-provider edge that ADR-0005 led with no longer heads
  the story. The US market has more incumbents and a higher bar for a first
  reference deployment. Mitigation: the substrate is deployment-pluggable and
  the compliance crosswalks are multi-jurisdiction, so a US-first sequence does
  not strand the India work — it defers it.
- Re-sequencing mid-build risks message churn. Mitigation: the change is a
  string-and-ADR change only; no code, no package version bump (it ships with
  the Phase 2 exit).

**Neutral:**

- No code change and **no package version bump**. The positioning string change
  ships with the Phase 2 exit.

## Alternatives Considered

- **Keep India-first (ADR-0005 as written).** Rejected: the design-partner
  conversations and the standards vocabulary are US-centered right now; leading
  with India delays contact with where the market is actively forming.
- **EU-first.** Considered — the AI Act is the most prescriptive regime.
  Rejected as the *first* step: the agentic-payments vocabulary and the
  nearest liability pressure (Reg E, AP2) are US. The EU is a strong second,
  not the wedge.
- **Geo-agnostic "regulated industries" with no sequence.** Rejected: a first
  wedge needs a named first market. "US regulated finance" is sharp; the
  generic version is not.

## References

- ADR-0005 — the positioning this amends (market-choice sections superseded in
  part; the rest stands).
- ADR-0004 — self-hosted Postgres for data residency (remains pluggable).
- ADR-0017 — on-prem deployment posture (remains pluggable).
- ADR-0018 — signed mandates / AP2 verification (the US-centered payment
  standard this sequencing leans into).
- `docs/compliance/nist-agentic-iam-mapping.md`,
  `docs/compliance/eu-regulatory-mapping.md`,
  `docs/compliance/india-regulatory-mapping.md` — the multi-jurisdiction
  crosswalks that keep EU and India on the map.
- NIST/NCCoE, *Design Tenets for Agent Identity Management Systems*,
  27 October 2026.
