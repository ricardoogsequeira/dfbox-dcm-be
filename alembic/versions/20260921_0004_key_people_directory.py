"""add configurable key people directory

Revision ID: 20260921_0004
Revises: 20260921_0003
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0004"
down_revision: str | Sequence[str] | None = "20260921_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "key_people_directory",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.resources.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        schema="portfolio",
    )
    op.create_index(
        "ux_key_people_directory_role_resource",
        "key_people_directory",
        ["role", "resource_id"],
        unique=True,
        schema="portfolio",
    )
    op.create_index(
        "ix_key_people_directory_role",
        "key_people_directory",
        ["role"],
        schema="portfolio",
    )


def downgrade() -> None:
    op.drop_index("ix_key_people_directory_role", table_name="key_people_directory", schema="portfolio")
    op.drop_index("ux_key_people_directory_role_resource", table_name="key_people_directory", schema="portfolio")
    op.drop_table("key_people_directory", schema="portfolio")
