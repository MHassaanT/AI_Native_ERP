"""Continuous Bank Reconciliation API Endpoints."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.sales import Customer, SalesOrder
from erp.workflows.reconciliation.auto_clear import (
    AutoClearResult,
    auto_clearing_engine,
)
from erp.workflows.reconciliation.bank_feed_ingestor import (
    bank_feed_ingestor,
)

router = APIRouter(prefix="/reconciliation", tags=["Bank Reconciliation"])


class IngestBankFeedRequest(BaseModel):
    account_number: str = "ACC-OPERATING-01"
    amount: Decimal
    counterparty_name: str
    remittance_information: str = ""
    currency: str = "USD"


class CreateSalesOrderReceivableRequest(BaseModel):
    order_number: str = Field(..., min_length=2, max_length=64)
    customer_name: str = Field(..., min_length=2, max_length=255)
    total_amount: Decimal
    order_date: date = Field(default_factory=date.today)
    delivery_date: date = Field(default_factory=date.today)


@router.get("/orders", summary="List open sales receivables for reconciliation")
async def list_open_receivables(tenant_id: TenantIdDep, db: DbSessionDep):
    """Lists sales orders and their customer counterparties."""
    stmt = (
        select(SalesOrder, Customer.customer_name, Customer.customer_code)
        .join(Customer, SalesOrder.customer_id == Customer.customer_id)
        .where(SalesOrder.tenant_id == tenant_id)
        .order_by(SalesOrder.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    results = []
    for order, cust_name, cust_code in rows:
        results.append(
            {
                "order_id": str(order.order_id),
                "order_number": order.order_number,
                "customer_name": cust_name,
                "customer_code": cust_code,
                "order_date": order.order_date.isoformat(),
                "delivery_date": order.delivery_date.isoformat(),
                "total_amount": str(order.total_amount),
                "status": order.status,
            }
        )
    return results


@router.post(
    "/orders", status_code=status.HTTP_201_CREATED, summary="Create sales order receivable"
)
async def create_sales_order_receivable(
    req: CreateSalesOrderReceivableRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Creates a sales order for a customer so incoming wire transfers can be matched."""
    cust = (
        (
            await db.execute(
                select(Customer).where(
                    Customer.tenant_id == tenant_id,
                    Customer.customer_name == req.customer_name,
                )
            )
        )
        .scalars()
        .first()
    )

    if not cust:
        # Auto-create customer if does not exist
        cust = Customer(
            tenant_id=tenant_id,
            customer_code=f"CUST-{req.customer_name[:6].upper().replace(' ', '-')}",
            customer_name=req.customer_name,
            credit_limit=Decimal("500000.00"),
            lifetime_value=Decimal("0.0000"),
            is_active=True,
        )
        db.add(cust)
        await db.flush()

    so = SalesOrder(
        tenant_id=tenant_id,
        order_number=req.order_number,
        customer_id=cust.customer_id,
        order_date=req.order_date,
        delivery_date=req.delivery_date,
        total_amount=req.total_amount,
        status="CONFIRMED",
    )
    db.add(so)
    await db.flush()
    return so


@router.post(
    "/feed",
    response_model=AutoClearResult,
    summary="Ingest open-banking transaction feed item",
)
async def ingest_bank_feed_transaction(
    req: IngestBankFeedRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Ingests a real-time bank settlement. Automatically posts clearing entries if confidence >= 0.92."""
    raw_tx = bank_feed_ingestor.parse_webhook_payload(req.model_dump())
    return await auto_clearing_engine.process_bank_transaction(
        session=db,
        tenant_id=tenant_id,
        tx=raw_tx,
    )
