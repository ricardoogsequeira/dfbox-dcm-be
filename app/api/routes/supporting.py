from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.schemas.capacity import PartnerCompanyCreate, PartnerCompanyRead, ProjectPartnerCreate, ProjectPartnerRead, ResourceAvailabilityCreate, ResourceAvailabilityRead, ResourceSkillCreate, ResourceSkillRead, SkillCreate, SkillRead, SprintCreate, SprintRead
from app.application.supporting_service import add_project_partner, add_resource_skill, create_partner, create_skill, create_sprint, deactivate_partner, list_availability, list_partners, list_project_partners, list_resource_skills, list_skills, list_sprints, upsert_availability
from app.core.database import get_db_session

router = APIRouter(tags=["supporting-domain"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]

@router.get("/partners", response_model=list[PartnerCompanyRead])
async def partners(session: SessionDependency): return await list_partners(session)

@router.post("/partners", response_model=PartnerCompanyRead, status_code=status.HTTP_201_CREATED)
async def create_partner_endpoint(payload: PartnerCompanyCreate, session: SessionDependency): return await create_partner(session, payload)

@router.delete("/partners/{partner_id}", response_model=PartnerCompanyRead)
async def deactivate_partner_endpoint(partner_id: UUID, session: SessionDependency): return await deactivate_partner(session, partner_id)

@router.get("/projects/{project_id}/partners", response_model=list[ProjectPartnerRead])
async def project_partners(project_id: UUID, session: SessionDependency): return await list_project_partners(session, project_id)

@router.post("/projects/{project_id}/partners", response_model=ProjectPartnerRead, status_code=status.HTTP_201_CREATED)
async def add_project_partner_endpoint(project_id: UUID, payload: ProjectPartnerCreate, session: SessionDependency): return await add_project_partner(session, project_id, payload)

@router.get("/projects/{project_id}/sprints", response_model=list[SprintRead])
async def sprints(project_id: UUID, session: SessionDependency): return await list_sprints(session, project_id)

@router.post("/projects/{project_id}/sprints", response_model=SprintRead, status_code=status.HTTP_201_CREATED)
async def create_sprint_endpoint(project_id: UUID, payload: SprintCreate, session: SessionDependency): return await create_sprint(session, project_id, payload)

@router.get("/skills", response_model=list[SkillRead])
async def skills(session: SessionDependency): return await list_skills(session)

@router.post("/skills", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
async def create_skill_endpoint(payload: SkillCreate, session: SessionDependency): return await create_skill(session, payload)

@router.get("/resources/{resource_id}/skills", response_model=list[ResourceSkillRead])
async def resource_skills(resource_id: UUID, session: SessionDependency): return await list_resource_skills(session, resource_id)

@router.post("/resources/{resource_id}/skills", response_model=ResourceSkillRead, status_code=status.HTTP_201_CREATED)
async def add_resource_skill_endpoint(resource_id: UUID, payload: ResourceSkillCreate, session: SessionDependency): return await add_resource_skill(session, resource_id, payload)

@router.get("/resources/{resource_id}/availability", response_model=list[ResourceAvailabilityRead])
async def resource_availability(resource_id: UUID, session: SessionDependency): return await list_availability(session, resource_id)

@router.put("/resources/{resource_id}/availability", response_model=ResourceAvailabilityRead)
async def upsert_resource_availability(resource_id: UUID, payload: ResourceAvailabilityCreate, session: SessionDependency): return await upsert_availability(session, resource_id, payload)
