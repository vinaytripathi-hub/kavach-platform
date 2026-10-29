# Kavach Platform — Business User Guide

> **Covered as of Phase 1.** This guide describes only what has shipped and
> been tested in the current working prototype. Features that are planned for
> later phases are clearly marked as *coming later* and are not yet available.

This guide is written for **business readers in banking, financial services,
and insurance (BFSI)** — business line owners, compliance officers, risk and
operations managers, and audit teams. It contains no code, no technical
payloads, and no commands. It explains, in plain language, *what Kavach is,
what problem it solves, how a human stays in control of AI agents, and how
Kavach supports your compliance obligations*.

---

## 1. Executive summary

Banks and insurers are beginning to deploy **autonomous AI agents** — software
that can act on its own to move money, open or service accounts, answer
customers, and make or recommend decisions. The business upside is real. The
governance problem is equally real: **when an agent acts, who authorized it,
was the action within bounds, and can you prove it afterwards?**

Traditional controls assume a human clicks the button. Agents remove the human
from the moment of action, which breaks the usual accountability trail. A
regulator, an auditor, or your own risk committee will still ask the same
questions they always ask — and "the AI did it" is not an acceptable answer.

**Kavach is the accountability layer around those agents.** It is *not* an AI
model and it does not make your agents smarter. It is a **source-available
agent-accountability substrate** purpose-built for Indian BFSI that:

- **Keeps a human in control** of what agents are allowed to do, by requiring
  explicit human approval for high-impact actions.
- **Checks every proposed action against policy** before it happens, and
  returns a clear decision: **allow, deny, or step-up (escalate to a human)**.
- **Records cryptographically signed, tamper-evident evidence** of every
  decision, so you can prove after the fact exactly what happened and why.
- **Runs entirely inside your own perimeter**, so sensitive data never leaves
  your environment.

In short: agents can move fast on routine work, while the actions that carry
real risk are gated by a human and permanently, verifiably recorded.

---

## 2. Key concepts in plain language

You only need a handful of concepts to understand everything else in this
guide.

**Agent.** A piece of AI-driven software that proposes and takes actions on
behalf of your organization or your customer — for example, a customer-service
assistant that can look up a balance or initiate a transfer.

**Originator.** The party who actually *authorized the task* in the first
place — a human, a service, another agent, or (in future) a customer's digital
wallet. The originator is distinct from the agent. The originator says "do
this, within these limits"; the agent carries it out.

**Mandate.** A **bounded, signed authorization** from an originator to an
agent. A mandate says, in a verifiable way, *which actions* the agent may take
and *under what constraints* (for example, "may transfer up to a set amount, to
an approved payee, before a certain time"). Because the mandate is
cryptographically signed, anyone downstream can confirm it is genuine and was
not tampered with. If a specific action is not covered by a valid mandate, it
can be refused — even if the agent's general credentials would otherwise allow
it. Mandates can be **revoked** before they expire.

**Policy decision.** For every proposed action, Kavach's policy engine returns
one of three outcomes:

- **Allow** — the action is within bounds; it proceeds.
- **Deny** — the action is out of bounds; it is blocked and logged.
- **Step-up** — the action is high-impact and requires a human to approve or
  reject it before it can proceed.

Policy decisions are **deterministic**: the same inputs always produce the same
outcome, and the decision is made by rules *outside* the AI model, so a cleverly
worded prompt cannot talk the system into granting more permission.

**Human step-up approval.** When policy returns *step-up*, the request goes
into a **queue** that a human operator reviews. The operator sees the context
and then **approves or rejects**. Nothing high-impact happens without that human
decision, and the human's decision is itself recorded.

**Signed evidence / audit trail.** Every event — the proposed action, the
policy decision, the human approval or rejection, the mandate that authorized
it — is written into an **append-only, tamper-evident chain**. Each record is
cryptographically linked to the one before it, so any later alteration is
detectable. You can **export a signed "evidence pack"** for a given agent and
time window, and an auditor can independently verify that it has not been
changed.

**Trust assessment.** Rather than reducing an agent to a single "trust score,"
Kavach tracks trust across **several dimensions** (for example, the integrity of
its credentials, the consistency of its behavior, and its compliance with
policy). Each dimension also carries an honest indicator of **how much data it
is based on** — a brand-new agent is reported as "cold / limited data" rather
than being given a falsely confident rating. Trust is treated as an *input* to
decisions, never as the sole decider.

---

## 3. How a human stays in control: the decision lifecycle

The best way to understand Kavach is to follow a single high-impact action from
start to finish. The scenario below is the **customer-service** use case that
ships and is tested in the current prototype.

**The situation.** A customer-service agent is handling a request that involves
**initiating a transfer of funds**. This is exactly the kind of action where a
mistake — or a manipulated agent — is costly and hard to reverse.

**Step 1 — The agent proposes an action.** The agent does not simply execute
the transfer. It asks Kavach whether it is allowed to, presenting its own
credentials and the **mandate** that authorized the task.

**Step 2 — Policy evaluates it.** Kavach's policy engine checks the request
against the rules for this use case. For transfers, the rules require a valid
mandate that actually covers this action and its amount. Because a transfer is
high-impact, the policy outcome is **step-up**: a human must approve.

**Step 3 — The request enters the step-up queue.** The escalation is recorded
with the reason it was raised and the role required to resolve it. It now
appears in the operator console's step-up queue.

**Step 4 — A human operator decides.** An authorized operator reviews the
request in context and either **approves** or **rejects** it. This is the moment
of human oversight — the deliberate point where a person, not the AI, makes the
call on a consequential action.

**Step 5 — Signed evidence is recorded.** Every part of this story — the
proposed action, the policy evaluation, the mandate reference, and the
operator's approval or rejection — is written into the tamper-evident audit
chain, signed, and permanently linked. Later, you can export and independently
verify the whole sequence.

The result: the agent handled the routine parts of the interaction on its own,
but the risky action was **gated by a human and fully evidenced**. If a
regulator later asks "who authorized this transfer, was it in scope, and who
approved it?", the answer is a signed record, not a guess.

---

## 4. Workflows business users care about

These are the day-to-day activities the current prototype supports. Several of
them are exposed through the **operator console** — a simple screen-based
interface that needs no technical skills — while a few are currently performed
through Kavach's administrative interface rather than the console (each is noted
below).

