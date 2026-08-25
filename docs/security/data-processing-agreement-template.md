# Data Processing Agreement (Template)

> Template for a Kavach prototype/pilot engagement. Not legal advice;
> review with counsel before execution. Bracketed values are filled per
> engagement.

This Data Processing Agreement ("DPA") supplements the agreement between
**[Partner / BFSI Entity]** ("Controller") and **Aurvia Global**
("Processor") for the Kavach Platform.

## 1. Roles

The Controller determines the purposes and means of processing personal
data. The Processor processes personal data only on documented
instructions from the Controller.

## 2. Subject matter and duration

- **Subject matter:** agent-accountability processing — recording agent
  actions, evaluating policy, generating audit evidence.
- **Duration:** the term of the underlying agreement / pilot.

## 3. Nature and purpose of processing

Recording and supervising autonomous-agent actions in BFSI workflows;
generating tamper-evident audit evidence and trust assessments.

## 4. Categories of data and data subjects

- **Data subjects:** the Controller's customers and the Controller's
  agent operators.
- **Categories:** agent identifiers and actions; decision metadata.
  Sensitive personal/financial records are referenced by identifier and
  **not** stored inline in the event log (data minimisation; see
  `docs/adr/0012-decision-events-with-evidence-and-reasoning.md`).

## 5. Location of processing (residency)

All processing occurs on infrastructure within **[India / partner
perimeter]**. The platform is self-hosted on the Controller's chosen host
(e.g. Yotta Yntraa); no personal data is transferred to a Processor SaaS.

## 6. Security measures

The Processor implements, at minimum: append-only event logging;
HMAC-SHA256 tamper-evident audit chaining with signed export;
tenant-scoped access control; credential verification for agents;
data minimisation by reference; secrets supplied at deploy time. See
`docs/security/security-whitepaper.md` and `docs/security/threat-model.md`.

## 7. Sub-processors

The Processor uses no sub-processors for in-perimeter deployments beyond
the Controller's chosen infrastructure provider. Any change requires prior
written notice.

## 8. Data subject rights

The Processor assists the Controller in responding to data-subject
requests (access, correction, erasure) under DPDP Act 2023, to the extent
technically feasible given data-minimisation by reference.

## 9. Breach notification

The Processor notifies the Controller without undue delay (and within
**[N]** hours) of becoming aware of a personal-data breach, with the
information needed for the Controller's regulatory reporting.

## 10. Return and deletion

On termination, the Processor returns or deletes personal data per the
Controller's instruction, subject to retention required by law.

## 11. Audit

The Controller may audit the Processor's compliance, including review of
the audit evidence chain and ADR-documented controls.

---

Signatures, effective date, and annexes (technical and organisational
measures, sub-processor list) attached per engagement.
