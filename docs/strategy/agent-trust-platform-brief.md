# Agent Trust Platform — Positioning Brief

**Agent Accountability for Regulated Finance.** The accountability runtime for
AI agents in banking and payments — mapped to the NIST agentic-IAM tenets, the
EU AI Act, and India's RBI/DPDP. Market sequencing is US-first, then the EU,
then India (ADR-0022).

One page. The claim, the architecture, the gap, the ask.

## The claim

Kavach is the only architecture we are aware of that maps **one-to-one**
to the ten design tenets published by NIST / NCCoE in *Design Tenets
for Agent Identity Management Systems* (27 October 2026). Existing
agent-identity offerings (Microsoft Entra Agent ID, AWS AgentCore)
address 1–2 of the tenets; policy-as-guardrails frameworks address 1–2
more. Nothing on the market today covers the full post-identity set
of accountability tenets as implemented, deterministic mechanisms.

Current scorecard: **7 implemented / 3 partial / 0 weak**. Tenets 04–10
are implemented and tested in the working prototype; tenets 01–03 are
partial. See the full crosswalk:
[docs/compliance/nist-agentic-iam-mapping.md](../compliance/nist-agentic-iam-mapping.md).

## The architecture — one platform, nine modules

Each module owns one or more NIST tenets and exposes a stable
Protocol-bounded interface. The deployer plugs their internal systems
(identity, HSM, policy store, audit lake, SIEM, notification channel,
event bus) into the matching adapter without touching the core.

```mermaid
flowchart LR
    subgraph deployer [Deployer internal systems]
        pid[Identity service]
        phsm[HSM / KMS]
        ppol[Policy stores]
        paud[Audit lake / SIEM]
        pmon[Observability]
        pnot[Notification channel]
        pbus[Internal event bus]
    end

    subgraph adapters [Connector adapters]
        aid[Identity adapter]
        ahsm[Signing adapter]
        apol[Policy rule provider]
        aaud[Audit sink]
        amon[Monitoring sink]
        anot[Operator channel]
        aeg[Egress channel]
    end

    subgraph core [Agent Trust Platform core]
        m1[Identity - T1 T2]
        m2[Mandate - T6]
        m3[Session and authz - T3 T4]
        m4[Policy engine - T7 T8]
        m5[HITL step-up - T5]
        m6[Audit chain and export - T10]
        m7[Monitoring and anomaly - T9]
        m8[Projections and console]
        m9[Egress and outbox]
    end

    pid --> aid --> m1
    phsm --> ahsm --> m6
    ppol --> apol --> m4
    paud <-- aaud <-- m6
    pmon <-- amon <-- m7
    pnot <-- anot <-- m5
    pbus <-- aeg <-- m9

    m1 --> m2 --> m3 --> m4 --> m5
    m4 --> m6
    m4 --> m7
    m6 --> m8
    m7 --> m8
```

### Module-to-tenet-to-connector map

| Module | NIST tenets owned | Connector seam | State |
|--------|-------------------|----------------|-------|
| **Identity** | 01 Distinct ID · 02 Linking & Delegation | `CredentialVerifier` Protocol — swap the Pramana adapter for an IdP / SPIFFE / EUDIW adapter | Partial (fake verifier is the default; cryptographic identity needs the Pramana or an equivalent adapter) |
| **Mandate** | 06 Mandates & Constraints | Signed `MandateIssued` events; originator is any principal in the deployer's identity graph | Built (AP2 SD-JWT + fake HMAC verifier) |
| **Session & Authorization** | 03 Least/Zero Standing · 04 Short-lived & Revocable | Task-scoped session credentials; TTL and revocation list; integrates with the deployer's identity provider | 04 Built (≤15-min session credentials, credential-family revocation, Keycloak OIDC operators); 03 Partial |
| **Policy Engine** | 07 Separation of Policy from Reasoning · 08 Deterministic Decisions | `PolicyRuleProvider` extension point — pull from deployer policy stores (OPA, internal) | Built |
| **Human-in-the-Loop** | 05 HITL Triggers | Operator channel adapter — Slack, PagerDuty, ticketing, or an internal operator console | Built |
| **Audit Chain & Evidence** | 10 Immutable Evidence | HSM/KMS adapter for the signing key; audit-sink adapter writes to the deployer audit lake / SIEM | Built (software key; HSM/KMS adapter is interface-ready) |
| **Monitoring & Anomaly** | 09 Continuous Monitoring | Metrics/anomaly sink adapter — Datadog, Splunk, internal observability; emits `AnomalyDetected` back to policy | Built |
| **Projections & Console** | cross-cutting | Can render in the deployer's internal admin surfaces, or standalone | Built |
| **Egress & Outbox** | cross-cutting | Signed webhooks and CAEP/SSF signals today; Kafka / internal-bus adapter for streaming | Built |

## The gap — honest status

**Implemented and tested today:** tenets 04, 05, 06, 07, 08, 09, 10 —
the accountability core, plus short-lived revocable authorization
(session credentials with family revocation and OIDC operator identity),
signed mandates, and continuous monitoring. **Partial:** 01 and 02
(cryptographic identity depends on wiring the Pramana adapter, or an
equivalent IdP / SPIFFE / EUDIW adapter, in place of the default fake
verifier) and 03 (least / zero standing privilege and a declarative
separation-of-duties primitive).

Aggregate: **7 of 10 tenets implemented** as running, tested mechanisms.
The remaining work is additive — none of it requires restructuring what
exists.

## The ask

A 6–8 week scoped POC on **one** agentic use case inside the
deployer's perimeter:

1. Wire the Identity adapter to the deployer's identity service, so
   tenets 01 and 02 run on cryptographic identity rather than the fake
   verifier.
2. Wire the Audit sink and Signing adapter to the deployer's audit
   lake and HSM.
3. Run the Customer Service use case end-to-end: KYC → step-up →
   operator resolution → signed evidence export, verified by internal
   audit.
4. Deliver a 10-tenet scorecard based on the POC run, plus a prioritized
   plan for the remaining work (tenet 03, and cryptographic maturity for
   01 / 02).

## Dependencies and notes

- Kavach is proprietary, source-available ([LICENSE](../../LICENSE),
  [NOTICE](../../NOTICE)). The identity substrate ([Pramana
  Protocol](https://github.com/vinaysflow/pramana-protocol)) is
  AGPL-3.0 and consumed only through its public SDK boundary
  ([ADR-0003](../adr/0003-pramana-kavach-separation.md),
  [ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
  Alternative identity adapters (deployer-internal, EUDIW, Entra Agent
  ID) satisfy the `CredentialVerifier` Protocol without substrate
  changes.
- Data residency is satisfied by where the deployer runs the stack
  ([ADR-0004](../adr/0004-self-hosted-postgres-on-yotta.md),
  [ADR-0017](../adr/0017-on-prem-deployment-posture.md)). Nothing
  leaves the perimeter.

## Reference

- NIST / NCCoE, *Design Tenets for Agent Identity Management
  Systems*, Cybersecurity Insights blog, 27 October 2026.
- Full crosswalk:
  [docs/compliance/nist-agentic-iam-mapping.md](../compliance/nist-agentic-iam-mapping.md).
- Companion mappings:
  [EU AI Act + eIDAS/EUDIW](../compliance/eu-regulatory-mapping.md);
  [India RBI/SEBI/IRDAI/DPDP](../compliance/india-regulatory-mapping.md).