**Issuing and revoking mandates.** An authorized operator can issue a mandate
that authorizes an agent to perform a bounded set of actions under specific
constraints (such as an amount limit, an approved payee, or an expiry time). If
circumstances change — a task is cancelled, a risk is identified — the mandate
can be **revoked before it expires**, immediately removing the agent's authority
for any action that depended on it. Both issuance and revocation are recorded as
signed events.

> *Note on current maturity:* mandate issuance and revocation work end-to-end
> today through Kavach's administrative interface; they are **not yet part of the
> point-and-click operator console**. Console screens for mandate issuance and
> revocation, along with reusable mandate templates, are **coming in a later
> phase**.

**Reviewing the step-up queue.** The console shows every action that policy has
escalated for human approval, with the reason and required role. An operator
works through the queue, reviewing each item and recording an **approve** or
**reject** decision. This is the core human-oversight workflow and is fully
functional today.

**Reviewing agent activity and trust.** For any agent, an operator can view a
**timeline** of its activity and its current **multidimensional trust
assessment**, including the honest data-sufficiency indicators described above.

**Monitoring for anomalies.** Kavach continuously watches agent behavior for
patterns such as unusual rates of activity, drift in outcomes, scope expansion,
or drops in confidence. When something stands out, it raises an **anomaly** that
operators can see and acknowledge, and that the policy engine can take into
account when making future decisions.

**Exporting a verifiable audit trail.** For any agent and time window, an
operator can request a **signed evidence pack**. This export is tamper-evident:
an auditor who holds the verification key can independently confirm it is
complete and unaltered. This is the artifact you hand to internal audit, to a
regulator, or to a dispute-resolution process.

---

## 5. Compliance value in business terms

Kavach is designed so that each compliance obligation maps to a **running
mechanism**, not a written intention. This section summarizes that mapping in
business language. It is informational and is **not legal advice**; your
compliance and legal teams remain the authority on how these obligations apply
to you.

### EU AI Act — human oversight and accountability

The EU AI Act sets expectations for high-risk AI systems that are directly
relevant to agentic deployments:

- **Human oversight (Article 14).** The Act expects that a human can oversee and
  intervene in the system. Kavach implements this concretely through
  **graduated authority**: routine actions proceed automatically, high-impact
  actions are **escalated to a human** who approves or rejects them, and
  rejections are logged. This is *implemented and tested today*.
- **Record-keeping and logging (Articles 12 & 13).** The Act expects automatic
  logging and transparency about how outputs were produced. Kavach keeps an
  **append-only, tamper-evident audit chain**, and every decision carries its
  supporting evidence, reasoning, and confidence. *Implemented today.*
- **Risk management and quality processes (Articles 9 & 17).** Every proposed
  action is checked against a versioned rule set with a **default-deny** posture
  outside the approved action schema, and the platform is built under a
  disciplined, documented engineering process. *Implemented today.*
- **Accountability along the value chain (Article 25).** Each decision records
  *what made it* and the authorization behind it, so accountability is a design
  property rather than something reconstructed after an incident. *Implemented
  today.*
