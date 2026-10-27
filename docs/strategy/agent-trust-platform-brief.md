# Agent Trust Platform — Positioning Brief

One page. The claim, the architecture, the gap, the ask.

## The claim

Kavach is the only architecture we are aware of that maps **one-to-one**
to the ten design tenets published by NIST / NCCoE in *Design Tenets
for Agent Identity Management Systems* (27 October 2026). Existing
agent-identity offerings (Microsoft Entra Agent ID, AWS AgentCore)
address 1–2 of the tenets; policy-as-guardrails frameworks address 1–2
    10|more. Nothing on the market today covers the full post-identity set
of accountability tenets (03–10) as implemented, deterministic
mechanisms.

See the full crosswalk:
[docs/compliance/nist-agentic-iam-mapping.md](../compliance/nist-agentic-iam-mapping.md).

## The architecture — one platform, nine modules

Each module owns one or more NIST tenets and exposes a stable
Protocol-bounded interface. The deployer plugs their internal systems
    20|(identity, HSM, policy store, audit lake, SIEM, notification channel,
event bus) into the matching adapter without touching the core.

```mermaid
flowchart LR
    subgraph deployer [Deployer internal systems]
        pid[Identity service]
        phsm[HSM / KMS]
        ppol[Policy stores]
        paud[Audit lake / SIEM]
        pmon[Observability]
    30|        pnot[Notification channel]
        pbus[Internal event bus]
    end

    subgraph adapters [Connector adapters]
        aid[Identity adapter]
        ahsm[Signing adapter]
        apol[Policy rule provider]
        aaud[Audit sink]
        amon[Monitoring sink]
    40|        anot[Operator channel]
        aeg[Egress channel]
    end

    subgraph core [Agent Trust Platform core]
        m1[Identity - T1 T2]
        m2[Mandate - T6]
        m3[Session and authz - T3 T4]
        m4[Policy engine - T7 T8]
        m5[HITL step-up - T5]
    50|        m6[Audit chain and export - T10]
        m7[Monitoring and anomaly - T9]
        m8[Projections and console]
        m9[Egress and outbox]
    end

    pid --> aid --> m1
    phsm --> ahsm --> m6
    ppol --> apol --> m4
    paud <-- aaud <-- m6
    60|    pmon <-- amon <-- m7
    pnot <-- anot <-- m5
    pbus <-- aeg <-- m9

    m1 --> m2 --> m3 --> m4 --> m5
    m4 --> m6
    m4 --> m7
    m6 --> m8
    m7 --> m8
```

    70|### Module-to-tenet-to-connector map

| Module | NIST tenets owned | Connector seam | State |
|--------|-------------------|----------------|-------|
| **Identity** | 01 Distinct ID · 02 Linking & Delegation | `CredentialVerifier` Protocol — swap Pramana adapter for an IdP / SPIFFE / EUDIW adapter | Prototype |
| **Mandate** | 06 Mandates & Constraints | Signed `MandateIssued` events; originator is any principal in the deployer's identity graph | Planned |
| **Session & Authorization** | 03 Least/Zero Standing · 04 Short-lived & Revocable | Task-scoped tickets; TTL and revocation list; integrates with the deployer's token service | Partial |
| **Policy Engine** | 07 Separation of Policy from Reasoning · 08 Deterministic Decisions | `PolicyRuleProvider` extension point — pull from deployer policy stores (OPA, internal) | Built |
    80|| **Human-in-the-Loop** | 05 HITL Triggers | Operator channel adapter — Slack, PagerDuty, ticketing, or an internal operator console | Built |
| **Audit Chain & Evidence** | 10 Immutable Evidence | HSM/KMS adapter for the signing key; audit-sink adapter writes to the deployer audit lake / SIEM | Built (software key) |
| **Monitoring & Anomaly** | 09 Continuous Monitoring | Metrics/anomaly sink adapter — Datadog, Splunk, internal observability; emits `AnomalyDetected` back to policy | Planned |
| **Projections & Console** | cross-cutting | Can render in the deployer's internal admin surfaces, or standalone | Built |
| **Egress & Outbox** | cross-cutting | Signed webhooks today; Kafka / internal-bus adapter for streaming | Built |

## The gap — honest status

**Built end-to-end today:** tenets 05, 07, 08, 10 (the accountability
core). Partial: 01, 02, 03, 09. Weak or planned: 04, 06.

    90|Approximate aggregate: ~55–60% as a working prototype, ~75% as a
design. The remaining tenets are additive modules — none require
restructuring what exists.

## The ask

A 6–8 week scoped POC on **one** agentic use case inside the
deployer's perimeter:

1. Wire the Identity adapter to the deployer's identity service.
2. Wire the Audit sink and Signing adapter to the deployer's audit
   100|   lake and HSM.
3. Run the Customer Service use case end-to-end: KYC → step-up →
   operator resolution → signed evidence export, verified by internal
   audit.
4. Deliver a 10-tenet scorecard based on the POC run, plus a prioritized
   plan for the remaining modules (04, 06, 09).

## Dependencies and notes

- Kavach is proprietary, source-available ([LICENSE](../../LICENSE),
  [NOTICE](../../NOTICE)). The identity substrate ([Pramana
   110|  Protocol](https://github.com/vinaysflow/pramana-protocol)) is
  AGPL-3.0 and consumed only through its public SDK boundary
  ([ADR-0003](../adr/0003-pramana-kavach-separation.md),
  [ADR-0015](../adr/0015-pramana-sdk-packaging-and-agpl-posture.md)).
  Alternative identity adapters (deployer-internal, EUDIW, Entra Agent
  ID) satisfy the `CredentialVerifier` Protocol without substrate
  changes.
- Data residency is satisfied by where the deployer runs the stack
  ([ADR-0004](../adr/0004-self-hosted-postgres-on-yotta.md),
  [ADR-0017](../adr/0017-on-prem-deployment-posture.md)). Nothing
   120|  leaves the perimeter.

## Reference

- NIST / NCCoE, *Design Tenets for Agent Identity Management
  Systems*, Cybersecurity Insights blog, 27 October 2026.
- Full crosswalk:
  [docs/compliance/nist-agentic-iam-mapping.md](../compliance/nist-agentic-iam-mapping.md).
- Companion mappings:
  [EU AI Act + eIDAS/EUDIW](../compliance/eu-regulatory-mapping.md);
   130|  [India RBI/SEBI/IRDAI/DPDP](../compliance/india-regulatory-mapping.md).
