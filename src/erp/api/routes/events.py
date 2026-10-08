"""Tenant-scoped event dead-letter review routes."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from erp.api.deps import DbSessionDep, TenantIdDep, require_roles
from erp.db.models.events import EventDeadLetterRecord
from erp.db.models.user import User

router = APIRouter(prefix="/events", tags=["Event Operations"])


class DeadLetterReviewRequest(BaseModel):
    notes: str = Field(..., min_length=10, max_length=1000)


def _dead_letter_payload(record: EventDeadLetterRecord) -> dict[str, Any]:
    return {
        "dead_letter_id": str(record.dead_letter_id),
        "event_id": record.event_id,
        "consumer_group": record.consumer_group,
        "source_topic": record.source_topic,
        "partition_key": record.partition_key,
        "payload": record.payload,
        "attempt_count": record.attempt_count,
        "failure_type": record.failure_type,
        "status": record.status,
        "reviewed_by": str(record.reviewed_by) if record.reviewed_by else None,
        "resolution_notes": record.resolution_notes,
        "created_at": record.created_at.isoformat(),
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
    }


@router.get("/dead-letters")
async def list_dead_letters(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    reviewer: User = require_roles("TENANT_ADMIN"),
    status_filter: str = Query("OPEN", alias="status", pattern="^(OPEN|REVIEWED)$"),
    limit: int = Query(50, ge=1, le=100),
):
    """Lists event payloads that require review, visible only to this tenant's admins."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    rows = (
        await session.execute(
            select(EventDeadLetterRecord)
            .where(
                EventDeadLetterRecord.tenant_id == tenant_id,
                EventDeadLetterRecord.status == status_filter,
            )
            .order_by(desc(EventDeadLetterRecord.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return [_dead_letter_payload(row) for row in rows]


@router.get("/dead-letters/{dead_letter_id}")
async def get_dead_letter(
    dead_letter_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    reviewer: User = require_roles("TENANT_ADMIN"),
):
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    record = (
        await session.execute(
            select(EventDeadLetterRecord).where(
                EventDeadLetterRecord.dead_letter_id == dead_letter_id,
                EventDeadLetterRecord.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Dead-letter event not found.")
    return _dead_letter_payload(record)


@router.post("/dead-letters/{dead_letter_id}/review")
async def review_dead_letter(
    dead_letter_id: uuid.UUID,
    request: DeadLetterReviewRequest,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    reviewer: User = require_roles("TENANT_ADMIN"),
):
    """Records human review; it does not replay the event or imply it was processed."""
    if reviewer.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Reviewer is not a member of this tenant.")
    record = (
        await session.execute(
            select(EventDeadLetterRecord)
            .where(
                EventDeadLetterRecord.dead_letter_id == dead_letter_id,
                EventDeadLetterRecord.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Dead-letter event not found.")
    if record.status != "OPEN":
        raise HTTPException(status_code=409, detail="Dead-letter event has already been reviewed.")
    record.status = "REVIEWED"
    record.resolution_notes = request.notes
    record.reviewed_by = reviewer.user_id
    record.resolved_at = datetime.now(UTC)
    await session.commit()
    return {"status": "REVIEWED", "dead_letter_id": str(record.dead_letter_id)}
