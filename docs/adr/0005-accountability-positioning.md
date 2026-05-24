# ADR-0005 — "Accountability for BFSI agents" market positioning

**Status:** Accepted
**Date:** 2026-05-24

## Context

The AI agent infrastructure market in 2026 is crowded with adjacent
plays, most of which solve part of the problem we care about:

- **Microsoft Entra Agent ID** and **AWS AgentCore** — agent
  identity and credentialing. Solid for "who is this agent,"
  weaker on "what did this agent do and was it authorized."
- **LangChain, AutoGen, CrewAI** — agent orchestration frameworks.
  They produce agents; they don't supervise them.
- **OpenAI, Anthropic** — model providers. They host the brains,
  not the trust layer.
- **Verifiable Credential and DID ecosystem players** — solve
  identity-issuance but don't address operational supervision.
- **Traditional fraud detection, transaction monitoring, AML
  platforms** — solve human-operator misbehavior detection; not
  designed for autonomous agent activity at AI cadence.

There is a gap: **operational accountability for AI agents in
regulated environments.** Specifically, the ability to answer,
in real-time and post-hoc, with cryptographic evidence:

- What did the agent do?
- On whose authority?
- Was the action within authorized scope?
- What inputs and context drove the decision?
- Did the outcome match expert judgment?

BFSI is the sharpest market for this because:

- Regulators already require human-equivalent accountability for
  every decision that touches money, credit, or financial advice.
  Agent activity has to meet that bar.
- Compliance officers, internal auditors, and external regulators
  routinely demand evidence trails. AI agents that cannot produce
  them are functionally unusable in regulated workflows.
- Tier-A BFSI enterprises are large, can pay, are conservative
  enough to want third-party trust infrastructure rather than
  building their own, and have explicit AI deployment roadmaps.

The wedge has to be sharp enough to win attention from BFSI buyers
who already deal with many vendors, and broad enough to expand
beyond the initial three use cases into a multi-product platform.

## Decision

Kavach Platform positions as **"Agent Accountability for Indian BFSI."**

The positioning has three components:

1. **Accountability, not identity.** Identity is necessary but
   not the differentiator. Microsoft Entra Agent ID and AWS
   AgentCore handle agent identity. Aurvia builds the operational
   layer on top: what the identified agents do, with what
   authorization, with what evidence, with what outcomes. Pramana
   (the open-source substrate) provides identity primitives;
   Kavach (the commercial layer) supervises agents acting in
   BFSI workflows.

2. **BFSI-first, not BFSI-only.** The wedge is BFSI because the
   compliance pressure makes accountability urgent and the
   willingness-to-pay is high. But the architecture is designed
   to extend beyond BFSI later (insurance claims, healthcare
   agents, government services, enterprise-SaaS agent supervision)
   as the multidimensional trust substrate matures (ADR-0014,
   planned in Block D). The positioning supports both narratives:
   "we solve BFSI's hardest agent problem today" and "we are
   building trust infrastructure for the agent economy."

3. **Indian-sovereign, globally-relevant.** The first market is
   Indian BFSI for two reasons: it is genuinely underserved by
   existing global vendors (whose products were not designed for
   India's DPI integration, regulatory specifics, or
   data-residency requirements); and it is large enough to
   sustain a multi-year build. Aurvia explicitly positions as a
   sovereign Indian provider (per ADR-0004). The substrate is
   reusable globally; the initial go-to-market is India.

The positioning language used externally:

- **One-liner:** "Agent Accountability for Indian BFSI."
- **Tagline (longer):** "The trust substrate for AI agents
  deployed in banking, financial services, and insurance."
- **Brand stance:** Aurvia is the company. Pramana is the
  open-source substrate. Kavach is the BFSI commercial layer.
  Future Aurvia products use the substrate for other verticals.

## Consequences

**Positive:**

- A defensible position that is not directly contested by any
  existing player. Microsoft and AWS sell agent identity;
  Aurvia sells what comes after. The complementarity is genuine,
  which makes co-selling and integration partnerships viable.
- The "Accountability" frame resonates with compliance officers,
  internal auditors, and CISOs — the buyers who hold the budget
  in BFSI. It does not require explaining new concepts; it
  attaches to an existing organizational mandate.
- The Indian-sovereign positioning is hard for global hyperscaler
  competitors to credibly counter. They can run in Indian regions
  but cannot match the regulatory and political-stability
  positioning of a sovereign Indian provider.
- The BFSI-first / BFSI-not-only frame leaves expansion paths
  open without diluting the initial wedge. Investors can see both
  the near-term wedge and the long-term ambition.

**Negative:**

- "Accountability" is not as catchy as "agent identity" or
  "agent orchestration" in social media and casual tech discourse.
  We are betting that the buyer (compliance) cares more about
  precision than the marketer (developer relations). For BFSI this
  is the right bet; for an SMB-developer go-to-market it would
  not be.
- Tied to BFSI's regulatory cadence. If RBI, SEBI, or IRDAI
  significantly relax or alter their guidance, the positioning's
  urgency could weaken. Mitigation: the multidimensional trust
  substrate (ADR-0014, planned) is designed to retain value even
  if specific regulatory pressure points shift.
- Tied to India as a regulated market. If geopolitical or
  economic shifts make Indian BFSI less attractive, the wedge
  weakens. Mitigation: the substrate generalizes; non-Indian
  BFSI markets (Indonesia, Brazil, GCC) have similar profiles.

## Alternatives Considered

- **"Agent identity for enterprises."** Considered. Rejected
  because Microsoft Entra Agent ID and AWS AgentCore already
  occupy this space at the cloud-vendor scale; Aurvia would be
  perpetually a "me too" play.
- **"Agent orchestration for compliance teams."** Considered.
  Rejected because orchestration frameworks already exist
  (LangChain et al.), and "compliance team" framing positions us
  as a tools vendor rather than a substrate provider — narrower
  TAM, lower defensibility.
- **"AI safety for BFSI."** Considered. Rejected because "AI
  safety" is a contested term loaded with associations that don't
  serve our buyer (compliance teams want operational evidence,
  not philosophical alignment).
- **"Trust infrastructure for the agent economy"** without the
  BFSI-first qualifier. Considered. Rejected because the
  unqualified version is too abstract for a first-product wedge.
  We use it as the long-term aspirational frame, not the
  near-term go-to-market.
- **Vertical-agnostic positioning.** Considered. Rejected because
  the architectural choices that make Kavach valuable for BFSI
  (data residency on Yotta per ADR-0004, DPI integration per the
  capability roadmap, audit-chain rigor) would be over-engineered
  for non-regulated verticals. A vertical-agnostic substrate is
  worse at every specific vertical's actual needs.

## References

- ADR-0001 — Three-layer architecture
- ADR-0003 — Pramana–Kavach IP separation (Pramana is the
  open-source substrate that supports the Kavach commercial layer)
- ADR-0004 — Self-hosted Postgres on Yotta (the sovereign
  Indian infrastructure that backs the positioning)
- ADR-0014 (planned, Block D) — Multidimensional trust substrate
  (the technical foundation for expanding beyond BFSI later)
- README.md at this repository root — internal-audience overview
  reflecting this positioning
