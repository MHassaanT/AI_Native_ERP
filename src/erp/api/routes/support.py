"""Support & Helpdesk Router: SLAs, Issues/Tickets, Conversations, and Warranty Claims."""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.support import issue_service, sla_service, warranty_service

router = APIRouter(prefix="/support", tags=["Support & Helpdesk"])


# =========================================================================
# Schemas
# =========================================================================

class PriorityMatrixItemSchema(BaseModel):
    priority: str
    response_time_hours: Decimal
    resolution_time_hours: Decimal


class CreateSlaSchema(BaseModel):
    sla_name: str
    is_default: bool = False
    entity_type: str = "ALL"
    entity_id: uuid.UUID | None = None
    priorities: list[PriorityMatrixItemSchema] | None = None


class CreateIssueSchema(BaseModel):
    subject: str
    customer_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    raised_by_email: str | None = None
    raised_by_name: str | None = None
    priority: str = "MEDIUM"
    issue_type: str = "TECHNICAL"
    description: str | None = None
    assigned_to_id: uuid.UUID | None = None
    sla_id: uuid.UUID | None = None


class AddCommunicationSchema(BaseModel):
    sender_type: str = "AGENT"  # AGENT, CUSTOMER
    sender_name: str
    message: str
    is_internal_note: bool = False
    sender_email: str | None = None


class ResolveIssueSchema(BaseModel):
    resolution_details: str
    status: str = "RESOLVED"


class CreateWarrantyClaimSchema(BaseModel):
    claim_number: str
    customer_id: uuid.UUID
    serial_number: str
    complaint_description: str
    resolution_type: str = "REPAIR"
    item_id: uuid.UUID | None = None


class ResolveWarrantyClaimSchema(BaseModel):
    resolution_details: str
    resolution_type: str | None = None
    status: str = "RESOLVED"


# =========================================================================
# SLA Endpoints
# =========================================================================

@router.post("/slas", status_code=status.HTTP_201_CREATED)
async def create_sla(
    data: CreateSlaSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Configures a Service Level Agreement policy."""
    raw_p = [p.model_dump() for p in data.priorities] if data.priorities else None
    return await sla_service.create_sla(
        session=session,
        tenant_id=tenant_id,
        sla_name=data.sla_name,
        is_default=data.is_default,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        priorities=raw_p,
    )


@router.get("/slas")
async def list_slas(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Lists configured Service Level Agreements."""
    return await sla_service.list_slas(session, tenant_id)


# =========================================================================
# Issue Ticket Endpoints
# =========================================================================

@router.post("/issues", status_code=status.HTTP_201_CREATED)
async def create_issue(
    data: CreateIssueSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Opens a support ticket and attaches applicable SLA deadlines."""
    return await issue_service.create_issue(
        session=session,
        tenant_id=tenant_id,
        subject=data.subject,
        customer_id=data.customer_id,
        lead_id=data.lead_id,
        raised_by_email=data.raised_by_email,
        raised_by_name=data.raised_by_name,
        priority=data.priority,
        issue_type=data.issue_type,
        description=data.description,
        assigned_to_id=data.assigned_to_id,
        sla_id=data.sla_id,
    )


@router.get("/issues")
async def list_issues(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status: str | None = Query(None),
    priority: str | None = Query(None),
    search: str | None = Query(None),
):
    """Lists support tickets with dynamic SLA breach assessment."""
    return await issue_service.list_issues(
        session, tenant_id, status=status, priority=priority, search=search
    )


@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Retrieves an issue with its threaded message history."""
    issue = await issue_service.get_issue(session, tenant_id, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return issue


@router.post("/issues/{issue_id}/communications", status_code=status.HTTP_201_CREATED)
@router.post("/issues/{issue_id}/communication", status_code=status.HTTP_201_CREATED)
async def add_issue_communication(
    issue_id: uuid.UUID,
    data: AddCommunicationSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Appends a customer response, agent reply, or private internal note."""
    try:
        return await issue_service.add_communication(
            session=session,
            tenant_id=tenant_id,
            issue_id=issue_id,
            sender_type=data.sender_type,
            sender_name=data.sender_name,
            message=data.message,
            is_internal_note=data.is_internal_note,
            sender_email=data.sender_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/issues/{issue_id}/resolve")
async def resolve_issue(
    issue_id: uuid.UUID,
    data: ResolveIssueSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Marks a ticket resolved and evaluates SLA compliance."""
    try:
        return await issue_service.resolve_issue(
            session=session,
            tenant_id=tenant_id,
            issue_id=issue_id,
            resolution_details=data.resolution_details,
            status=data.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Warranty Claim Endpoints
# =========================================================================

@router.get("/warranty/verify")
async def verify_serial_warranty(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    serial_number: str = Query(...),
):
    """Live verification of serial number registration and warranty coverage status via query param."""
    return await warranty_service.verify_serial_warranty(session, tenant_id, serial_number)


@router.get("/warranty/verify/{serial_number}")
async def verify_serial_warranty_path(
    serial_number: str,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Live verification of serial number registration and warranty coverage status via path param."""
    return await warranty_service.verify_serial_warranty(session, tenant_id, serial_number)


@router.post("/warranty/claims", status_code=status.HTTP_201_CREATED)
@router.post("/warranty-claims", status_code=status.HTTP_201_CREATED)
async def create_warranty_claim(
    data: CreateWarrantyClaimSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Files a new warranty claim and automatically evaluates warranty entitlement."""
    try:
        return await warranty_service.create_warranty_claim(
            session=session,
            tenant_id=tenant_id,
            claim_number=data.claim_number,
            customer_id=data.customer_id,
            serial_number=data.serial_number,
            complaint_description=data.complaint_description,
            resolution_type=data.resolution_type,
            item_id=data.item_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/warranty/claims")
@router.get("/warranty-claims")
async def list_warranty_claims(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status: str | None = Query(None),
):
    """Lists warranty claims."""
    return await warranty_service.list_warranty_claims(session, tenant_id, status=status)


@router.post("/warranty/claims/{claim_id}/resolve")
@router.post("/warranty-claims/{claim_id}/resolve")
async def resolve_warranty_claim(
    claim_id: uuid.UUID,
    data: ResolveWarrantyClaimSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Resolves a warranty claim with repair/replacement authorization."""
    try:
        return await warranty_service.resolve_warranty_claim(
            session=session,
            tenant_id=tenant_id,
            claim_id=claim_id,
            resolution_details=data.resolution_details,
            resolution_type=data.resolution_type,
            new_status=data.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
