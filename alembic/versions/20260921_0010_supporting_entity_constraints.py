"""add constraints and audit foreign keys to supporting entities

Revision ID: 20260921_0010
Revises: 20260921_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260921_0010"
down_revision: str | Sequence[str] | None = "20260921_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table, schema in (("partner_companies", "portfolio"), ("project_partners", "portfolio"), ("sprints", "portfolio"), ("skills", "resource"), ("resource_skills", "resource")):
        op.create_foreign_key(f"fk_{table}_created_by_user", table, "users", ["created_by_user_id"], ["id"], source_schema=schema, referent_schema="security")
        op.create_foreign_key(f"fk_{table}_updated_by_user", table, "users", ["updated_by_user_id"], ["id"], source_schema=schema, referent_schema="security")
    op.create_check_constraint("ck_project_partners_contribution_percentage", "project_partners", "contribution_percentage IS NULL OR (contribution_percentage >= 0 AND contribution_percentage <= 100)", schema="portfolio")
    op.create_check_constraint("ck_sprints_end_after_start", "sprints", "end_date >= start_date", schema="portfolio")
    op.create_check_constraint("ck_resource_skills_level", "resource_skills", "level >= 1 AND level <= 5", schema="resource")


def downgrade() -> None:
    op.drop_constraint("ck_resource_skills_level", "resource_skills", schema="resource", type_="check")
    op.drop_constraint("ck_sprints_end_after_start", "sprints", schema="portfolio", type_="check")
    op.drop_constraint("ck_project_partners_contribution_percentage", "project_partners", schema="portfolio", type_="check")
    for table, schema in (("resource_skills", "resource"), ("skills", "resource"), ("sprints", "portfolio"), ("project_partners", "portfolio"), ("partner_companies", "portfolio")):
        op.drop_constraint(f"fk_{table}_updated_by_user", table, schema=schema, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_created_by_user", table, schema=schema, type_="foreignkey")
