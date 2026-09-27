from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import (
    PartnerCompanyCreate, ProjectPartnerCreate, ResourceAvailabilityCreate,
    ResourceSkillCreate, SkillCreate, SprintCreate,
)
from app.domain.models import (
    PartnerCompany, Project, ProjectPartner, Resource, ResourceAvailability,
    ResourceSkill, Skill, Sprint, normalize_code,
)
from app.application.capacity_service import commit_or_conflict
from app.application.audit_service import record_audit


async def create_partner(session: AsyncSession, payload: PartnerCompanyCreate) -> PartnerCompany:
    item = PartnerCompany(name=payload.name.strip(), name_normalized=normalize_code(payload.name), contact_name=payload.contact_name, contact_email=payload.contact_email, notes=payload.notes)
    session.add(item); await record_audit(session, entity_type="PartnerCompany", entity_id=item.id, action="CREATE", new_values={"name": item.name}); await commit_or_conflict(session, "Partner already exists or violates constraints."); await session.refresh(item); return item

async def list_partners(session: AsyncSession) -> list[PartnerCompany]:
    return list((await session.scalars(select(PartnerCompany).where(PartnerCompany.active.is_(True)).order_by(PartnerCompany.name))).all())

async def deactivate_partner(session: AsyncSession, partner_id: UUID) -> PartnerCompany:
    partner = await session.get(PartnerCompany, partner_id, with_for_update=True)
    if partner is None or not partner.active:
        raise HTTPException(status_code=404, detail="Partner not found.")
    partner.active = False
    partner.version += 1
    await record_audit(session, entity_type="PartnerCompany", entity_id=partner.id, action="DEACTIVATE", old_values={"active": True}, new_values={"active": False})
    await commit_or_conflict(session, "Partner update violates constraints.")
    await session.refresh(partner)
    return partner

async def add_project_partner(session: AsyncSession, project_id: UUID, payload: ProjectPartnerCreate) -> ProjectPartner:
    project = await session.get(Project, project_id)
    partner = await session.get(PartnerCompany, payload.partner_company_id)
    if project is None or not project.active or partner is None or not partner.active:
        raise HTTPException(status_code=404, detail="Project or partner not found.")
    item = ProjectPartner(project_id=project_id, **payload.model_dump())
    session.add(item); await record_audit(session, entity_type="ProjectPartner", entity_id=item.id, action="CREATE", new_values={"project_id": str(project_id), "partner_company_id": str(partner.id)}); await commit_or_conflict(session, "Project partner already exists or violates constraints."); await session.refresh(item); return item

async def list_project_partners(session: AsyncSession, project_id: UUID) -> list[ProjectPartner]:
    return list((await session.scalars(select(ProjectPartner).where(ProjectPartner.project_id == project_id))).all())

async def create_sprint(session: AsyncSession, project_id: UUID, payload: SprintCreate) -> Sprint:
    project = await session.get(Project, project_id)
    if project is None or not project.active: raise HTTPException(status_code=404, detail="Project not found.")
    if payload.end_date < payload.start_date: raise HTTPException(status_code=422, detail="end_date must be on or after start_date.")
    item = Sprint(project_id=project_id, **payload.model_dump())
    session.add(item); await record_audit(session, entity_type="Sprint", entity_id=item.id, action="CREATE", new_values={"project_id": str(project_id), "sprint_number": item.sprint_number}); await commit_or_conflict(session, "Sprint already exists or violates constraints."); await session.refresh(item); return item

async def list_sprints(session: AsyncSession, project_id: UUID) -> list[Sprint]:
    return list((await session.scalars(select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.sprint_number))).all())

async def create_skill(session: AsyncSession, payload: SkillCreate) -> Skill:
    item = Skill(name=payload.name.strip(), name_normalized=normalize_code(payload.name), category=payload.category)
    session.add(item); await record_audit(session, entity_type="Skill", entity_id=item.id, action="CREATE", new_values={"name": item.name}); await commit_or_conflict(session, "Skill already exists or violates constraints."); await session.refresh(item); return item

async def list_skills(session: AsyncSession) -> list[Skill]:
    return list((await session.scalars(select(Skill).where(Skill.active.is_(True)).order_by(Skill.name))).all())

async def add_resource_skill(session: AsyncSession, resource_id: UUID, payload: ResourceSkillCreate) -> ResourceSkill:
    resource = await session.get(Resource, resource_id); skill = await session.get(Skill, payload.skill_id)
    if resource is None or not resource.active or skill is None or not skill.active: raise HTTPException(status_code=404, detail="Resource or skill not found.")
    item = ResourceSkill(resource_id=resource_id, **payload.model_dump())
    session.add(item); await record_audit(session, entity_type="ResourceSkill", entity_id=item.id, action="CREATE", new_values={"resource_id": str(resource_id), "skill_id": str(skill.id), "level": item.level}); await commit_or_conflict(session, "Resource skill already exists or violates constraints."); await session.refresh(item); return item

async def list_resource_skills(session: AsyncSession, resource_id: UUID) -> list[ResourceSkill]:
    return list((await session.scalars(select(ResourceSkill).where(ResourceSkill.resource_id == resource_id))).all())

async def upsert_availability(session: AsyncSession, resource_id: UUID, payload: ResourceAvailabilityCreate) -> ResourceAvailability:
    resource = await session.get(Resource, resource_id)
    if resource is None or not resource.active: raise HTTPException(status_code=404, detail="Resource not found.")
    item = await session.scalar(select(ResourceAvailability).where(ResourceAvailability.resource_id == resource_id, ResourceAvailability.calendar_week_id == payload.calendar_week_id))
    if item is None: item = ResourceAvailability(resource_id=resource_id, **payload.model_dump()); session.add(item)
    else: item.available_percentage = payload.available_percentage; item.reason = payload.reason; item.version += 1
    await record_audit(session, entity_type="ResourceAvailability", entity_id=item.id, action="UPSERT", new_values={"resource_id": str(resource_id), "calendar_week_id": str(item.calendar_week_id), "available_percentage": str(item.available_percentage)}); await commit_or_conflict(session, "Resource availability violates constraints."); await session.refresh(item); return item

async def list_availability(session: AsyncSession, resource_id: UUID) -> list[ResourceAvailability]:
    return list((await session.scalars(select(ResourceAvailability).where(ResourceAvailability.resource_id == resource_id).order_by(ResourceAvailability.calendar_week_id))).all())
