"""Add source_type and rename selectors -> config for adapter framework

Revision ID: 003
Revises: 002
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            server_default="html_css",
        ),
    )
    op.alter_column("sources", "selectors", new_column_name="config")


def downgrade() -> None:
    op.alter_column("sources", "config", new_column_name="selectors")
    op.drop_column("sources", "source_type")
