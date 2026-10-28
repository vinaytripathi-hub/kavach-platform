"""Add mandate, anomaly, egress, and notification tables.

Revision ID: 0002_mandates
Revises: 0001_initial
Create Date: 2026-10-27
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import kavach.capabilities.audit._internal.models
import kavach.query.projections._tables  # noqa: F401
from kavach.capabilities.storage import Base

revision: str = "0002_mandates"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    for table in (
        "notify_channels",
        "egress_channels",
        "proj_agent_anomaly_current",
        "proj_mandate_current",
        "mandate_revocations",
        "mandates",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
