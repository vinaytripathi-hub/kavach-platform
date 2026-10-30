"""RFC 7807 problem type URIs (ADR-0020, ADR-0016).

``code`` stays the stable machine discriminator. ``type`` is a URI so
clients can branch without parsing free text. Unknown codes fall back
to ``about:blank`` rather than failing the response.
"""

from __future__ import annotations

PROBLEM_TYPE_BASE = "https://kavach.invalid/problems"

PROBLEM_TYPES: dict[str, str] = {
    "unauthorized": f"{PROBLEM_TYPE_BASE}/unauthorized",
    "forbidden": f"{PROBLEM_TYPE_BASE}/forbidden",
    "not_found": f"{PROBLEM_TYPE_BASE}/not_found",
    "validation_error": f"{PROBLEM_TYPE_BASE}/validation-error",
    "step_up_already_resolved": f"{PROBLEM_TYPE_BASE}/step-up-already-resolved",
    "mandate_already_exists": f"{PROBLEM_TYPE_BASE}/mandate-already-exists",
    "already_revoked": f"{PROBLEM_TYPE_BASE}/already-revoked",
    "internal_error": f"{PROBLEM_TYPE_BASE}/internal-error",
    "credential_expired": f"{PROBLEM_TYPE_BASE}/credential-expired",
    "credential_not_yet_valid": f"{PROBLEM_TYPE_BASE}/credential-not-yet-valid",
    "agent_revoked": f"{PROBLEM_TYPE_BASE}/agent-revoked",
    "credential_revoked": f"{PROBLEM_TYPE_BASE}/credential-revoked",
}


def problem_type(code: str) -> str:
    """Return the problem type URI for ``code``."""
    return PROBLEM_TYPES.get(code, "about:blank")
