"""add project dependencies

Revision ID: 20260921_0002
Revises: 20260920_0001
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260921_0002"
down_revision: str | Sequence[str] | None = "20260920_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("title_normalized", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("resolved_date", sa.Date(), nullable=True),
        sa.Column("impact_level", sa.String(length=20), nullable=False),
        sa.Column("mitigation_plan", sa.String(length=2000), nullable=True),
        sa.Column("external_reference", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name="ck_project_dependencies_title_not_blank"
        ),
        sa.CheckConstraint(
            "length(trim(description)) > 0",
            name="ck_project_dependencies_description_not_blank",
        ),
        sa.CheckConstraint(
            "target_date >= start_date", name="ck_project_dependencies_target_after_start"
        ),
        sa.CheckConstraint(
            "(status = 'RESOLVED' AND resolved_date IS NOT NULL AND resolved_date >= start_date) "
            "OR (status <> 'RESOLVED' AND resolved_date IS NULL)",
            name="ck_project_dependencies_resolved_state",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["portfolio.projects.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        schema="portfolio",
    )
    op.create_index(
        "ux_project_dependencies_project_title",
        "project_dependencies",
        ["project_id", "title_normalized"],
        unique=True,
        schema="portfolio",
    )
    op.create_index(
        "ix_project_dependencies_project_status",
        "project_dependencies",
        ["project_id", "status"],
        schema="portfolio",
    )
    op.create_index(
        "ix_project_dependencies_impact_status",
        "project_dependencies",
        ["impact_level", "status"],
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_dependencies_impact_status",
        table_name="project_dependencies",
        schema="portfolio",
    )
    op.drop_index(
        "ix_project_dependencies_project_status",
        table_name="project_dependencies",
        schema="portfolio",
    )
    op.drop_index(
        "ux_project_dependencies_project_title",
        table_name="project_dependencies",
        schema="portfolio",
    )
    op.drop_table("project_dependencies", schema="portfolio")
