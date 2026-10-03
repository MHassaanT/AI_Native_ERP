"""Domain Service for Quality Management, Tolerance Inspections & Non-Conformance CAPA."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.quality import (
    NonConformance,
    QualityAction,
    QualityInspection,
    QualityInspectionParameter,
    QualityInspectionTemplate,
)


class QualityService:
    """Enterprise Quality Assurance, Tolerance Verification & Non-Conformance CAPA Lifecycle."""

    async def create_template(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        template_name: str,
        description: Optional[str] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> QualityInspectionTemplate:
        template_id = uuid.uuid4()
        template = QualityInspectionTemplate(
            template_id=template_id,
            tenant_id=tenant_id,
            template_name=template_name,
            description=description,
        )
        session.add(template)
        await session.flush()

        if parameters:
            for p in parameters:
                param = QualityInspectionParameter(
                    parameter_id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    template_id=template.template_id,
                    parameter_name=p["parameter_name"],
                    specification=p["specification"],
                    min_value=Decimal(str(p["min_value"])) if p.get("min_value") is not None else None,
                    max_value=Decimal(str(p["max_value"])) if p.get("max_value") is not None else None,
                    acceptance_tolerance=p.get("acceptance_tolerance"),
                )
                session.add(param)

        await session.flush()
        return await self.get_template(session, tenant_id, template_id)  # type: ignore

    async def list_templates(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> List[QualityInspectionTemplate]:
        stmt = (
            select(QualityInspectionTemplate)
            .options(selectinload(QualityInspectionTemplate.parameters))
            .where(QualityInspectionTemplate.tenant_id == tenant_id)
            .order_by(QualityInspectionTemplate.template_name)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_template(
        self, session: AsyncSession, tenant_id: uuid.UUID, template_id: uuid.UUID
    ) -> Optional[QualityInspectionTemplate]:
        stmt = (
            select(QualityInspectionTemplate)
            .options(selectinload(QualityInspectionTemplate.parameters))
            .where(
                QualityInspectionTemplate.tenant_id == tenant_id,
                QualityInspectionTemplate.template_id == template_id,
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_inspection(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        inspection_number: str,
        inspection_type: str,
        reference_doc_type: str,
        item_code: str,
        sample_size: Decimal = Decimal("1.0000"),
        reference_doc_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        inspected_by_id: Optional[uuid.UUID] = None,
        inspection_date: Optional[date] = None,
        readings: Optional[List[Dict[str, Any]]] = None,
        remarks: Optional[str] = None,
        auto_create_nc_on_failure: bool = True,
    ) -> QualityInspection:
        overall_status = "PASS"
        evaluated_readings = []

        if readings:
            for r in readings:
                param_name = r.get("parameter_name", "Reading")
                val = Decimal(str(r.get("reading_value", "0"))) if r.get("reading_value") is not None else None
                min_v = Decimal(str(r.get("min_value"))) if r.get("min_value") is not None else None
                max_v = Decimal(str(r.get("max_value"))) if r.get("max_value") is not None else None

                param_pass = True
                if val is not None:
                    if min_v is not None and val < min_v:
                        param_pass = False
                    if max_v is not None and val > max_v:
                        param_pass = False

                item_eval = {
                    "parameter_name": param_name,
                    "reading_value": float(val) if val is not None else None,
                    "min_value": float(min_v) if min_v is not None else None,
                    "max_value": float(max_v) if max_v is not None else None,
                    "status": "PASS" if param_pass else "FAIL",
                }
                evaluated_readings.append(item_eval)

                if not param_pass:
                    overall_status = "FAIL"

        inspection_id = uuid.uuid4()
        inspection = QualityInspection(
            inspection_id=inspection_id,
            tenant_id=tenant_id,
            inspection_number=inspection_number,
            inspection_type=inspection_type.upper(),
            reference_doc_type=reference_doc_type,
            reference_doc_id=reference_doc_id,
            item_id=item_id,
            item_code=item_code,
            sample_size=sample_size,
            inspected_by_id=inspected_by_id,
            inspection_date=inspection_date or date.today(),
            status=overall_status,
            readings=evaluated_readings,
            remarks=remarks,
        )
        session.add(inspection)
        await session.flush()

        if overall_status == "FAIL" and auto_create_nc_on_failure:
            nc_num = f"NCR-{inspection_number}"
            await self.create_non_conformance(
                session=session,
                tenant_id=tenant_id,
                nc_number=nc_num,
                title=f"Defect in {item_code} ({inspection_type})",
                source_type="INSPECTION",
                inspection_id=inspection.inspection_id,
                item_id=item_id,
                item_code=item_code,
                severity="MAJOR",
                description=f"Auto-generated from failed inspection {inspection_number}. Remarks: {remarks or 'Out of spec'}",
                immediate_disposition="REWORK",
            )

        return inspection

    async def get_inspection(
        self, session: AsyncSession, tenant_id: uuid.UUID, inspection_id: uuid.UUID
    ) -> Optional[QualityInspection]:
        stmt = (
            select(QualityInspection)
            .options(selectinload(QualityInspection.non_conformances))
            .where(
                QualityInspection.tenant_id == tenant_id,
                QualityInspection.inspection_id == inspection_id,
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_inspections(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        inspection_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[QualityInspection]:
        stmt = select(QualityInspection).where(QualityInspection.tenant_id == tenant_id)
        if inspection_type:
            stmt = stmt.where(QualityInspection.inspection_type == inspection_type.upper())
        if status:
            stmt = stmt.where(QualityInspection.status == status.upper())
        stmt = stmt.order_by(QualityInspection.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def create_non_conformance(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        nc_number: str,
        title: str,
        source_type: str = "INSPECTION",
        inspection_id: Optional[uuid.UUID] = None,
        item_id: Optional[uuid.UUID] = None,
        item_code: Optional[str] = None,
        severity: str = "MAJOR",
        description: str = "",
        immediate_disposition: str = "REWORK",
        status: str = "OPEN",
    ) -> NonConformance:
        nc_id = uuid.uuid4()
        nc = NonConformance(
            nc_id=nc_id,
            tenant_id=tenant_id,
            nc_number=nc_number,
            title=title,
            source_type=source_type.upper(),
            inspection_id=inspection_id,
            item_id=item_id,
            item_code=item_code,
            severity=severity.upper(),
            description=description,
            immediate_disposition=immediate_disposition.upper(),
            status=status.upper(),
        )
        session.add(nc)
        await session.flush()
        return nc

    async def list_non_conformances(
        self, session: AsyncSession, tenant_id: uuid.UUID, status: Optional[str] = None
    ) -> List[NonConformance]:
        stmt = (
            select(NonConformance)
            .options(selectinload(NonConformance.actions))
            .where(NonConformance.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(NonConformance.status == status.upper())
        stmt = stmt.order_by(NonConformance.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_non_conformance(
        self, session: AsyncSession, tenant_id: uuid.UUID, nc_id: uuid.UUID
    ) -> Optional[NonConformance]:
        stmt = (
            select(NonConformance)
            .options(selectinload(NonConformance.actions))
            .where(NonConformance.tenant_id == tenant_id, NonConformance.nc_id == nc_id)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_action(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        capa_number: str,
        nc_id: uuid.UUID,
        action_type: str,
        root_cause_analysis: str,
        action_plan: str,
        target_completion_date: date,
        assigned_to_id: Optional[uuid.UUID] = None,
    ) -> QualityAction:
        nc = await self.get_non_conformance(session, tenant_id, nc_id)
        if not nc:
            raise ValueError(f"Non-Conformance {nc_id} not found.")

        action_id = uuid.uuid4()
        action = QualityAction(
            action_id=action_id,
            tenant_id=tenant_id,
            capa_number=capa_number,
            nc_id=nc_id,
            action_type=action_type.upper(),
            root_cause_analysis=root_cause_analysis,
            action_plan=action_plan,
            assigned_to_id=assigned_to_id,
            target_completion_date=target_completion_date,
            status="OPEN",
        )
        session.add(action)

        nc.status = "CAPA_ASSIGNED"
        await session.flush()
        return action

    async def resolve_action(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        action_id: uuid.UUID,
        resolution_notes: str,
        new_status: str = "VERIFIED_CLOSED",
    ) -> QualityAction:
        stmt = select(QualityAction).where(
            QualityAction.tenant_id == tenant_id, QualityAction.action_id == action_id
        )
        res = await session.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise ValueError(f"Quality Action {action_id} not found.")

        action.resolution_notes = resolution_notes
        action.status = new_status.upper()
        await session.flush()

        if action.nc_id:
            nc = await self.get_non_conformance(session, tenant_id, action.nc_id)
            if nc:
                all_closed = all(a.status == "VERIFIED_CLOSED" for a in nc.actions)
                if all_closed:
                    nc.status = "CLOSED"

        await session.flush()
        return action

    async def list_actions(
        self, session: AsyncSession, tenant_id: uuid.UUID, status: Optional[str] = None
    ) -> List[QualityAction]:
        stmt = select(QualityAction).where(QualityAction.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(QualityAction.status == status.upper())
        stmt = stmt.order_by(QualityAction.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())


quality_service = QualityService()
