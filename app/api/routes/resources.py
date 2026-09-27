from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.capacity import ResourceCreate, ResourceRead, ResourceUpdate
from app.application.capacity_service import create_resource, list_resources, update_resource
from app.application.import_service import (
    commit_resources,
    parse_resources,
    preview_resources,
)
from app.core.database import get_db_session
from app.core.concurrency import etag_for, version_from_if_match

router = APIRouter(prefix="/resources", tags=["resources"])
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
CsvFile = Annotated[UploadFile, File(...)]


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
async def create_resource_endpoint(
    payload: ResourceCreate,
    session: SessionDependency,
) -> ResourceRead:
    resource = await create_resource(session, payload)
    return ResourceRead.model_validate(resource)


@router.patch("/{resource_id}", response_model=ResourceRead)
async def update_resource_endpoint(
    resource_id: UUID,
    payload: ResourceUpdate,
    session: SessionDependency,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> ResourceRead:
    resource = await update_resource(session, resource_id, payload, version_from_if_match(if_match))
    response.headers["ETag"] = etag_for(resource.version)
    return ResourceRead.model_validate(resource)


@router.get("", response_model=list[ResourceRead])
async def list_resources_endpoint(session: SessionDependency) -> list[ResourceRead]:
    resources = await list_resources(session)
    return [ResourceRead.model_validate(resource) for resource in resources]


@router.post("/import/preview")
async def preview_resources_import(
    session: SessionDependency,
    file: CsvFile,
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a CSV file.")
    parsed = parse_resources(await file.read())
    return await preview_resources(session, parsed)


@router.post("/import")
async def import_resources_endpoint(
    session: SessionDependency,
    file: CsvFile,
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Upload a CSV file.")
    parsed = parse_resources(await file.read())
    preview = await preview_resources(session, parsed)
    if preview["issues"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "CSV validation failed.", "issues": preview["issues"]},
        )
    return {"entity": "developers", **await commit_resources(session, parsed)}
