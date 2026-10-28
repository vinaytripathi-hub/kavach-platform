# Kavach Platform — Security Whitepaper (Prototype)

This whitepaper describes the security posture of the Kavach prototype for
a partner CISO. It is honest about what is implemented and what is
deferred to production hardening.

## Architecture in brief

Three layers ([ADR-0001](../adr/0001-three-layer-architecture.md)): a
substrate (events, capabilities, projections), use-case configs, and
experiences (API + operator console). Domain events are the source of
truth ([ADR-0008](../adr/0008-events-as-substrate-primary-output.md));
read models are derived projections ([ADR-0009](../adr/0009-read-side-projections.md)).
Everything runs in the partner's perimeter
([ADR-0017](../adr/0017-on-prem-deployment-posture.md)).

## Identity and authentication

- **Agents** present a bearer credential verified through the `sdk_bridge`
  `CredentialVerifier` Protocol ([ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
  The prototype default is an offline deterministic verifier; the Pramana
  adapter verifies real presentations and delegation chains. An agent can
  only act as its own `agent_id` (enforced at the API boundary).
- **Operators/admins** present a Kavach-issued bearer token; access is
  tenant-scoped.
- Transport security (TLS/mTLS) is terminated at a reverse proxy in front
  of the API in production; it is a deployment-edge concern, not embedded
  in application code.

## Signed mandates

High-impact actions can require a signed mandate
([ADR-0018](../adr/0018-signed-mandates-and-policy-integration.md)).
The presented token is verified outside the agent's reasoning path.
The decision evidence stores the mandate digest and the originator
identity, not the raw token. Revocation is checked before the policy
effect is applied. The audit chain is signed through a `Signer`
boundary; the shipping signer is HMAC-SHA256, with a KMS stub for
deployments that will move the key into an HSM.

## Tamper-evident audit

Every event is written to an append-only log and, in the same
transaction, chained into an HMAC-SHA256 record linking to its
predecessor ([ADR-0012](../adr/0012-decision-events-with-evidence-and-reasoning.md)).
Evidence exports carry a detached signature manifest over the chain head;
any payload change, reordering, insertion, or deletion breaks the chain
and is detectable by recomputation with the signing key.

## Data minimisation

Sensitive records (PII, credit data) are referenced by id; only compact,
non-sensitive attributes are stored inline in events. This aligns with
DPDP Act 2023 and eIDAS selective-disclosure expectations.

## Idempotency and at-least-once delivery

State-changing requests accept an `Idempotency-Key`; replays return the
original result. Outbound webhook delivery uses a transactional outbox
([ADR-0008](../adr/0008-events-as-substrate-primary-output.md)) with
HMAC-signed payloads and retry, so partner systems can dedupe.

## Secrets

Secrets (DB password, JWT secret, audit HMAC key) are supplied at deploy
time via environment variables, never baked into the image
([ADR-0017](../adr/0017-on-prem-deployment-posture.md)).

## Known limitations (prototype)

- Audit signing uses a software-held HMAC key; production should use an
  HSM/KMS with rotation.
- The shared operator token is a placeholder for a real operator IdP /
  RBAC integration.
- The per-tenant audit chain advances without an explicit row lock;
  concurrent high-throughput writers need a chain-head lock in production.
- TLS/mTLS, rate limiting at the edge, and WAF are deployment concerns not
  exercised by the prototype.

## Supply chain

Dependencies are pinned with lower bounds and major-version caps. CI runs
`pip-audit` and CodeQL ([.github/workflows](../../.github/workflows)).
Pramana (AGPL-3.0) is consumed only via its public SDK boundary; Kavach
contains no Pramana source ([ADR-0003](../adr/0003-pramana-kavach-separation.md)).
