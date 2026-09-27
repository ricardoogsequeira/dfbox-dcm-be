"""add company and business area to key people

Revision ID: 20260922_0012
Revises: 20260922_0011
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260922_0012"
down_revision: str | Sequence[str] | None = "20260922_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("key_people", sa.Column("company", sa.String(length=200), nullable=True), schema="portfolio")
    op.add_column("key_people", sa.Column("business_area", sa.String(length=40), nullable=True), schema="portfolio")


def downgrade() -> None:
    op.drop_column("key_people", "business_area", schema="portfolio")
    op.drop_column("key_people", "company", schema="portfolio")
