"""Autonomous Sales SDR & CRM Pipeline Agent."""

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.agents.channels.communications import dispatcher
from erp.agents.core.llm_gateway import llm_gateway
from erp.db.models.agents import (
    AgentDefinition,
    AgentDomain,
    AgentExecutionRun,
    AgentStepLog,
)
from erp.db.models.crm import Lead, Opportunity
from erp.db.session import async_session_factory
from erp.workflows.crm.lead_service import LeadService
from erp.workflows.crm.opportunity_service import OpportunityService

logger = logging.getLogger(__name__)


class SalesSDRAgent:
    """Automates lead qualification, personalized pitch generation, and quotation stages."""

    SLUG = "sales_sdr_agent"

    async def execute_cycle(
        self,
        tenant_id: uuid.UUID,
        trigger_type: str = "SCHEDULED",
        trigger_context: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionRun:
        """Processes uncontacted leads and advances qualified opportunities."""
        start_time = datetime.now(timezone.utc)
        run_id = uuid.uuid4()
        step_num = 1

        async with async_session_factory() as session:
            # 1. Fetch agent definition
            res = await session.execute(
                select(AgentDefinition).where(
                    AgentDefinition.tenant_id == tenant_id,
                    AgentDefinition.slug == self.SLUG,
                )
            )
            agent_def = res.scalar_one_or_none()
            if not agent_def:
                raise ValueError(f"Agent definition '{self.SLUG}' is not provisioned for tenant {tenant_id}.")
            if not agent_def.is_active or agent_def.autonomy_level.value == "DISABLED":
                raise ValueError(f"Agent '{agent_def.name}' is disabled.")
            agent_id = agent_def.agent_id

            run = AgentExecutionRun(
                run_id=run_id,
                tenant_id=tenant_id,
                agent_id=agent_id,
                agent_name="Autonomous Sales SDR & CRM Pipeline Agent",
                trigger_type=trigger_type,
                trigger_context=trigger_context or {},
                status="RUNNING",
                started_at=start_time,
            )
            session.add(run)
            await session.commit()

            # STEP 1: Query open uncontacted leads
            leads_res = await session.execute(
                select(Lead).where(
                    Lead.tenant_id == tenant_id,
                    Lead.status.in_(["LEAD", "OPEN", "QUALIFICATION"]),
                ).limit(5)
            )
            leads = leads_res.scalars().all()

            step1_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="scan_crm_leads",
                reasoning_thought=f"Identified {len(leads)} active pipeline leads requiring evaluation.",
                tool_name="query_leads",
                tool_arguments={"tenant_id": str(tenant_id)},
                tool_output={"open_leads_count": len(leads)},
                status="COMPLETED",
                duration_ms=30,
            )
            session.add(step1_log)
            step_num += 1

            if not leads:
                run.status = "COMPLETED"
                run.summary = "No open leads in qualification queue. Pipeline fully up to date."
                run.completed_at = datetime.now(timezone.utc)
                await session.commit()
                return run

            target_lead = leads[0]

            # STEP 2: Gemini ICP Qualification & Pitch Generation
            lead_summary = {
                "name": target_lead.lead_name,
                "company": target_lead.company_name,
                "email": target_lead.email_id,
                "industry": getattr(target_lead, "industry", "General"),
            }

            llm_res = await llm_gateway.ainvoke_json(
                prompt=f"Qualify this lead against enterprise ICP and generate a personalized WhatsApp/Email pitch. Lead: {lead_summary}. Return JSON with 'icp_score' (1-100), 'is_qualified' (boolean), 'pitch_text', and 'recommended_deal_size'.",
                system_prompt="You are a high-performing enterprise Sales SDR."
            )
            try:
                icp_score = float(llm_res.get("icp_score"))
                if not math.isfinite(icp_score) or not 1 <= icp_score <= 100:
                    icp_score = None
            except (TypeError, ValueError):
                icp_score = None
            pitch_text = llm_res.get("pitch_text")
            if not isinstance(pitch_text, str) or not pitch_text.strip() or len(pitch_text) > 4000:
                pitch_text = (
                    f"Hello {target_lead.lead_name}, we'd be glad to discuss workflow improvements "
                    f"for {target_lead.company_name or 'your organization'}."
                )

            step2_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="icp_qualification_and_pitch",
                reasoning_thought=f"Lead scored {icp_score if icp_score is not None else 'unavailable'}/100 ICP fit. Qualified: {llm_res.get('is_qualified') is True}.",
                tool_name="llm_qualify_and_pitch",
                tool_arguments=lead_summary,
                tool_output=llm_res,
                status="COMPLETED",
                duration_ms=480,
            )
            session.add(step2_log)
            step_num += 1

            # STEP 3: Dispatch Personalized Outreach
            phone = target_lead.phone or target_lead.mobile_no
            email = target_lead.email_id
            communication = None
            if phone:
                communication = await dispatcher.send_whatsapp(
                    tenant_id=tenant_id,
                    agent_name="Sales SDR Agent",
                    to_phone=phone,
                    message=pitch_text,
                    run_id=run_id,
                    metadata={"lead_id": str(target_lead.lead_id), "icp_score": llm_res.get("icp_score")},
                )
            elif email:
                communication = await dispatcher.send_gmail(
                    tenant_id=tenant_id,
                    agent_name="Sales SDR Agent",
                    to_email=email,
                    subject=f"Follow-up for {target_lead.company_name or target_lead.lead_name}",
                    body=pitch_text,
                    run_id=run_id,
                    metadata={"lead_id": str(target_lead.lead_id), "icp_score": llm_res.get("icp_score")},
                )
            delivery_status = communication.status if communication else "SKIPPED"
            recipient = phone or email

            step3_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="dispatch_outreach",
                reasoning_thought=(
                    f"Outreach delivery status for {target_lead.lead_name}: {delivery_status}."
                    if communication
                    else f"Outreach was not attempted for {target_lead.lead_name}; no contact details are configured."
                ),
                tool_name=("dispatch_whatsapp" if phone else "dispatch_gmail") if communication else "outreach_not_configured",
                tool_arguments={"recipient": recipient} if recipient else {},
                tool_output={"message_sent": delivery_status == "SENT", "status": delivery_status},
                status="COMPLETED" if delivery_status == "SENT" else ("FAILED" if communication else "SKIPPED"),
                duration_ms=0,
            )
            session.add(step3_log)
            step_num += 1

            # STEP 4: Advance Lead Stage in CRM
            qualified = llm_res.get("is_qualified") is True and icp_score is not None
            if qualified:
                target_lead.status = "INTERESTED"
                session.add(target_lead)

            run.status = "COMPLETED"
            run.summary = (
                f"Evaluated lead '{target_lead.lead_name}' (ICP Score: {icp_score if icp_score is not None else 'unavailable'}/100). "
                f"Outreach status: {delivery_status}. "
                + ("Lead progressed to INTERESTED." if qualified else "Lead was not progressed.")
            )
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(run)
            return run


sales_sdr_agent = SalesSDRAgent()
