"""add dependency owner reference

Revision ID: 20260921_0008
Revises: 20260921_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0008"
down_revision: str | Sequence[str] | None = "20260921_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_dependencies",
        sa.Column("owner_key_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="portfolio",
    )
    op.create_foreign_key(
        "fk_project_dependencies_owner_key_person",
        "project_dependencies",
        "key_people",
        ["owner_key_person_id"],
        ["id"],
        source_schema="portfolio",
        referent_schema="portfolio",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_project_dependencies_owner_key_person",
        "project_dependencies",
        schema="portfolio",
        type_="foreignkey",
    )
    op.drop_column("project_dependencies", "owner_key_person_id", schema="portfolio")
