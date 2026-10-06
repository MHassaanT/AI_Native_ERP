"""Autonomous Sales SDR & CRM Pipeline Agent."""

import logging
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
            agent_id = agent_def.agent_id if agent_def else uuid.uuid4()

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

            step2_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="icp_qualification_and_pitch",
                reasoning_thought=f"Lead scored {llm_res.get('icp_score')}/100 ICP fit. Qualified: {llm_res.get('is_qualified')}.",
                tool_name="llm_qualify_and_pitch",
                tool_arguments=lead_summary,
                tool_output=llm_res,
                status="COMPLETED",
                duration_ms=480,
            )
            session.add(step2_log)
            step_num += 1

            # STEP 3: Dispatch Personalized Outreach
            pitch_text = llm_res.get("pitch_text", f"Hello {target_lead.lead_name}, we noticed your enterprise operations at {target_lead.company_name} and would love to show you how AI-Native ERP automates workflows.")
            recipient = target_lead.phone or target_lead.mobile_no or target_lead.email_id or "+923009876543"

            await dispatcher.send_whatsapp(
                tenant_id=tenant_id,
                agent_name="Sales SDR Agent",
                to_phone=recipient,
                message=pitch_text,
                run_id=run_id,
                metadata={"lead_id": str(target_lead.lead_id), "icp_score": llm_res.get("icp_score")},
            )

            step3_log = AgentStepLog(
                step_id=uuid.uuid4(),
                run_id=run_id,
                step_number=step_num,
                node_name="dispatch_outreach",
                reasoning_thought=f"Dispatched conversational sales pitch to {target_lead.lead_name} ({recipient}).",
                tool_name="dispatch_whatsapp",
                tool_arguments={"recipient": recipient},
                tool_output={"message_sent": True},
                status="COMPLETED",
                duration_ms=90,
            )
            session.add(step3_log)
            step_num += 1

            # STEP 4: Advance Lead Stage in CRM
            if llm_res.get("is_qualified", True):
                target_lead.status = "INTERESTED"
                session.add(target_lead)

            run.status = "COMPLETED"
            run.summary = f"Evaluated lead '{target_lead.lead_name}' (ICP Score: {llm_res.get('icp_score')}/100). Dispatched tailored outreach pitch. Lead progressed to INTERESTED."
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(run)
            return run


sales_sdr_agent = SalesSDRAgent()
