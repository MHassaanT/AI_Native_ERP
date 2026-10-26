"""Transactional source-document lineage helpers for purchasing conversions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.purchasing import MaterialRequest, MaterialRequestItem


class SourceDocumentService:
    """Owns ordered source locks and derived progress for purchasing documents.

    Callers keep this work in their request transaction: locks remain held until
    the enclosing transaction commits or rolls back.
    """

    async def lock_material_request_lines(
        self, session: AsyncSession, tenant_id: uuid.UUID, request_id: uuid.UUID,
    ) -> tuple[MaterialRequest, dict[uuid.UUID, MaterialRequestItem]]:
        request = (await session.execute(select(MaterialRequest).where(
            MaterialRequest.tenant_id == tenant_id,
            MaterialRequest.mr_id == request_id,
        ).with_for_update())).scalar_one_or_none()
        if request is None:
            raise ValueError("Material request not found in this workspace.")
        lines = (await session.scalars(select(MaterialRequestItem).where(
            MaterialRequestItem.tenant_id == tenant_id,
            MaterialRequestItem.mr_id == request_id,
        ).order_by(MaterialRequestItem.mr_item_id).with_for_update())).all()
        return request, {line.mr_item_id: line for line in lines}

    async def refresh_material_request_progress(
        self, session: AsyncSession, tenant_id: uuid.UUID, request_id: uuid.UUID,
    ) -> MaterialRequest:
        request, lines = await self.lock_material_request_lines(session, tenant_id, request_id)
        if request.status in {"CANCELLED", "DRAFT"}:
            return request
        request.status = (
            "ORDERED" if lines and all(line.ordered_qty >= line.quantity for line in lines)
            else "PARTIALLY_ORDERED" if any(line.ordered_qty > 0 for line in lines)
            else "SUBMITTED"
        )
        await session.flush()
        return request


source_document_service = SourceDocumentService()
