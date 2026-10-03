"""Domain Service for Support Tickets, Omnichannel Conversations, and SLA Breach Auditing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.crm import Lead
from erp.db.models.sales import Customer
from erp.db.models.support import Issue, IssueCommunication, ServiceLevelAgreement
from erp.workflows.support.sla_service import sla_service


class IssueService:
    """Enterprise support ticketing, threaded messaging, and SLA monitoring."""

    async def create_issue(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        subject: str,
        customer_id: uuid.UUID | None = None,
        lead_id: uuid.UUID | None = None,
        raised_by_email: str | None = None,
        raised_by_name: str | None = None,
        priority: str = "MEDIUM",
        issue_type: str = "TECHNICAL",
        description: str | None = None,
        assigned_to_id: uuid.UUID | None = None,
        sla_id: uuid.UUID | None = None,
    ) -> Issue:
        """Opens a new support ticket and attaches applicable SLA deadlines."""
        # Generate Issue Number
        count_stmt = select(func.count(Issue.issue_id)).where(Issue.tenant_id == tenant_id)
        total_issues = (await session.execute(count_stmt)).scalar() or 0
        issue_number = f"ISS-{datetime.now().year}-{total_issues + 1:04d}"

        # Resolve SLA
        sla = None
        if sla_id:
            sla_stmt = (
                select(ServiceLevelAgreement)
                .options(selectinload(ServiceLevelAgreement.priorities))
                .where(
                    ServiceLevelAgreement.tenant_id == tenant_id,
                    ServiceLevelAgreement.sla_id == sla_id,
                )
            )
            sla = (await session.execute(sla_stmt)).scalar_one_or_none()

        if not sla:
            sla = await sla_service.get_or_create_default_sla(
                session, tenant_id, customer_id=customer_id
            )

        now = datetime.now(timezone.utc)
        response_by, resolution_by = sla_service.calculate_deadlines(
            sla=sla, priority=priority, start_time=now
        )

        initial_comms = []
        if description and description.strip():
            initial_comms.append(
                IssueCommunication(
                    tenant_id=tenant_id,
                    sender_type="CUSTOMER",
                    sender_name=raised_by_name or raised_by_email or "Customer",
                    sender_email=raised_by_email,
                    message=description.strip(),
                    is_internal_note=False,
                )
            )

        issue = Issue(
            tenant_id=tenant_id,
            issue_number=issue_number,
            subject=subject.strip(),
            customer_id=customer_id,
            lead_id=lead_id,
            raised_by_email=raised_by_email.strip() if raised_by_email else None,
            raised_by_name=raised_by_name.strip() if raised_by_name else None,
            status="OPEN",
            priority=priority.strip().upper(),
            issue_type=issue_type.strip().upper(),
            assigned_to_id=assigned_to_id,
            sla_id=sla.sla_id if sla else None,
            response_by=response_by,
            resolution_by=resolution_by,
            sla_status="WITHIN_SLA",
            communications=initial_comms,
        )
        session.add(issue)
        await session.commit()
        return await self.get_issue(session, tenant_id, issue.issue_id)  # type: ignore

    async def get_issue(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        issue_id: uuid.UUID,
    ) -> Issue | None:
        """Retrieves a single issue with full message thread and customer/lead details."""
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.communications),
                selectinload(Issue.customer),
                selectinload(Issue.lead),
                selectinload(Issue.sla),
            )
            .where(Issue.tenant_id == tenant_id, Issue.issue_id == issue_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_issues(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
    ) -> list[Issue]:
        """Lists support tickets with filters and real-time SLA breach evaluation."""
        stmt = (
            select(Issue)
            .options(
                selectinload(Issue.customer),
                selectinload(Issue.lead),
                selectinload(Issue.communications),
            )
            .where(Issue.tenant_id == tenant_id)
        )

        if status:
            stmt = stmt.where(Issue.status == status.strip().upper())
        if priority:
            stmt = stmt.where(Issue.priority == priority.strip().upper())
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Issue.issue_number.ilike(term),
                    Issue.subject.ilike(term),
                    Issue.raised_by_name.ilike(term),
                    Issue.raised_by_email.ilike(term),
                )
            )

        stmt = stmt.order_by(Issue.created_at.desc())
        issues = list((await session.execute(stmt)).scalars().all())

        # Real-time SLA breach evaluation on load
        now = datetime.now(timezone.utc)
        for iss in issues:
            if iss.status not in ["RESOLVED", "CLOSED"]:
                if iss.resolution_by and now > iss.resolution_by:
                    iss.sla_status = "RESOLUTION_BREACHED"
                elif not iss.first_responded_on and iss.response_by and now > iss.response_by:
                    iss.sla_status = "RESPONSE_BREACHED"

        return issues

    async def add_communication(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        issue_id: uuid.UUID,
        sender_type: str,
        sender_name: str,
        message: str,
        is_internal_note: bool = False,
        sender_email: str | None = None,
    ) -> IssueCommunication:
        """Appends a customer response, agent message, or private internal note."""
        issue = await self.get_issue(session, tenant_id, issue_id)
        if not issue:
            raise ValueError(f"Issue '{issue_id}' not found.")

        now = datetime.now(timezone.utc)
        type_norm = sender_type.strip().upper()

        # If first agent reply, record first response time and check response SLA
        if type_norm == "AGENT" and not is_internal_note:
            if not issue.first_responded_on:
                issue.first_responded_on = now
                if issue.response_by and now > issue.response_by:
                    issue.sla_status = "RESPONSE_BREACHED"
            issue.status = "REPLIED"

        comm = IssueCommunication(
            tenant_id=tenant_id,
            issue_id=issue_id,
            sender_type=type_norm,
            sender_name=sender_name.strip(),
            sender_email=sender_email.strip() if sender_email else None,
            message=message.strip(),
            is_internal_note=is_internal_note,
        )
        session.add(comm)
        await session.commit()
        await session.refresh(comm)
        return comm

    async def resolve_issue(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        issue_id: uuid.UUID,
        resolution_details: str,
        status: str = "RESOLVED",
    ) -> Issue:
        """Marks a ticket resolved, recording resolution timestamp and SLA compliance."""
        issue = await self.get_issue(session, tenant_id, issue_id)
        if not issue:
            raise ValueError(f"Issue '{issue_id}' not found.")

        now = datetime.now(timezone.utc)
        issue.resolution_date = now
        issue.resolution_details = resolution_details.strip()
        issue.status = status.strip().upper()

        if issue.resolution_by and now > issue.resolution_by:
            issue.sla_status = "RESOLUTION_BREACHED"
        else:
            issue.sla_status = "FULFILLED"

        # Log system resolution communication
        sys_comm = IssueCommunication(
            tenant_id=tenant_id,
            issue_id=issue_id,
            sender_type="SYSTEM",
            sender_name="Helpdesk Automation",
            message=f"Ticket marked as {issue.status}. Resolution: {resolution_details}",
            is_internal_note=False,
        )
        session.add(sys_comm)

        await session.commit()
        return await self.get_issue(session, tenant_id, issue.issue_id)  # type: ignore


issue_service = IssueService()
