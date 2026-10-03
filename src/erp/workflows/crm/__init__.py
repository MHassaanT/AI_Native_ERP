"""CRM Workflow Domain Services Package."""

from erp.workflows.crm.campaign_service import CampaignService, campaign_service
from erp.workflows.crm.lead_service import LeadService, lead_service
from erp.workflows.crm.opportunity_service import OpportunityService, opportunity_service

__all__ = [
    "LeadService",
    "lead_service",
    "OpportunityService",
    "opportunity_service",
    "CampaignService",
    "campaign_service",
]
