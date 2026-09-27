"""add project key people

Revision ID: 20260921_0003
Revises: 20260921_0002
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0003"
down_revision: str | Sequence[str] | None = "20260921_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_stakeholders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["portfolio.projects.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.resources.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        schema="portfolio",
    )
    op.create_index(
        "ux_project_stakeholders_project_role_active",
        "project_stakeholders",
        ["project_id", "role"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        schema="portfolio",
    )
    op.create_index(
        "ux_project_stakeholders_project_resource_role_active",
        "project_stakeholders",
        ["project_id", "resource_id", "role"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_index(
        "ux_project_stakeholders_project_resource_role_active",
        table_name="project_stakeholders",
        schema="portfolio",
    )
    op.drop_index(
        "ux_project_stakeholders_project_role_active",
        table_name="project_stakeholders",
        schema="portfolio",
    )
    op.drop_table("project_stakeholders", schema="portfolio")
