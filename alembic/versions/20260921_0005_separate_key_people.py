"""separate key people from allocation resources

Revision ID: 20260921_0005
Revises: 20260921_0004
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0005"
down_revision: str | Sequence[str] | None = "20260921_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "key_people",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        schema="portfolio",
    )
    op.create_index("ix_key_people_name", "key_people", ["name"], schema="portfolio")
    op.execute(
        """
        INSERT INTO portfolio.key_people (id, name, email, active, created_at, updated_at, version)
        SELECT gen_random_uuid(), r.name, r.email, true, now(), now(), 1
        FROM resource.resources r
        WHERE r.id IN (
          SELECT resource_id FROM portfolio.project_stakeholders
          UNION
          SELECT resource_id FROM portfolio.key_people_directory
        )
        """
    )
    op.add_column(
        "project_stakeholders",
        sa.Column("key_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="portfolio",
    )
    op.add_column(
        "key_people_directory",
        sa.Column("key_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="portfolio",
    )
    op.execute(
        """
        UPDATE portfolio.project_stakeholders ps
        SET key_person_id = kp.id
        FROM portfolio.key_people kp, resource.resources r
        WHERE ps.resource_id = r.id AND kp.name = r.name
          AND COALESCE(kp.email, '') = COALESCE(r.email, '')
        """
    )
    op.execute(
        """
        UPDATE portfolio.key_people_directory kd
        SET key_person_id = kp.id
        FROM portfolio.key_people kp, resource.resources r
        WHERE kd.resource_id = r.id AND kp.name = r.name
          AND COALESCE(kp.email, '') = COALESCE(r.email, '')
        """
    )
    op.alter_column("project_stakeholders", "key_person_id", nullable=False, schema="portfolio")
    op.alter_column("key_people_directory", "key_person_id", nullable=False, schema="portfolio")
    op.drop_index(
        "ux_project_stakeholders_project_resource_role_active",
        table_name="project_stakeholders",
        schema="portfolio",
    )
    op.drop_index(
        "ux_key_people_directory_role_resource",
        table_name="key_people_directory",
        schema="portfolio",
    )
    op.drop_constraint(
        "fk_project_stakeholders_resource_id_resources", "project_stakeholders", schema="portfolio", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_key_people_directory_resource_id_resources", "key_people_directory", schema="portfolio", type_="foreignkey"
    )
    op.drop_column("project_stakeholders", "resource_id", schema="portfolio")
    op.drop_column("key_people_directory", "resource_id", schema="portfolio")
    op.create_foreign_key(
        "project_stakeholders_key_person_id_fkey",
        "project_stakeholders",
        "key_people",
        ["key_person_id"],
        ["id"],
        source_schema="portfolio",
        referent_schema="portfolio",
    )
    op.create_foreign_key(
        "key_people_directory_key_person_id_fkey",
        "key_people_directory",
        "key_people",
        ["key_person_id"],
        ["id"],
        source_schema="portfolio",
        referent_schema="portfolio",
    )
    op.create_index(
        "ux_project_stakeholders_project_person_role_active",
        "project_stakeholders",
        ["project_id", "key_person_id", "role"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        schema="portfolio",
    )
    op.create_index(
        "ux_key_people_directory_role_person",
        "key_people_directory",
        ["role", "key_person_id"],
        unique=True,
        schema="portfolio",
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for this data migration.")
