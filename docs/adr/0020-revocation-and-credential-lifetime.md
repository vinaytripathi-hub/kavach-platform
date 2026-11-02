# ADR-0020 — Revocation and credential lifetime

**Status:** Accepted
**Date:** 2026-10-30

## Context

NIST tenet 04 (*Short-Lived, Dynamic & Revocable Authorization*) is
the one tenet the substrate still marks **Weak**. The crosswalk
(`docs/compliance/nist-agentic-iam-mapping.md`) is explicit about why:

- Agent credentials are verified on every request, but `VerifiedAgent`
  carries no `exp`, `nbf`, or session. The fake verifier has no notion
  of time, and the Pramana adapter reads only `verified`, `holder_did`,
  and scopes. An agent bearer that was valid yesterday is valid forever.
- There is no general revocation endpoint for an agent or a credential.
  Mandate revocation (ADR-0018) is the only revocation path, and it
  covers the authorization grant, not the credential that presents it.
- Operator authentication is a static shared secret
  (`KAVACH_OPERATOR_TOKEN`). That is a separate decision (ADR-0021);
  this ADR covers the agent-side lifetime and revocation model.

Two facts constrain the design.

1. **The Pramana adapter is verify-only.** `LocalPramanaAdapter` calls
   `pramana.verify_presentation` and `verify_delegation_chain`. It does
   not mint, refresh, or revoke presentations. Kavach must not grow a
   dependency on an issuance API the SDK does not expose.
2. **The holder credential and the session credential are different
   objects.** The holder credential (a Pramana presentation, or the
   offline `agent:<id>:<scopes>` grammar in fake mode) proves *who the
   agent is*. A session credential is a short-lived Kavach-signed JWT
   that proves *this agent is allowed to call this API right now*,
   bound to a session, with an explicit `nbf`/`exp` and a revocable
   `jti`.

DPoP (RFC 9449) would bind that session credential to a client key so
a stolen bearer cannot be replayed from another process. It is the
right end state. It is also a sizable cryptographic surface (key
generation, `DPoP` header, `htm`/`htu`/`ath` binding, nonce) that does
not fit this phase without crowding out the lifetime and revocation
guarantees tenet 04 actually fails on today.

## Decision

**1. Kavach mints short-lived session credentials.** A new
`credentials` capability (`kavach/capabilities/credentials/`) issues a
Kavach-signed JWT after the holder credential has been verified by the
existing SDK bridge. Claims:

| Claim | Meaning |
|-------|---------|
| `sub` | Agent id |
| `sid` | Session id the credential is bound to |
| `jti` | Credential id (revocation key) |
| `scopes` | Scopes copied from the verified holder |
| `aud` | `SubstrateConfig.expected_audience` |
| `iat` / `nbf` / `exp` | Issued-at, not-before, expiry |

TTL is `min(requested, KAVACH_AGENT_CREDENTIAL_TTL_SECONDS)` and the
configured maximum is **900 seconds (15 minutes)**. A refresh token
rotates: presenting a valid, unexpired, unrevoked refresh token mints
a new session JWT and a new refresh token, and retires the previous
refresh token.

Exchange and refresh are API operations:

- `POST /v1/agents/{agent_id}/credentials` — bearer is the holder
  credential; response is the session JWT plus refresh token.
- `POST /v1/credentials/refresh` — bearer is the refresh token.

Refresh does not trust the refresh token alone. Before minting,
`refresh_session_credential` re-verifies the upstream holder credential
through `sdk_bridge.verify` (the same verifier that accepted it at
issuance). The holder token is stored with the credential family for
that check. A holder that no longer verifies does not produce a new
session credential.

The legacy `agent:<id>:<scopes>` grammar stays valid in `fake` mode so
existing demos keep running. It has no `exp`. Agent-level revocation
still applies to it. It is a development credential, not a session
credential. Every presentation logs a warning. Production (`pramana`
mode, and any mode other than `fake`) rejects it.

**2. `exp` and `nbf` are enforced at the API boundary**, before any
policy effect. `require_agent` verifies the presented token, then:

- `now < nbf` → 401 `credential_not_yet_valid`
- `now >= exp` → 401 `credential_expired`

Both are RFC 7807 `application/problem+json` with a stable problem
`type` URI, not `about:blank`. The same not-before check is added to
mandate verification (ADR-0018 already enforces `expires_at`; it does
not enforce a lower bound). Mandate `not_before` is optional; when
present and `now < not_before`, verification fails closed.

**3. Revocation is an authoritative row plus an event, checked before
policy effect.** Three revocation keys:

| Target | Store | Event | Checked |
|--------|-------|-------|---------|
| Mandate | `mandate_revocations` (exists) | `MandateRevoked` (exists) | At `decide`, as today |
| Agent | `agent_revocations` | `AgentRevoked` | In `require_agent`, every request |
| Credential | `credential_revocations` (by `jti`) | `CredentialRevoked` | In `require_agent`, every request |

Endpoints:

- `POST /v1/agents/{agent_id}/revoke`
- `POST /v1/credentials/{credential_id}/revoke`

Both are operator actions (ADR-0021). A revoked agent or credential is
denied on the **next** request. The check is a primary-key read inside
the request, not a projection lag, so the denial is well under one
second. Revoking an agent denies every later presentation of that
agent, including a freshly minted session credential.

A session credential and the refresh tokens that rotate it are one
credential family. Each refreshed credential records
`parent_credential_id` of the credential it was minted from: the
session credential at issuance, and the presented refresh credential
on rotation. Revoking any credential in the family revokes the family.
`refresh_session_credential` checks that revocation and returns 401
`credential_revoked` without minting a replacement, and a session
token in that family is denied on the next request. Retiring a refresh
token because it was rotated (`reason=rotated`) denies that refresh
`jti` only and does not revoke the family.

**4. DPoP is deferred.** This phase ships TTL, refresh, and
revocation. Proof-of-possession (RFC 9449 `DPoP`, `jkt` binding) is
explicitly out of scope and will be its own ADR when the session
credential is stable. Until then a stolen session JWT is replayable
until `exp` or revocation, which is why the TTL cap is 15 minutes and
revocation is synchronous.

## Consequences

**Positive:**

- Tenet 04's three concrete gaps — no TTL, no general revocation, no
  not-before — close without waiting on a Pramana issuance API.
- Session credentials are Kavach-signed and Kavach-revocable. The
  holder credential remains a Pramana (or fake) concern, preserving
  ADR-0003 and ADR-0015.
- Problem types are stable and machine-readable
  (`credential_expired`, `credential_not_yet_valid`, `agent_revoked`,
  `credential_revoked`).
- The revocation check shares the request path with authentication, so
  the "denied on the next request in < 1 s" gate is a property of the
  design, not of worker lag.

**Negative:**

- Kavach now mints tokens. `KAVACH_JWT_SECRET` (HS256) is the signing
  key for session and refresh tokens. Loss of that secret forges
  session credentials until it is rotated. HSM-backed signing remains
  a later hardening step (the audit signer already has a `kms_stub`
  mode; session signing does not, in this phase).
- Two credential shapes exist in `fake` mode (legacy dev token and
  session JWT). Production mode accepts only verifiable holder
  credentials exchanged for session JWTs.
- DPoP deferral leaves a replay window bounded by TTL and revocation.
  That is an accepted residual risk, recorded here so it is not
  rediscovered as a surprise.
- `VerifiedAgent` grows optional temporal fields. Callers that
  construct it positionally stay valid because the new fields default
  to `None` (no lifetime → no temporal rejection, which is how the
  legacy dev token behaves).

## Alternatives Considered

- **Mint short-lived presentations inside the Pramana adapter.**
  Rejected for this phase. The adapter has no issue/refresh entry
  point, and ADR-0015 forbids Kavach from depending on Pramana
  internals. Revisit if the public SDK grows an issuance API.
- **Enforce `exp`/`nbf` only, and defer issuance.** Rejected. Without
  a mint path there is nothing in the substrate that *has* an `exp`,
  so the enforcement would be dead code except for mandates (which
  already enforce expiry).
- **Include DPoP in this phase.** Rejected. It does not close the
  Weak disposition by itself, and it would delay the revocation and
  TTL gates. Recorded as a follow-up, not forgotten.
- **Check revocation only in the projection / worker.** Rejected.
  Projection lag would miss the "< 1 s on the next request" gate.
  The projection may still mirror revocation for operator views; the
  authoritative check is the revocation row.

## References

- [ADR-0015](0015-pramana-sdk-packaging-and-agpl-posture.md) — verify-only Pramana boundary.
- [ADR-0016](0016-external-api-surface-and-versioning.md) — `/v1` problem responses.
- [ADR-0018](0018-signed-mandates-and-policy-integration.md) — mandate expiry and revocation, the pattern this generalises.
- [ADR-0021](0021-operator-identity.md) — who is allowed to call the revoke endpoints.
- NIST tenet 04, `docs/compliance/nist-agentic-iam-mapping.md`.
- RFC 7519 (JWT), RFC 7807 (problem details). RFC 9449 (DPoP) — deferred.
