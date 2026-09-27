from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="Check service readiness")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="dfbox-dcm-be",
        timestamp=datetime.now(UTC),
    )
