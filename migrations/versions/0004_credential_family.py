"""Add credential-family parent and stored holder token.

Revision ID: 0004_credential_family
Revises: 0003_credentials
Create Date: 2026-10-30

``0003`` creates tables from current metadata, so a fresh upgrade already
has these columns. This revision adds them only when an older database
does not.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_credential_family"
down_revision: str | None = "0003_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("agent_credentials")}
    if "parent_credential_id" not in columns:
        op.add_column(
            "agent_credentials",
            sa.Column("parent_credential_id", sa.String(length=64), nullable=True),
        )
    if "holder_token" not in columns:
        op.add_column("agent_credentials", sa.Column("holder_token", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in sa.inspect(bind).get_columns("agent_credentials")}
    if "holder_token" in columns:
        op.drop_column("agent_credentials", "holder_token")
    if "parent_credential_id" in columns:
        op.drop_column("agent_credentials", "parent_credential_id")
