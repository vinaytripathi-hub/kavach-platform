# FIDO Agentic Standards Mapping — AP2, Verifiable Intent, AATWG

This document maps the agentic standards track that the FIDO Alliance
opened on 28 April 2026 onto Kavach mechanisms. It sits beside the
[NIST tenets crosswalk](./nist-agentic-iam-mapping.md). Status legend:
**Implemented** · **Partial** · **Planned**.

## What the specifications do not cover

Google AP2 (v0.2) defines mandate credentials and the verification
duty of each role. Mastercard Verifiable Intent (v0.1-draft) defines
the layered SD-JWT and the constraint check. Both leave the following
to the deployer runtime:

- transport and API surface
- key custody beyond the credential itself
- enrollment and lifecycle
- dispute-resolution workflow
- regulatory evidence export (PCI DSS, PSD2, EU AI Act, DPDP, RBI)

Kavach is that runtime: policy enforcement, human step-up, and a
tamper-evident audit chain.

## Google Agent Payments Protocol (AP2 v0.2)

| AP2 element | Kavach mechanism | Status |
|-------------|------------------|--------|
| Shopping Agent | External agent calling `POST /v1/agents/{id}/decisions` | Implemented |
| Credential Provider | `CredentialVerifier` adapter (Pramana, deployer IdP, or fake) | Partial |
| Trusted Surface (must be non-agentic) | Operator issuance of mandates; policy engine is deterministic code | Partial |
| Merchant / Merchant Payment Processor | Downstream systems that verify the exported mandate digest | Planned (partner verifier guide) |
| `mandate.checkout` | Referenced by payment-mandate `transaction_id`; checked in `AP2MandateVerifier` | Implemented |
| `mandate.payment` / `mandate.payment.open` | `AP2MandateVerifier` parses the payment mandate and translates constraints | Implemented |
| Constraint vocabulary (amount, payee, instrument, budget) | `MandateConstraint` paths consumed by `PolicyEngine` | Implemented |
| Dispute evidence | HMAC audit chain + signed evidence pack containing the mandate digest | Implemented |

## Mastercard Verifiable Intent (v0.1-draft)

| VI layer | Kavach mechanism | Status |
|----------|------------------|--------|
| L1 identity (issuer-signed) | `CredentialVerifier` / Pramana presentation | Partial |
| L2 immediate (user confirms final values) | Mandate with concrete constraints, no parent attenuation | Implemented (mandate model) |
| L2 autonomous (constraints + agent key) | `Mandate.action_scope` + `constraints` | Implemented |
| L3 agent execution within L2 | `parent_mandate_id` strict-subset check in `FakeMandateVerifier` | Implemented |
| Selective disclosure | Evidence stores mandate by digest, not the full token ([ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md)) | Implemented |
| Dedicated VI SD-JWT adapter | `VIMandateVerifier` | Planned |

## FIDO Agentic Authentication Technical Working Group

| Focus area | Kavach mechanism | Status |
|------------|------------------|--------|
| Verifiable user instructions | Signed `Mandate` presented on `X-Kavach-Mandate` | Implemented |
| Agent authentication | Distinct agent principal; token may act only as its own `agent_id` | Partial (cryptographic root is the adapter) |
| Trusted delegation for commerce | Scope attenuation + per-rule `mandate_required` | Implemented |
| Phishing-resistant user authentication at issuance | Deployer IdP / passkey in front of mandate issuance | Planned (deployment edge) |

## What ships today

The substrate verifies a mandate (fake HMAC or AP2-shaped payment
mandate), requires it from policy, records `MandateIssued` /
`MandatePresented` / `MandateRevoked` on the audit chain, and exports
the mandate digest inside the signed evidence pack. See
[ADR-0018](../adr/0018-signed-mandates-and-policy-integration.md).
