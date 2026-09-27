"""add partners, sprints and skills

Revision ID: 20260921_0009
Revises: 20260921_0008
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260921_0009"
down_revision: str | Sequence[str] | None = "20260921_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
    ]

def upgrade() -> None:
    op.create_table("partner_companies", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("name_normalized", sa.String(200), nullable=False), sa.Column("contact_name", sa.String(200)), sa.Column("contact_email", sa.String(320)), sa.Column("notes", sa.String(2000)), sa.Column("active", sa.Boolean(), nullable=False), *_audit_columns(), schema="portfolio")
    op.create_index("ux_partner_companies_name_normalized", "partner_companies", ["name_normalized"], unique=True, schema="portfolio")
    op.create_table("project_partners", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("partner_company_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("contribution_description", sa.String(2000)), sa.Column("contribution_percentage", sa.Numeric(5, 2)), *_audit_columns(), sa.ForeignKeyConstraint(["project_id"], ["portfolio.projects.id"]), sa.ForeignKeyConstraint(["partner_company_id"], ["portfolio.partner_companies.id"]), schema="portfolio")
    op.create_index("ux_project_partners_project_partner", "project_partners", ["project_id", "partner_company_id"], unique=True, schema="portfolio")
    op.create_table("sprints", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("sprint_number", sa.Integer(), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("start_date", sa.Date(), nullable=False), sa.Column("end_date", sa.Date(), nullable=False), sa.Column("goal", sa.String(2000)), *_audit_columns(), sa.ForeignKeyConstraint(["project_id"], ["portfolio.projects.id"]), schema="portfolio")
    op.create_index("ux_sprints_project_number", "sprints", ["project_id", "sprint_number"], unique=True, schema="portfolio")
    op.create_table("skills", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("name_normalized", sa.String(120), nullable=False), sa.Column("category", sa.String(80)), sa.Column("active", sa.Boolean(), nullable=False), *_audit_columns(), schema="resource")
    op.create_index("ux_skills_name_normalized", "skills", ["name_normalized"], unique=True, schema="resource")
    op.create_table("resource_skills", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("skill_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("level", sa.Integer(), nullable=False), *_audit_columns(), sa.ForeignKeyConstraint(["resource_id"], ["resource.resources.id"]), sa.ForeignKeyConstraint(["skill_id"], ["resource.skills.id"]), schema="resource")
    op.create_index("ux_resource_skills_resource_skill", "resource_skills", ["resource_id", "skill_id"], unique=True, schema="resource")

def downgrade() -> None:
    op.drop_index("ux_resource_skills_resource_skill", table_name="resource_skills", schema="resource")
    op.drop_table("resource_skills", schema="resource")
    op.drop_index("ux_skills_name_normalized", table_name="skills", schema="resource")
    op.drop_table("skills", schema="resource")
    op.drop_index("ux_sprints_project_number", table_name="sprints", schema="portfolio")
    op.drop_table("sprints", schema="portfolio")
    op.drop_index("ux_project_partners_project_partner", table_name="project_partners", schema="portfolio")
    op.drop_table("project_partners", schema="portfolio")
    op.drop_index("ux_partner_companies_name_normalized", table_name="partner_companies", schema="portfolio")
    op.drop_table("partner_companies", schema="portfolio")
