"""allow reusing inactive key people directory assignments

Revision ID: 20260921_0006
Revises: 20260921_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0006"
down_revision: str | Sequence[str] | None = "20260921_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ux_key_people_directory_role_person",
        table_name="key_people_directory",
        schema="portfolio",
    )
    op.create_index(
        "ux_key_people_directory_role_person",
        "key_people_directory",
        ["role", "key_person_id"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_index(
        "ux_key_people_directory_role_person",
        table_name="key_people_directory",
        schema="portfolio",
    )
    op.create_index(
        "ux_key_people_directory_role_person",
        "key_people_directory",
        ["role", "key_person_id"],
        unique=True,
        schema="portfolio",
    )
