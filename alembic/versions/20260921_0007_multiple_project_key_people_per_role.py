"""allow multiple key people per project role

Revision ID: 20260921_0007
Revises: 20260921_0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260921_0007"
down_revision: str | Sequence[str] | None = "20260921_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ux_project_stakeholders_project_role_active",
        table_name="project_stakeholders",
        schema="portfolio",
    )


def downgrade() -> None:
    op.create_index(
        "ux_project_stakeholders_project_role_active",
        "project_stakeholders",
        ["project_id", "role"],
        unique=True,
        postgresql_where="active = true",
        schema="portfolio",
    )
