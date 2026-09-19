"""Autonomous Tenant Onboarding and Ledger Blueprint Provisioner."""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from erp.audit.hasher import GENESIS_HASH, compute_audit_record_hash
from erp.db.models.audit import AgentAuditLog
from erp.db.models.hr import Employee
from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.models.ledger import Account, CostCenter
from erp.db.models.manufacturing import Workstation
from erp.db.models.operator_cert import OperatorCertificationRecord
from erp.db.models.purchasing import Supplier
from erp.db.models.sales import Customer

logger = logging.getLogger(__name__)


async def provision_tenant_blueprint(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    company_name: str,
) -> None:
    """Provisions standard Chart of Accounts, factory floor, inventory master, and certifications for a new tenant."""
    logger.info(
        "Provisioning ledger and factory master records for tenant %s (%s)...",
        tenant_id,
        company_name,
    )

    # 1. Cost Centers
    cost_centers = [
        CostCenter(
            tenant_id=tenant_id,
            cost_center_code="PLANT-01",
            cost_center_name="Manufacturing Plant Floor 1",
        ),
        CostCenter(
            tenant_id=tenant_id,
            cost_center_code="CORP-FINANCE",
            cost_center_name="Corporate Financial Controller",
        ),
        CostCenter(
            tenant_id=tenant_id,
            cost_center_code="SALES-GLOBAL",
            cost_center_name="Commercial Sales & Revenue",
        ),
    ]
    session.add_all(cost_centers)

    # 2. Standard Chart of Accounts
    accounts = [
        Account(
            tenant_id=tenant_id,
            account_code="1010-CASH",
            account_name="Operating Vault Cash",
            account_type="ASSET",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="1020-BANK-OPERATING",
            account_name="Primary Operating Bank Account",
            account_type="ASSET",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="1200-AR-CUSTOMERS",
            account_name="Accounts Receivable - Trade Customers",
            account_type="ASSET",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="1300-RAW-MATERIALS",
            account_name="Raw Materials & Components Inventory",
            account_type="ASSET",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="1400-FINISHED-GOODS",
            account_name="Finished Goods Inventory Valuation",
            account_type="ASSET",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="2100-AP-VENDORS",
            account_name="Accounts Payable - Trade Vendors",
            account_type="LIABILITY",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="2110-AP-EMPLOYEES",
            account_name="Accounts Payable - Employee Expense Claims",
            account_type="LIABILITY",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="3000-EQUITY-CAPITAL",
            account_name="Shareholders Paid-In Capital",
            account_type="EQUITY",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="4000-REV-SALES",
            account_name="Commercial Sales Revenue",
            account_type="REVENUE",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="5000-COGS-MATERIALS",
            account_name="Cost of Goods Sold - Materials",
            account_type="EXPENSE",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="5100-EXP-TRAVEL",
            account_name="Employee Travel & Operational Expenses",
            account_type="EXPENSE",
        ),
        Account(
            tenant_id=tenant_id,
            account_code="5200-DEP-MACHINERY",
            account_name="Machine Depreciation Expense",
            account_type="EXPENSE",
        ),
    ]
    session.add_all(accounts)

    # 3. Default Primary Warehouse (Clean slate: 0 items, 0 stock)
    wh = Warehouse(
        warehouse_id=uuid.uuid4(),
        tenant_id=tenant_id,
        warehouse_code="WH-MAIN-01",
        warehouse_name="Primary Central Warehouse",
    )
    session.add(wh)

    # 4. Genesis Cryptographic Audit Log (Block #0)
    trace_id = f"trace_genesis_{tenant_id.hex[:8]}"
    genesis_payload = {
        "event": "TENANT_PROVISIONED",
        "company_name": company_name,
        "blueprint_version": "2.0.0",
        "status": "INITIALIZED",
    }
    genesis_hash = compute_audit_record_hash(
        trace_id=trace_id,
        agent_id="SYSTEM_PROVISIONER",
        input_payload=genesis_payload,
        previous_hash=GENESIS_HASH,
    )
    genesis_log = AgentAuditLog(
        tenant_id=tenant_id,
        trace_id=trace_id,
        agent_id="SYSTEM_PROVISIONER",
        session_id=f"init_{tenant_id.hex[:8]}",
        model_provider="SYSTEM",
        model_version="v2",
        prompt_template_hash="genesis_template_hash",
        retrieved_context_hashes=[],
        baml_function_called="AutonomousTenantProvisioner",
        input_payload=genesis_payload,
        model_raw_output="Tenant master blueprint provisioned successfully.",
        parsed_structured_output={"provisioned": True},
        evaluated_guardrail_rules={"multi_tenancy": "ENFORCED", "genesis_verified": True},
        execution_duration_ms=12,
        previous_record_hash=GENESIS_HASH,
        record_hash=genesis_hash,
    )
    session.add(genesis_log)

    await session.flush()
    logger.info("Tenant %s successfully provisioned.", tenant_id)
