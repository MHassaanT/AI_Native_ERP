"""CRM Router: Leads, Opportunities, Campaigns, Appointments, and Contracts."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.crm import campaign_service, lead_service, opportunity_service

router = APIRouter(prefix="/crm", tags=["CRM & Pipeline"])


# =========================================================================
# Schemas
# =========================================================================

class CreateLeadSchema(BaseModel):
    lead_name: str
    salutation: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email_id: str | None = None
    mobile_no: str | None = None
    phone: str | None = None
    company_name: str | None = None
    annual_revenue: Decimal = Decimal("0.0000")
    no_of_employees: int = 1
    industry: str | None = None
    market_segment: str | None = None
    territory: str | None = None
    source: str = "WEBSITE"
    status: str = "LEAD"
    notes: str | None = None


class ConvertLeadOpportunitySchema(BaseModel):
    title: str | None = None
    opportunity_amount: Decimal = Decimal("10000.0000")
    sales_stage: str = "QUALIFICATION"


class OpportunityItemInputSchema(BaseModel):
    item_id: uuid.UUID
    item_code: str
    item_name: str
    quantity: Decimal = Decimal("1.0000")
    rate: Decimal = Decimal("0.0000")


class CreateOpportunitySchema(BaseModel):
    opportunity_number: str
    party_id: uuid.UUID
    party_name: str
    title: str
    opportunity_from: str = "LEAD"
    opportunity_type: str = "SALES"
    sales_stage: str = "PROSPECTING"
    probability: Decimal | None = None
    opportunity_amount: Decimal = Decimal("0.0000")
    expected_closing_date: date | None = None
    notes: str | None = None
    items: list[OpportunityItemInputSchema] | None = None


class UpdateOpportunityStageSchema(BaseModel):
    sales_stage: str
    lost_reason: str | None = None


class ConvertOpportunityQuotationSchema(BaseModel):
    valid_days: int = 30


class CreateCampaignSchema(BaseModel):
    campaign_name: str
    campaign_type: str = "EMAIL"
    status: str = "ACTIVE"
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal = Decimal("0.0000")
    actual_cost: Decimal = Decimal("0.0000")


class AddDripStepSchema(BaseModel):
    sequence_step: int
    delay_days: int
    subject: str
    template_body: str
    lead_id: uuid.UUID | None = None


class CreateAppointmentSchema(BaseModel):
    party_id: uuid.UUID
    party_name: str
    scheduled_time: datetime
    appointment_with: str = "LEAD"
    duration_mins: int = 30
    summary: str | None = None


class UpdateAppointmentStatusSchema(BaseModel):
    status: str


class CreateContractSchema(BaseModel):
    contract_name: str
    party_id: uuid.UUID
    party_name: str
    start_date: date
    party_type: str = "CUSTOMER"
    end_date: date | None = None
    contract_value: Decimal = Decimal("0.0000")
    terms_and_conditions: str | None = None


# =========================================================================
# Lead Endpoints
# =========================================================================

@router.post("/leads", status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: CreateLeadSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Registers a prospective lead and calculates its qualification score."""
    lead = await lead_service.create_lead(
        session=session,
        tenant_id=tenant_id,
        lead_name=data.lead_name,
        salutation=data.salutation,
        first_name=data.first_name,
        last_name=data.last_name,
        email_id=data.email_id,
        mobile_no=data.mobile_no,
        phone=data.phone,
        company_name=data.company_name,
        annual_revenue=data.annual_revenue,
        no_of_employees=data.no_of_employees,
        industry=data.industry,
        market_segment=data.market_segment,
        territory=data.territory,
        source=data.source,
        status=data.status,
        notes=data.notes,
    )
    return lead


@router.get("/leads")
async def list_leads(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status: str | None = Query(None),
    search: str | None = Query(None),
):
    """Lists leads with status filter and search."""
    return await lead_service.list_leads(session, tenant_id, status=status, search=search)


@router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Retrieves a single lead."""
    lead = await lead_service.get_lead(session, tenant_id, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead


@router.post("/leads/{lead_id}/convert-opportunity")
async def convert_lead_to_opportunity(
    lead_id: uuid.UUID,
    data: ConvertLeadOpportunitySchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """1-click conversion from Lead to Opportunity deal in pipeline."""
    try:
        opp = await lead_service.convert_lead_to_opportunity(
            session=session,
            tenant_id=tenant_id,
            lead_id=lead_id,
            title=data.title,
            opportunity_amount=data.opportunity_amount,
            sales_stage=data.sales_stage,
        )
        return opp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/leads/{lead_id}/convert-customer")
async def convert_lead_to_customer(
    lead_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """1-click conversion from Lead to official Customer profile."""
    try:
        cust = await lead_service.convert_lead_to_customer(session, tenant_id, lead_id)
        return cust
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Opportunity Endpoints
# =========================================================================

@router.post("/opportunities", status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    data: CreateOpportunitySchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Creates a new sales opportunity deal."""
    raw_items = [it.model_dump() for it in data.items] if data.items else None
    opp = await opportunity_service.create_opportunity(
        session=session,
        tenant_id=tenant_id,
        opportunity_number=data.opportunity_number,
        party_id=data.party_id,
        party_name=data.party_name,
        title=data.title,
        opportunity_from=data.opportunity_from,
        opportunity_type=data.opportunity_type,
        sales_stage=data.sales_stage,
        probability=data.probability,
        opportunity_amount=data.opportunity_amount,
        expected_closing_date=data.expected_closing_date,
        notes=data.notes,
        items=raw_items,
    )
    return opp


