from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AuditEvent
from app.middleware.correlation import current_correlation_id


async def record_audit(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: Any,
    action: str,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            correlation_id=correlation_id or current_correlation_id.get(),
            request_source="api",
        )
    )
