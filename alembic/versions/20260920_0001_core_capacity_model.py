"""core capacity model

Revision ID: 20260920_0001
Revises: None
Create Date: 2026-09-20
"""

from collections.abc import Sequence
from datetime import date, timedelta
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260920_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("security", "portfolio", "resource", "capacity", "audit")
PRESEEDED_CALENDAR_END_YEAR = 2030


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entra_object_id", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="security",
    )
    op.create_index(
        "ux_users_entra_object_id", "users", ["entra_object_id"], unique=True, schema="security"
    )
    op.create_index("ix_users_email", "users", ["email"], schema="security")

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("code_normalized", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=True),
        sa.Column("business_area", sa.String(length=40), nullable=False),
        sa.Column("project_type", sa.String(length=40), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=40), nullable=False),
        sa.Column("delivery_model", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_end_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_projects_code_not_blank"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_not_blank"),
        sa.CheckConstraint(
            "start_date IS NULL OR target_end_date IS NULL OR target_end_date >= start_date",
            name="ck_projects_target_end_after_start",
        ),
        sa.CheckConstraint(
            "start_date IS NULL OR actual_end_date IS NULL OR actual_end_date >= start_date",
            name="ck_projects_actual_end_after_start",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="portfolio",
    )
    op.create_index(
        "ux_projects_code_normalized",
        "projects",
        ["code_normalized"],
        unique=True,
        schema="portfolio",
    )
    op.create_index(
        "ix_projects_lifecycle_state", "projects", ["lifecycle_state"], schema="portfolio"
    )
    op.create_index("ix_projects_project_type", "projects", ["project_type"], schema="portfolio")
    op.create_index(
        "ix_projects_delivery_model", "projects", ["delivery_model"], schema="portfolio"
    )

    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("discipline", sa.String(length=40), nullable=False),
        sa.Column("role_type", sa.String(length=60), nullable=False),
        sa.Column("specialization", sa.String(length=120), nullable=True),
        sa.Column("seniority", sa.String(length=80), nullable=True),
        sa.Column("default_weekly_capacity", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_resources_name_not_blank"),
        sa.CheckConstraint(
            "default_weekly_capacity >= 0 AND default_weekly_capacity <= 150",
            name="ck_resources_default_weekly_capacity_range",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["security.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="resource",
    )
    op.create_index(
        "ux_resources_user_id", "resources", ["user_id"], unique=True, schema="resource"
    )
    op.create_index("ix_resources_discipline", "resources", ["discipline"], schema="resource")
    op.create_index("ix_resources_role_type", "resources", ["role_type"], schema="resource")

    op.create_table(
        "calendar_weeks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("iso_year", sa.Integer(), nullable=False),
        sa.Column("iso_week", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.CheckConstraint("iso_week >= 1 AND iso_week <= 53", name="ck_calendar_weeks_iso_week"),
        sa.CheckConstraint("end_date >= start_date", name="ck_calendar_weeks_end_after_start"),
        sa.PrimaryKeyConstraint("id"),
        schema="capacity",
    )
    op.create_index(
        "ux_calendar_weeks_iso_year_week",
        "calendar_weeks",
        ["iso_year", "iso_week"],
        unique=True,
        schema="capacity",
    )
    seed_calendar_weeks_until(PRESEEDED_CALENDAR_END_YEAR)

    op.create_table(
        "resource_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_week_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("available_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
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
            "available_percentage >= 0 AND available_percentage <= 150",
            name="ck_resource_availability_percentage_range",
        ),
        sa.ForeignKeyConstraint(["calendar_week_id"], ["capacity.calendar_weeks.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.resources.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="resource",
    )
    op.create_index(
        "ux_resource_availability_resource_week",
        "resource_availability",
        ["resource_id", "calendar_week_id"],
        unique=True,
        schema="resource",
    )

    op.create_table(
        "allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("calendar_week_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocation_type", sa.String(length=40), nullable=False),
        sa.Column("percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
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
            "percentage > 0 AND percentage <= 150", name="ck_allocations_percentage_range"
        ),
        sa.CheckConstraint(
            "allocation_type <> 'PROJECT' OR project_id IS NOT NULL",
            name="ck_allocations_project_required_for_project_type",
        ),
        sa.ForeignKeyConstraint(["calendar_week_id"], ["capacity.calendar_weeks.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["security.users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["portfolio.projects.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["resource.resources.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["security.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="capacity",
    )
    op.create_index(
        "ix_allocations_resource_week",
        "allocations",
        ["resource_id", "calendar_week_id"],
        schema="capacity",
    )
    op.create_index(
        "ix_allocations_project_week",
        "allocations",
        ["project_id", "calendar_week_id"],
        schema="capacity",
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_display_name", sa.String(length=200), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("old_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("request_source", sa.String(length=100), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["security.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="audit",
    )
    op.create_index(
        "ix_audit_events_entity",
        "audit_events",
        ["entity_type", "entity_id", "occurred_at"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_events_actor", "audit_events", ["actor_user_id", "occurred_at"], schema="audit"
    )
    op.create_index(
        "ix_audit_events_correlation_id", "audit_events", ["correlation_id"], schema="audit"
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events", schema="audit")
    op.drop_index("ix_audit_events_actor", table_name="audit_events", schema="audit")
    op.drop_index("ix_audit_events_entity", table_name="audit_events", schema="audit")
    op.drop_table("audit_events", schema="audit")

    op.drop_index("ix_allocations_project_week", table_name="allocations", schema="capacity")
    op.drop_index("ix_allocations_resource_week", table_name="allocations", schema="capacity")
    op.drop_table("allocations", schema="capacity")

    op.drop_index(
        "ux_resource_availability_resource_week",
        table_name="resource_availability",
        schema="resource",
    )
    op.drop_table("resource_availability", schema="resource")

    op.drop_index("ux_calendar_weeks_iso_year_week", table_name="calendar_weeks", schema="capacity")
    op.drop_table("calendar_weeks", schema="capacity")

    op.drop_index("ix_resources_role_type", table_name="resources", schema="resource")
    op.drop_index("ix_resources_discipline", table_name="resources", schema="resource")
    op.drop_index("ux_resources_user_id", table_name="resources", schema="resource")
    op.drop_table("resources", schema="resource")

    op.drop_index("ix_projects_delivery_model", table_name="projects", schema="portfolio")
    op.drop_index("ix_projects_project_type", table_name="projects", schema="portfolio")
    op.drop_index("ix_projects_lifecycle_state", table_name="projects", schema="portfolio")
    op.drop_index("ux_projects_code_normalized", table_name="projects", schema="portfolio")
    op.drop_table("projects", schema="portfolio")

    op.drop_index("ix_users_email", table_name="users", schema="security")
    op.drop_index("ux_users_entra_object_id", table_name="users", schema="security")
    op.drop_table("users", schema="security")

    for schema in reversed(SCHEMAS):
        op.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema}"))


def seed_calendar_weeks_until(end_year: int) -> None:
    rows = []
    cursor = date(2026, 1, 1)
    cursor = cursor - timedelta(days=cursor.weekday())
    end = date.fromisocalendar(end_year, date(end_year, 12, 28).isocalendar().week, 1)

    while cursor <= end:
        iso_year, iso_week, _ = cursor.isocalendar()
        rows.append(
            {
                "id": uuid4(),
                "iso_year": iso_year,
                "iso_week": iso_week,
                "start_date": cursor,
                "end_date": cursor + timedelta(days=6),
            }
        )
        cursor += timedelta(weeks=1)

    calendar_weeks = sa.table(
        "calendar_weeks",
        sa.column("id"),
        sa.column("iso_year"),
        sa.column("iso_week"),
        sa.column("start_date"),
        sa.column("end_date"),
        schema="capacity",
    )
    op.bulk_insert(calendar_weeks, rows)
