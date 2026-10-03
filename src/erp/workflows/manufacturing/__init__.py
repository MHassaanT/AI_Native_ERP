"""Manufacturing and MES Domain Workflows."""

from erp.workflows.manufacturing.bom_service import BOMService, bom_service
from erp.workflows.manufacturing.job_card_service import JobCardService, job_card_service
from erp.workflows.manufacturing.mrp_service import MRPService, mrp_service
from erp.workflows.manufacturing.oee_service import OEEService, oee_service
from erp.workflows.manufacturing.work_order_service import (
    WorkOrderService,
    work_order_service,
)

__all__ = [
    "BOMService",
    "bom_service",
    "MRPService",
    "mrp_service",
    "WorkOrderService",
    "work_order_service",
    "JobCardService",
    "job_card_service",
    "OEEService",
    "oee_service",
]
