from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import KeyPersonCreate, KeyPersonRead, KeyPersonUpdate, KeyPeopleDirectoryRead, KeyPeopleUpdate
from app.application.capacity_service import create_key_person, deactivate_key_person, list_key_people, list_key_people_directory, replace_key_people_directory, update_key_person
from app.core.concurrency import etag_for, version_from_if_match
from uuid import UUID
from app.core.database import get_db_session

router = APIRouter(prefix="/settings", tags=["settings"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]


def directory_read(entry) -> KeyPeopleDirectoryRead:
    return KeyPeopleDirectoryRead(
        id=entry.id,
        role=entry.role,
        key_person_id=entry.key_person_id,
        person_name=entry.key_person.name,
        person_email=entry.key_person.email,
        active=entry.active,
        version=entry.version,
    )


@router.get("/key-people", response_model=list[KeyPeopleDirectoryRead])
async def list_key_people_endpoint(session: SessionDependency) -> list[KeyPeopleDirectoryRead]:
    entries = await list_key_people_directory(session)
    return [directory_read(entry) for entry in entries]


@router.put("/key-people", response_model=list[KeyPeopleDirectoryRead])
async def replace_key_people_endpoint(
    payload: KeyPeopleUpdate,
    session: SessionDependency,
) -> list[KeyPeopleDirectoryRead]:
    entries = await replace_key_people_directory(session, payload)
    return [directory_read(entry) for entry in entries]


@router.get("/key-people/people", response_model=list[KeyPersonRead])
async def list_key_people_endpoint(session: SessionDependency) -> list[KeyPersonRead]:
    return [KeyPersonRead.model_validate(person) for person in await list_key_people(session)]


@router.post("/key-people/people", response_model=KeyPersonRead, status_code=201)
async def create_key_person_endpoint(payload: KeyPersonCreate, session: SessionDependency) -> KeyPersonRead:
    return KeyPersonRead.model_validate(await create_key_person(session, payload))


@router.patch("/key-people/people/{key_person_id}", response_model=KeyPersonRead)
async def update_key_person_endpoint(
    key_person_id: UUID,
    payload: KeyPersonUpdate,
    session: SessionDependency,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> KeyPersonRead:
    person = await update_key_person(session, key_person_id, payload, version_from_if_match(if_match))
    response.headers["ETag"] = etag_for(person.version)
    return KeyPersonRead.model_validate(person)


@router.delete("/key-people/people/{key_person_id}", response_model=KeyPersonRead)
async def deactivate_key_person_endpoint(key_person_id: UUID, session: SessionDependency) -> KeyPersonRead:
    return KeyPersonRead.model_validate(await deactivate_key_person(session, key_person_id))
