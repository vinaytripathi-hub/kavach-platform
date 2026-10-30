"""Add session credentials, revocation, and the signal outbox.

Revision ID: 0003_credentials
Revises: 0002_mandates
Create Date: 2026-10-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import kavach.capabilities.audit._internal.models
import kavach.query.projections._tables  # noqa: F401
from kavach.capabilities.storage import Base

revision: str = "0003_credentials"
down_revision: str | None = "0002_mandates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    for table in (
        "signal_outbox",
        "credential_revocations",
        "agent_revocations",
        "agent_credentials",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
