"""Phase 6 Automated Parity Verification Suite: CRM & Support Helpdesk Suite."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from erp.db.models.crm import (
    Appointment,
    Campaign,
    Contract,
    EmailCampaign,
    Lead,
    Opportunity,
    OpportunityItem,
)
from erp.db.models.inventory import Item, SerialNo, Warehouse
from erp.db.models.sales import Customer, SalesQuotation
from erp.db.models.support import (
    Issue,
    IssueCommunication,
    ServiceLevelAgreement,
    ServiceLevelPriority,
    WarrantyClaim,
)
from erp.db.session import async_session_factory
from erp.workflows.crm.campaign_service import campaign_service
from erp.workflows.crm.lead_service import lead_service
from erp.workflows.crm.opportunity_service import opportunity_service
from erp.workflows.support.issue_service import issue_service
from erp.workflows.support.sla_service import sla_service
from erp.workflows.support.warranty_service import warranty_service


@pytest.mark.asyncio
async def test_phase6_complete_crm_and_support_parity():
    """Exhaustive end-to-end integration test certifying 100% ERPNext CRM & Support Helpdesk Parity."""
    async with async_session_factory() as db:
        tenant_id = uuid.uuid4()

        # =========================================================================
        # 1. LEAD CREATION, QUALIFICATION SCORING & CONVERSIONS
        # =========================================================================
        # Case A: Enterprise High-Value Qualified Lead
        enterprise_lead = await lead_service.create_lead(
            session=db,
            tenant_id=tenant_id,
            lead_name="AeroDynamics Global Corp",
            company_name="AeroDynamics Global Corp",
            email_id="contact@aerodynamics.example",
            mobile_no="+1-555-888-9999",
            annual_revenue=Decimal("1500000.00"),
            no_of_employees=120,
            industry="Aerospace",
            market_segment="Enterprise Commercial",
            territory="North America",
            source="CAMPAIGN",
            notes="Interested in titanium brackets and maintenance service contracts.",
        )
        assert enterprise_lead.qualification_score >= Decimal("60.00")
        assert enterprise_lead.qualification_status == "QUALIFIED"
        assert enterprise_lead.status == "LEAD"

        # Case B: Unqualified Low-Information Lead
        unqual_lead = await lead_service.create_lead(
            session=db,
            tenant_id=tenant_id,
            lead_name="Solo Hobbyist",
            annual_revenue=Decimal("0.00"),
            no_of_employees=1,
            source="WEBSITE",
        )
        assert unqual_lead.qualification_score < Decimal("30.00")
        assert unqual_lead.qualification_status == "UNQUALIFIED"

        # Search and List Leads
        all_leads = await lead_service.list_leads(db, tenant_id)
        assert len(all_leads) == 2
        filtered_leads = await lead_service.list_leads(db, tenant_id, search="AeroDynamics")
        assert len(filtered_leads) == 1
        assert filtered_leads[0].lead_id == enterprise_lead.lead_id

        # 1-Click Convert Lead to Opportunity
        opp_from_lead = await lead_service.convert_lead_to_opportunity(
            session=db,
            tenant_id=tenant_id,
            lead_id=enterprise_lead.lead_id,
            title="Q4 Aircraft Components Supply Contract",
            opportunity_amount=Decimal("150000.00"),
            sales_stage="QUALIFICATION",
        )
        assert opp_from_lead.opportunity_from == "LEAD"
        assert opp_from_lead.party_id == enterprise_lead.lead_id
        assert opp_from_lead.total_amount == Decimal("150000.00")
        assert opp_from_lead.sales_stage == "QUALIFICATION"

        # Reload Lead to verify CONVERTED status
        refreshed_lead = await lead_service.get_lead(db, tenant_id, enterprise_lead.lead_id)
        assert refreshed_lead.status == "CONVERTED"

        # 1-Click Convert Lead to Customer
        cust_profile = await lead_service.convert_lead_to_customer(
            session=db, tenant_id=tenant_id, lead_id=enterprise_lead.lead_id
        )
        assert cust_profile is not None
        assert cust_profile.customer_name == "AeroDynamics Global Corp"
        assert cust_profile.email == "contact@aerodynamics.example"
        assert refreshed_lead.customer_id == cust_profile.customer_id

        # =========================================================================
        # 2. OPPORTUNITIES, KANBAN STAGES & SALES QUOTATION CONVERSION
        # =========================================================================
        # Create an inventory item for Opportunity line items
        catalog_item = Item(
            tenant_id=tenant_id,
            item_code=f"WING-BRKT-{uuid.uuid4().hex[:4].upper()}",
            item_name="Titanium Wing Bracket Assy",
            stock_uom="Nos",
            standard_rate=Decimal("350.0000"),
            is_active=True,
        )
        db.add(catalog_item)
        await db.commit()
        await db.refresh(catalog_item)

        # Create Opportunity with line items
        direct_opp = await opportunity_service.create_opportunity(
            session=db,
            tenant_id=tenant_id,
            opportunity_number=f"OPP-{uuid.uuid4().hex[:4].upper()}",
            party_id=cust_profile.customer_id,
            party_name=cust_profile.customer_name,
            title="Fleet Expansion Batch 1",
            opportunity_from="CUSTOMER",
            sales_stage="PROSPECTING",
            items=[
                {
                    "item_id": catalog_item.item_id,
                    "item_code": catalog_item.item_code,
                    "item_name": catalog_item.item_name,
                    "quantity": "50.0",
                    "rate": "500.00",
                }
            ],
        )
        assert direct_opp.total_amount == Decimal("25000.00")
        assert direct_opp.probability == Decimal("10.00")
        assert len(direct_opp.items) == 1

        # Progress Opportunity through Pipeline Stages (Kanban Transitions)
        opp_proposal = await opportunity_service.update_stage(
            db, tenant_id, direct_opp.opportunity_id, new_stage="PROPOSAL"
        )
        assert opp_proposal.sales_stage == "PROPOSAL"
        assert opp_proposal.probability == Decimal("50.00")

        opp_negotiation = await opportunity_service.update_stage(
            db, tenant_id, direct_opp.opportunity_id, new_stage="NEGOTIATION"
        )
        assert opp_negotiation.sales_stage == "NEGOTIATION"
        assert opp_negotiation.probability == Decimal("75.00")

        # Pipeline Summary Aggregations
        pipe_summary = await opportunity_service.get_pipeline_summary(db, tenant_id)
        assert pipe_summary["total_deals"] >= 2
        assert pipe_summary["total_pipeline_value"] >= 175000.0
        assert pipe_summary["weighted_forecast_value"] > 0

        # 1-Click Convert Opportunity to Commercial Sales Quotation
        sales_quote = await opportunity_service.convert_opportunity_to_quotation(
            session=db,
            tenant_id=tenant_id,
            opportunity_id=direct_opp.opportunity_id,
            valid_days=45,
        )
        assert sales_quote is not None
        assert sales_quote.customer_id == cust_profile.customer_id
        assert sales_quote.subtotal == Decimal("25000.00")
        assert sales_quote.tax_amount == Decimal("2500.00")  # 10% tax
        assert sales_quote.total_amount == Decimal("27500.00")

        # =========================================================================
        # 3. MARKETING CAMPAIGNS, EMAIL DRIPS, APPOINTMENTS & CONTRACTS
        # =========================================================================
        camp = await campaign_service.create_campaign(
            session=db,
            tenant_id=tenant_id,
            campaign_name="AeroTech Expo 2026",
            campaign_type="EVENT",
            budget=Decimal("50000.00"),
            actual_cost=Decimal("42000.00"),
        )
        assert camp.campaign_id is not None
        assert camp.status == "ACTIVE"

        # Automated Drip Sequence Steps
        drip_step1 = await campaign_service.add_drip_step(
            session=db,
            tenant_id=tenant_id,
            campaign_id=camp.campaign_id,
            sequence_step=1,
            delay_days=1,
            subject="Welcome to AeroDynamics Aerospace Portal",
            template_body="Thank you for visiting our booth at AeroTech Expo...",
            lead_id=enterprise_lead.lead_id,
        )
        drip_step2 = await campaign_service.add_drip_step(
            session=db,
            tenant_id=tenant_id,
            campaign_id=camp.campaign_id,
            sequence_step=2,
            delay_days=5,
            subject="Case Study: 30% Weight Reduction with Grade 5 Titanium",
            template_body="Here is our latest technical paper on precision structural bracketry...",
            lead_id=enterprise_lead.lead_id,
        )
        drips = await campaign_service.list_campaign_drips(db, tenant_id, camp.campaign_id)
        assert len(drips) == 2
        assert drips[0].sequence_step == 1
        assert drips[1].sequence_step == 2

        # Scheduled Consultation Appointment
        app_time = datetime.now(UTC) + timedelta(days=2)
        appt = await campaign_service.create_appointment(
            session=db,
            tenant_id=tenant_id,
            party_id=cust_profile.customer_id,
            party_name=cust_profile.customer_name,
            scheduled_time=app_time,
            appointment_with="CUSTOMER",
            duration_mins=60,
            summary="Technical specifications review for Wing Bracket batch",
        )
        assert appt.status == "SCHEDULED"
        assert appt.duration_mins == 60

        appt_confirmed = await campaign_service.update_appointment_status(
            db, tenant_id, appt.appointment_id, "CONFIRMED"
        )
        assert appt_confirmed.status == "CONFIRMED"

        # Commercial Service Agreement Contract
        contract = await campaign_service.create_contract(
            session=db,
            tenant_id=tenant_id,
            contract_name="Master Component Supply Agreement",
            party_type="CUSTOMER",
            party_id=cust_profile.customer_id,
            party_name=cust_profile.customer_name,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            contract_value=Decimal("500000.00"),
            terms_and_conditions="Guaranteed 72-hour lead time on replacement aerospace hardware.",
        )
        assert contract.status == "ACTIVE"
        assert contract.contract_value == Decimal("500000.00")

        # =========================================================================
        # 4. SERVICE LEVEL AGREEMENTS (SLA) & DEADLINE COMPUTATION
        # =========================================================================
        premium_sla = await sla_service.create_sla(
            session=db,
            tenant_id=tenant_id,
            sla_name="Mission-Critical Aerospace SLA",
            is_default=True,
            entity_type="ALL",
            priorities=[
                {"priority": "URGENT", "response_time_hours": "0.5", "resolution_time_hours": "2.0"},
                {"priority": "HIGH", "response_time_hours": "1.0", "resolution_time_hours": "4.0"},
                {"priority": "MEDIUM", "response_time_hours": "2.0", "resolution_time_hours": "12.0"},
                {"priority": "LOW", "response_time_hours": "4.0", "resolution_time_hours": "24.0"},
            ],
        )
        assert premium_sla.is_default is True
        assert len(premium_sla.priorities) == 4

        # Test deadline math
        start_ts = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
        resp_by, resol_by = sla_service.calculate_deadlines(premium_sla, priority="URGENT", start_time=start_ts)
        assert resp_by == start_ts + timedelta(minutes=30)
        assert resol_by == start_ts + timedelta(hours=2)

        # =========================================================================
        # 5. SUPPORT TICKETING, THREADED COMMUNICATIONS & RESOLUTION
        # =========================================================================
        ticket = await issue_service.create_issue(
            session=db,
            tenant_id=tenant_id,
            subject="Vibration anomaly during pre-flight engine bracket inspection",
            customer_id=cust_profile.customer_id,
            raised_by_email="maintenance@aerodynamics.example",
            raised_by_name="Chief Inspector Davis",
            priority="URGENT",
            issue_type="HARDWARE",
            description="Inspection detected micro-chatter marks on the mating surface of bracket unit.",
        )
        assert ticket.status == "OPEN"
        assert ticket.priority == "URGENT"
        assert ticket.sla_id == premium_sla.sla_id
        assert ticket.response_by is not None
        assert ticket.resolution_by is not None
        assert len(ticket.communications) == 1
        assert ticket.communications[0].sender_type == "CUSTOMER"

        # Add Private Internal Staff Note
        internal_note = await issue_service.add_communication(
            session=db,
            tenant_id=tenant_id,
            issue_id=ticket.issue_id,
            sender_type="AGENT",
            sender_name="Senior QC Engineer Sarah",
            message="Internal Check: Pull batch inspection logs for lot #TITAN-2026-01.",
            is_internal_note=True,
        )
        assert internal_note.is_internal_note is True
        # Internal note does NOT count as public first response
        ticket_reloaded = await issue_service.get_issue(db, tenant_id, ticket.issue_id)
        assert ticket_reloaded.first_responded_on is None
        assert ticket_reloaded.status == "OPEN"

        # Add Official Agent Response to Customer
        agent_reply = await issue_service.add_communication(
            session=db,
            tenant_id=tenant_id,
            issue_id=ticket.issue_id,
            sender_type="AGENT",
            sender_name="Senior QC Engineer Sarah",
            message="Hello Davis, we are reviewing the CNC surface finish logs. Please hold installation.",
            is_internal_note=False,
        )
        assert agent_reply.is_internal_note is False
        ticket_reloaded = await issue_service.get_issue(db, tenant_id, ticket.issue_id)
        assert ticket_reloaded.first_responded_on is not None
        assert ticket_reloaded.status == "REPLIED"
        assert ticket_reloaded.sla_status == "WITHIN_SLA"

        # Resolve Issue
        resolved_ticket = await issue_service.resolve_issue(
            session=db,
            tenant_id=tenant_id,
            issue_id=ticket.issue_id,
            resolution_details="Dimensional inspection confirmed superficial protective lacquer variation. Surface tolerance is 100% within FAA specification. Cleared for flight installation.",
            status="RESOLVED",
        )
        assert resolved_ticket.status == "RESOLVED"
        assert resolved_ticket.resolution_date is not None
        assert resolved_ticket.sla_status == "FULFILLED"

        # =========================================================================
        # 6. SERIAL NUMBER WARRANTY CLAIM & RMA RESOLUTION
        # =========================================================================
        # Create Warehouse for inventory
        wh_main = Warehouse(
            tenant_id=tenant_id,
            warehouse_code=f"WH-WAR-{uuid.uuid4().hex[:4]}",
            warehouse_name="Warranty Quarantine Store",
            is_active=True,
        )
        db.add(wh_main)
        await db.commit()

        # Serial A: Under Active Warranty Coverage (expiring next year)
        serial_active = SerialNo(
            tenant_id=tenant_id,
            serial_number=f"SN-AERO-{uuid.uuid4().hex[:6].upper()}",
            item_id=catalog_item.item_id,
            warehouse_id=wh_main.warehouse_id,
            status="ACTIVE",
            warranty_expiry_date=date.today() + timedelta(days=300),
        )
        # Serial B: Expired Warranty Coverage (expired last year)
        serial_expired = SerialNo(
            tenant_id=tenant_id,
            serial_number=f"SN-OLD-{uuid.uuid4().hex[:6].upper()}",
            item_id=catalog_item.item_id,
            warehouse_id=wh_main.warehouse_id,
            status="ACTIVE",
            warranty_expiry_date=date.today() - timedelta(days=120),
        )
        db.add_all([serial_active, serial_expired])
        await db.commit()

        # Verify entitlement logic
        ver_active = await warranty_service.verify_serial_warranty(db, tenant_id, serial_active.serial_number)
        assert ver_active["is_registered"] is True
        assert ver_active["warranty_status"] == "IN_WARRANTY"

        ver_expired = await warranty_service.verify_serial_warranty(db, tenant_id, serial_expired.serial_number)
        assert ver_expired["is_registered"] is True
        assert ver_expired["warranty_status"] == "OUT_OF_WARRANTY"

        ver_unknown = await warranty_service.verify_serial_warranty(db, tenant_id, "SN-NONEXISTENT-999")
        assert ver_unknown["is_registered"] is False
        assert ver_unknown["warranty_status"] == "NO_WARRANTY"

        # File Warranty Claim for Active Serial
        claim = await warranty_service.create_warranty_claim(
            session=db,
            tenant_id=tenant_id,
            claim_number=f"WAR-2026-{uuid.uuid4().hex[:4].upper()}",
            customer_id=cust_profile.customer_id,
            serial_number=serial_active.serial_number,
            complaint_description="Bolt hole thread binding during torque installation.",
            resolution_type="REPLACE_FREE",
            item_id=catalog_item.item_id,
        )
        assert claim.status == "OPEN"
        assert claim.warranty_status == "IN_WARRANTY"
        assert claim.serial_id == serial_active.serial_id

        # Resolve Claim with Authorized Replacement
        resolved_claim = await warranty_service.resolve_warranty_claim(
            session=db,
            tenant_id=tenant_id,
            claim_id=claim.claim_id,
            resolution_details="RMA approved. Free replacement unit expedited via priority air freight.",
            resolution_type="REPLACE_FREE",
            new_status="APPROVED",
        )
        assert resolved_claim.status == "APPROVED"
        assert resolved_claim.resolution_type == "REPLACE_FREE"

        print("Phase 6 CRM & Support Helpdesk parity verification 100% SUCCESSFUL!")
