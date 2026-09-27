"""add company to resources

Revision ID: 20260922_0011
Revises: 20260921_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0011"
down_revision: str | Sequence[str] | None = "20260921_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resources", sa.Column("company", sa.String(length=200), nullable=True), schema="resource")


def downgrade() -> None:
    op.drop_column("resources", "company", schema="resource")
