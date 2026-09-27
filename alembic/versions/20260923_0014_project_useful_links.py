"""add useful project links

Revision ID: 20260923_0014
Revises: 20260922_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260923_0014"
down_revision: str | Sequence[str] | None = "20260922_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    for name in ("edpx_card_url", "jira_url", "confluence_url", "figma_url"):
        op.add_column("projects", sa.Column(name, sa.String(length=2000), nullable=True), schema="portfolio")


def downgrade() -> None:
    for name in ("figma_url", "confluence_url", "jira_url", "edpx_card_url"):
        op.drop_column("projects", name, schema="portfolio")
