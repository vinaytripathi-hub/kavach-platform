"""Credential-family membership (ADR-0020).

A session credential and the refresh tokens that rotate it are one family,
linked by ``parent_credential_id``. Revoking any member revokes the family.
Retiring a refresh token because it was rotated does not.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import AgentCredentialRow, CredentialRevocationRow

ROTATION_REASON = "rotated"


def family_ids_from_rows(rows: list[AgentCredentialRow], credential_id: str) -> set[str]:
    """Return ``credential_id`` and every credential that shares its root."""
    by_id = {row.credential_id: row for row in rows}
    root = credential_id
    seen: set[str] = set()
    while root not in seen:
        seen.add(root)
        row = by_id.get(root)
        parent = row.parent_credential_id if row is not None else None
        if not parent:
            break
        root = parent
    children: dict[str, list[str]] = {}
    for row in rows:
        if row.parent_credential_id:
            children.setdefault(row.parent_credential_id, []).append(row.credential_id)
    family: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        if current in family:
            continue
        family.add(current)
        stack.extend(children.get(current, []))
    return family


async def family_credential_ids(
    session: AsyncSession, tenant_id: str, credential_id: str
) -> set[str]:
    """Load the family that contains ``credential_id``."""
    start = await session.get(AgentCredentialRow, (tenant_id, credential_id))
    if start is None:
        return {credential_id}
    result = await session.execute(
        select(AgentCredentialRow).where(
            AgentCredentialRow.tenant_id == tenant_id,
            AgentCredentialRow.agent_id == start.agent_id,
        )
    )
    return family_ids_from_rows(list(result.scalars().all()), credential_id)


async def family_operator_revoked(
    session: AsyncSession, tenant_id: str, credential_id: str
) -> bool:
    """True when any family member was revoked by an operator, not by rotation."""
    for member_id in await family_credential_ids(session, tenant_id, credential_id):
        hit = await session.get(CredentialRevocationRow, (tenant_id, member_id))
        if hit is not None and hit.reason != ROTATION_REASON:
            return True
    return False


__all__ = [
    "ROTATION_REASON",
    "family_credential_ids",
    "family_ids_from_rows",
    "family_operator_revoked",
]
