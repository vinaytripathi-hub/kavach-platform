"""Kavach Platform — Agent Accountability for Indian BFSI.

This is the proprietary commercial layer built atop the Pramana Protocol
(AGPL-3.0 open-source substrate). See LICENSE and NOTICE at the repository
root, and docs/ip-provenance.md (added in W01-S02 Block E) for the legal
and architectural analysis of the IP separation.

Package layout (target; populated across W01-S02 through W01-S0N):

- kavach.events       Event taxonomy, bus, persistence (substrate output)
- kavach.capabilities Modular capabilities (audit, policy, enrichment, etc.)
- kavach.composition  Wiring of capabilities into a usable substrate
- kavach.query        Read-side projections over the event stream
- kavach.usecases     Per-use-case configurations
- kavach.experiences  UI surfaces (Week 9+)

See docs/adr/ for the foundational architectural decisions.
"""

__version__ = "0.0.1"
