# Contributing to Kavach Platform

This is a **proprietary repository**. External contributions are not
accepted.

## For Aurvia Global team members

All contributors must:

1. Have explicit written authorization from Vinay Tripathi (founder
   and CTO).
2. Have an Employment Agreement and/or Contractor Agreement with
   Aurvia Global that includes IP-assignment clauses naming Aurvia
   Global as the assignee of all work product produced in connection
   with Kavach Platform.
3. Configure Git with their authorized identity (matching the email
   on their employment / contractor agreement) and a GPG signing key
   registered to the same email on GitHub.
4. Follow the engineering discipline documented in
   `docs/engineering-handbook.md` (added in a subsequent W01-S02
   block). The handbook will codify TDD, code review, branching,
   commit conventions, and observability discipline.

## For Pramana contributors (different repository)

Contributions to **Pramana Protocol** (the open-source AGPL-3.0
substrate) follow a separate process documented at:
- https://github.com/vinaysflow/pramana-protocol/blob/main/CONTRIBUTING.md

Pramana external contributions require a signed Contributor License
Agreement (CLA). The CLA templates are maintained in `docs/cla/` of
this repository (added in a subsequent W01-S02 block) for centralized
legal document management, since Aurvia Global owns both Pramana and
Kavach.

## Commit and branch conventions

Detailed conventions live in `docs/engineering-handbook.md`. Summary:

- `main` is protected; only Vinay (during the solo phase) merges to
  main.
- Feature branches: `feature/<short-description>`
- Spike branches: `spike/<topic>` — exempt from full TDD enforcement
  but cannot merge to main without rewrite as proper TDD work.
- Bug fix branches: `fix/<short-description>`
- Every commit on main MUST be GPG-signed.
- Commit messages: imperative present tense, ≤72 characters in
  subject; body explains *why*.
- `Co-authored-by:` trailers are NOT used. Sole-authorship is the
  discipline.

## Reporting security issues

Security issues in Kavach Platform: **vinay@aurviaglobal.com**.

Do NOT open public issues for security findings. (This is a private
repository, but issue visibility to all collaborators warrants the
same email-first discipline.)
