# Changelog

All notable changes to Kavach Platform are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Kavach Platform versioning will follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once the first stable release lands.

## [Unreleased]

### Added — W01-S02 Block A (this commit)

- LICENSE (proprietary, all rights reserved) with explicit
  "No License Granted by Mere Possession" clause.
- NOTICE attributing Pramana Protocol (AGPL-3.0) as a foundational
  dependency consumed solely via the public SDK boundary, with
  explicit statement that Kavach Platform contains no Pramana source
  code.
- README oriented to internal team and diligence reviewers.
- CONTRIBUTING gating contributions to authorized Aurvia Global
  personnel with IP-assignment-clause employment / contractor
  agreements.
- SECURITY vulnerability disclosure policy with email-first reporting
  and PGP key reference.
- CODE_OF_CONDUCT (Contributor Covenant v2.1).
- .gitignore covering Python, virtual environments, coverage, IDE
  artifacts, secrets, macOS metadata, log files, and macOS Finder
  duplicates.
- .gitattributes for line-ending normalization and GitHub language
  stat exclusions.

### Planned — subsequent W01-S02 blocks

- **Block B**: project skeleton (`kavach/` package layout),
  `pyproject.toml`, pre-commit configuration, GitHub Actions CI
  workflows, dev-setup script.
- **Block C**: foundational ADRs (0001-0006) — three-layer
  architecture, build order, Pramana-Kavach separation, Postgres on
  Yotta, "Accountability" positioning, TDD discipline.
- **Block D**: advanced architectural ADRs (0007-0014) — modular
  capability architecture, events as primary output, projections,
  event schema versioning, sub-product extraction posture, decision
  evidence and reasoning, multimodal data sufficiency,
  multidimensional trust.
- **Block E**: events infrastructure scaffolding, IP Provenance
  Document, CLA templates, Engineering Handbook, smoke tests, final
  verification, push to origin.
