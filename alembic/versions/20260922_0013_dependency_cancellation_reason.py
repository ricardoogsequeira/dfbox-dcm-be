"""add dependency cancellation reason

Revision ID: 20260922_0013
Revises: 20260922_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260922_0013"
down_revision: str | Sequence[str] | None = "20260922_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "project_dependencies",
        sa.Column("cancellation_reason", sa.String(length=2000), nullable=True),
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_column("project_dependencies", "cancellation_reason", schema="portfolio")