@router.get("/opportunities")
async def list_opportunities(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    sales_stage: str | None = Query(None),
    search: str | None = Query(None),
):
    """Lists opportunities with optional stage filter and search."""
    return await opportunity_service.list_opportunities(
        session, tenant_id, sales_stage=sales_stage, search=search
    )


@router.get("/pipeline-summary")
@router.get("/opportunities/pipeline-summary")
async def get_pipeline_summary(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Calculates weighted pipeline forecast and sales stage distribution."""
    return await opportunity_service.get_pipeline_summary(session, tenant_id)


@router.get("/opportunities/{opp_id}")
async def get_opportunity(
    opp_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Retrieves opportunity details with item lines."""
    opp = await opportunity_service.get_opportunity(session, tenant_id, opp_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found.")
    return opp


@router.patch("/opportunities/{opp_id}/stage")
async def update_opportunity_stage(
    opp_id: uuid.UUID,
    data: UpdateOpportunityStageSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Transitions deal to a new sales stage."""
    try:
        return await opportunity_service.update_stage(
            session=session,
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            new_stage=data.sales_stage,
            lost_reason=data.lost_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/opportunities/{opp_id}/convert-quotation")
async def convert_opportunity_to_quotation(
    opp_id: uuid.UUID,
    data: ConvertOpportunityQuotationSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """1-click conversion from Opportunity to official commercial Sales Quotation."""
    try:
        quote = await opportunity_service.convert_opportunity_to_quotation(
            session=session,
            tenant_id=tenant_id,
            opportunity_id=opp_id,
            valid_days=data.valid_days,
        )
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Campaign & Drip Endpoints
# =========================================================================

@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CreateCampaignSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Initializes a new marketing campaign."""
    return await campaign_service.create_campaign(
        session=session,
        tenant_id=tenant_id,
        campaign_name=data.campaign_name,
        campaign_type=data.campaign_type,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
        budget=data.budget,
        actual_cost=data.actual_cost,
    )


@router.get("/campaigns")
async def list_campaigns(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status: str | None = Query(None),
):
    """Lists marketing campaigns."""
    return await campaign_service.list_campaigns(session, tenant_id, status=status)


@router.get("/campaigns/{camp_id}")
async def get_campaign(
    camp_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Retrieves campaign details with drip sequence steps."""
    camp = await campaign_service.get_campaign(session, tenant_id, camp_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return camp


@router.post("/campaigns/{camp_id}/drip-step", status_code=status.HTTP_201_CREATED)
async def add_drip_step(
    camp_id: uuid.UUID,
    data: AddDripStepSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Adds an automated email drip step to a campaign."""
    return await campaign_service.add_drip_step(
        session=session,
        tenant_id=tenant_id,
        campaign_id=camp_id,
        sequence_step=data.sequence_step,
        delay_days=data.delay_days,
        subject=data.subject,
        template_body=data.template_body,
        lead_id=data.lead_id,
    )


@router.get("/campaigns/{camp_id}/drip-steps")
async def list_campaign_drips(
    camp_id: uuid.UUID,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Lists scheduled drip steps for a campaign."""
    return await campaign_service.list_campaign_drips(session, tenant_id, camp_id)


# =========================================================================
# Appointment Endpoints
# =========================================================================

@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: CreateAppointmentSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Schedules a calendar consultation appointment."""
    return await campaign_service.create_appointment(
        session=session,
        tenant_id=tenant_id,
        party_id=data.party_id,
        party_name=data.party_name,
        scheduled_time=data.scheduled_time,
        appointment_with=data.appointment_with,
        duration_mins=data.duration_mins,
        summary=data.summary,
    )


@router.get("/appointments")
async def list_appointments(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status: str | None = Query(None),
):
    """Lists calendar appointments."""
    return await campaign_service.list_appointments(session, tenant_id, status=status)


@router.patch("/appointments/{app_id}/status")
async def update_appointment_status(
    app_id: uuid.UUID,
    data: UpdateAppointmentStatusSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Updates appointment status."""
    try:
        return await campaign_service.update_appointment_status(
            session=session,
            tenant_id=tenant_id,
            appointment_id=app_id,
            status=data.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Contract Endpoints
# =========================================================================

@router.post("/contracts", status_code=status.HTTP_201_CREATED)
async def create_contract(
    data: CreateContractSchema,
    session: DbSessionDep,
    tenant_id: TenantIdDep,
):
    """Creates a commercial or service contract."""
    return await campaign_service.create_contract(
        session=session,
        tenant_id=tenant_id,
        contract_name=data.contract_name,
        party_id=data.party_id,
        party_name=data.party_name,
        start_date=data.start_date,
        party_type=data.party_type,
        end_date=data.end_date,
        contract_value=data.contract_value,
        terms_and_conditions=data.terms_and_conditions,
    )


@router.get("/contracts")
async def list_contracts(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    status: str | None = Query(None),
):
    """Lists contracts."""
    return await campaign_service.list_contracts(session, tenant_id, status=status)
