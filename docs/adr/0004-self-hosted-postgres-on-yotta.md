# ADR-0004 — Self-hosted Postgres 16 on Yotta Yntraa for data residency

**Status:** Accepted
**Date:** 2026-05-24

## Context

Kavach Platform stores BFSI-regulated data:

- Agent identity and credential records
- Audit trails (hash-chained, tamper-evident)
- Policy decisions and their evidence
- Trust assessments and behavioral baselines
- Use-case-specific data (KYC artifacts, credit decisions,
  trading event records)

This data is subject to **Indian regulatory data-residency requirements**
under multiple overlapping frameworks:

- **RBI Guidelines on Storage of Payment System Data** (2018) — all
  data related to payment transactions in India must be stored
  exclusively in India.
- **DPDP Act 2023** (Digital Personal Data Protection Act) — defines
  the rights and obligations around personal data; while not strictly
  a data-localization law in the way RBI's payment guidelines are,
  it constrains cross-border transfers.
- **SEBI and IRDAI specific guidelines** for trading and insurance
  agent data, which our use cases will exercise.
- **Customer contracts** — BFSI partners typically require contractual
  data-residency commitments that exceed legal minimums, often
  specifying named Indian data centers.

Hyperscaler cloud (AWS Mumbai, Azure Central India, GCP Mumbai) does
provide India-region storage, but BFSI partners frequently express
preference for sovereign Indian data center providers — both for
regulatory comfort and for political stability across multi-decade
contracts.

Postgres specifically: we need a relational database with strong
transactional guarantees (audit chain integrity, decision atomicity),
mature async drivers (asyncpg, psycopg3), and well-understood operational
characteristics. Newer entrants (CockroachDB, YugabyteDB) are interesting
but unnecessary at our scale and add complexity.

## Decision

**Production data store: self-hosted Postgres 16 on Yotta Yntraa (the
Yotta Infrastructure cloud), with all production tenants in Indian data
centers.**

Specifically:

- **Database engine:** PostgreSQL 16 (mature, current LTS-style,
  matches CI integration-test target). Upgrade cadence: review
  Postgres major versions yearly; upgrade with a one-major-version-lag
  policy to avoid bleeding-edge surprises.
- **Hosting:** Yotta Yntraa, India-region (Navi Mumbai primary, with
  a secondary region for DR once warranted). Yotta is an Adani Group
  sovereign Indian infrastructure provider with explicit BFSI
  compliance posture.
- **Configuration:** self-hosted (we manage the Postgres process), not
  managed (we do not use Yotta's managed-Postgres offering, when and
  if available). Reason: explicit operational control over backup
  cadence, replication topology, point-in-time recovery, and audit-log
  archival is part of the BFSI compliance evidence story. Managed
  Postgres abstracts decisions we need to be able to demonstrate.
- **Development:** local Postgres 16 via Docker for development;
  CI uses `postgres:16-alpine` service container (already configured in
  `.github/workflows/ci.yml` per Block B.3).
- **Async access:** SQLAlchemy 2.x with `asyncio` extras, `asyncpg`
  as the primary driver, `psycopg3` (binary) for synchronous helpers
  where needed.

## Consequences

**Positive:**

- Data-residency compliance is unambiguous. The data physically lives
  in India, in a named provider's named facility. This satisfies the
  strict reading of RBI guidance and gives BFSI partners contractual
  confidence.
- We retain operational control over Postgres configuration. Backup
  encryption keys, replication setup, audit log retention,
  point-in-time recovery windows — all explicit, all auditable.
- Cost is predictable. Self-hosted on dedicated infrastructure costs
  scale linearly with capacity, not multiplicatively with managed-
  service convenience features.
- We can demonstrate sovereign-Indian-infrastructure to BFSI partners
  who care about that distinction. This is a non-trivial sales asset
  vs. competitors who run on hyperscaler India regions.
- Postgres 16 is mature, well-understood, and has the operational
  ecosystem (monitoring, backup tools, replication frameworks) we need.

**Negative:**

- Operational burden. We are responsible for Postgres upgrades, kernel
  tuning, backup integrity, replication health, monitoring. This is
  more work than a managed service. Mitigation: in W02–W03 we
  establish operational runbooks, automated backup verification, and
  monitoring before any production data lands.
- Single-region until DR is established. The first BFSI pilot will
  run from a single Yotta region; multi-region DR setup is planned
  for after the first pilot proves the architecture. Acceptable risk
  for pre-revenue phase; not acceptable at scale.
- Yotta-specific operational knowledge becomes an ops dependency.
  Mitigation: avoid Yotta-specific Postgres extensions or features;
  treat Yotta as commodity Linux + commodity Postgres so that
  re-hosting elsewhere is mechanical if needed later.

## Alternatives Considered

- **AWS RDS Postgres in Mumbai region.** Managed Postgres on AWS
  Mumbai is technically compliant with data residency for most reads
  of RBI rules. Rejected because some BFSI partners are skeptical of
  hyperscaler sovereignty claims and prefer named-Indian-provider
  contracts; because AWS service-level Postgres tuning is restricted;
  and because pricing scales unpredictably with usage. AWS may be
  the right choice for non-BFSI Aurvia products in the future, but
  not for Kavach's primary store.
- **Azure Database for PostgreSQL Flexible Server in Central India.**
  Same considerations as AWS RDS. Rejected for the same reasons.
- **Yotta managed-Postgres offering** (if/when Yotta launches a
  managed-Postgres product, which they may have announced by the
  time this ADR is read). Rejected because we want explicit
  operational control over Postgres configuration; revisit if the
  managed offering matures and exposes the configuration knobs we
  need.
- **MongoDB or other document stores.** Audit chains, policy
  decisions with referential integrity, and transactional payments
  data benefit substantially from a relational model. Rejected.
- **CockroachDB or YugabyteDB.** Distributed SQL stores with stronger
  multi-region guarantees than vanilla Postgres. Rejected at current
  scale — they add operational complexity without solving a problem
  we have today. Revisit if multi-region active-active becomes
  necessary.
- **Hyperscaler-managed Postgres on an Indian region with an
  encrypted file system + customer-managed keys (KMS) for stronger
  sovereignty claims.** Considered briefly. Rejected because partner
  sales conversations are simpler when the answer to "where is the
  data?" is "in a sovereign Indian provider's data center" rather
  than "encrypted in a hyperscaler's data center with our key."

## References

- ADR-0001 — Three-layer architecture
- `.github/workflows/ci.yml` — integration test job uses
  `postgres:16-alpine` service container, matching production target
- `pyproject.toml` dependencies — `sqlalchemy[asyncio]`, `asyncpg`,
  `psycopg[binary]`, `alembic` already declared in W01-S02 Block B.2
- Reserve Bank of India, "Storage of Payment System Data" (2018):
  https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11244
- Digital Personal Data Protection Act, 2023