- Some deployer-facing items (for example, broader post-market monitoring
  dashboards) are **partial today** and mature in later phases.

### NIST agentic identity design tenets

In October 2026, NIST / NCCoE published design tenets for agent identity
management systems. Kavach maps directly onto the **accountability-focused**
tenets. In business terms, the tenets fully implemented and tested today
include:

- **Human-in-the-loop triggers** — risk-based escalation to a person.
- **Signed mandates and constraints** — bounded, verifiable authorization of
  what an agent may do.
- **Separation of policy from reasoning** — permission decisions are made
  outside the AI model, so prompts cannot expand permissions.
- **Deterministic access decisions** — consistent, repeatable outcomes.
- **Continuous monitoring** — agent-specific anomaly detection.
- **Immutable evidence** — an independent, tamper-evident chain of custody.

Other tenets — notably **short-lived, automatically revocable authorization**
and **zero standing privilege** — are **partial or planned** in the current
prototype, and the platform's own documentation is explicit about this. The
honest message to a risk committee is: *the accountability core is built and
tested; identity-lifecycle hardening is on the roadmap.*

> **Important framing.** Kavach provides **mechanisms that support** these
> obligations. It does not, by itself, make your organization compliant; that
> depends on how you deploy, configure, and operate it alongside your other
> controls. Avoid representing Kavach as a guarantee of regulatory compliance.

### Data residency and sovereignty

Kavach runs **inside your own environment**. Because the entire stack is
deployed within your perimeter, **no data leaves your environment**, which
directly supports Indian data-residency expectations and sovereign-hosting
requirements.

---

## 6. What exists today vs. what is coming

Being honest about scope is a core principle of this guide.

**Available and tested today (Phase 1):**

- The accountability substrate: policy decisions (allow / deny / step-up),
  signed tamper-evident evidence, multidimensional trust, and continuous
  anomaly monitoring.
- **Signed mandates**: issuing, presenting, and revoking bounded authorizations,
  with the customer-service transfer path requiring a mandate.
- The **customer-service use case**, driven end-to-end from proposed action
  through human step-up to signed evidence export.
- The **operator console** with timeline, anomalies, trust, step-up queue, and
  evidence-export screens.
- On-premise deployment inside your own perimeter.

**Coming in later phases (not yet available):**

- **Additional use cases** beyond customer service (for example, credit
  underwriting and trading are planned but not yet built).
- **Developer SDKs and integration helpers** to make it easier for your teams to
  connect agents and to issue mandates. *Documentation for these will appear in
  this guide only once they actually ship.*
- **Operator console polish**, including mandate-issuance wizards and reusable
  mandate templates.
- **Identity-lifecycle hardening**: shorter-lived and automatically revocable
  authorizations, stronger operator sign-in, and hardware-backed key custody for
  signing.
- **Broader compliance dashboards** over the monitoring and feedback loop.

As each of these lands and is tested, a future version of this guide will
describe it and the "Covered as of Phase N" marker at the top will advance.

---

## 7. Glossary

- **Agent** — AI-driven software that proposes and takes actions on behalf of
  your organization or a customer.
- **Originator** — the party (human, service, agent, or wallet) that authorized
  the task the agent is carrying out.
- **Mandate** — a bounded, cryptographically signed authorization from an
  originator to an agent, defining allowed actions and constraints; can be
  revoked before expiry.
- **Constraint** — a specific limit within a mandate (for example, a maximum
  amount or an approved payee).
- **Policy decision** — the outcome of checking a proposed action against the
  rules: **allow**, **deny**, or **step-up**.
- **Step-up** — an escalation that requires a human to approve or reject a
  high-impact action before it proceeds.
- **Step-up queue** — the list of pending escalations awaiting operator review.
- **Operator** — an authorized human who reviews escalations, issues and revokes
  mandates, and reviews agent activity.
- **Evidence pack** — an exportable, signed, tamper-evident bundle of records for
  an agent and time window that an auditor can independently verify.
- **Audit chain** — the append-only, cryptographically linked record of all
  events; any later tampering is detectable.
- **Trust assessment** — a multidimensional view of an agent's trustworthiness,
  each dimension accompanied by an honest indicator of the data behind it.
- **Anomaly** — a flagged pattern in agent behavior (such as an unusual rate,
  outcome drift, scope expansion, or confidence drop).
- **Data sufficiency** — an honest indication of how much data an assessment is
  based on, so cold-start agents are not given falsely confident ratings.
- **Perimeter** — your own controlled environment, inside which Kavach runs and
  where your data stays.

---

## Changelog

- **Phase 1 — initial guide:** substrate concepts, mandate + step-up +
  signed-evidence workflows, compliance framing.
