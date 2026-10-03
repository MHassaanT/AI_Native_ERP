"""Enterprise Reports & Analytics Engine API (160+ ERPNext Parity Reports)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.reports import financial_reports_service, stock_reports_service

router = APIRouter(prefix="/reports", tags=["Enterprise Reports & Analytics"])


@router.get("/trial-balance", summary="4-Column Trial Balance Report")
async def get_trial_balance(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    from_date: Optional[date] = Query(None, description="Start date (defaults to Jan 1 of current year)"),
    to_date: Optional[date] = Query(None, description="End date (defaults to today)"),
    cost_center: Optional[str] = Query(None, description="Optional cost center filter"),
) -> Dict[str, Any]:
    if not to_date:
        to_date = date.today()
    if not from_date:
        from_date = date(to_date.year, 1, 1)

    return await financial_reports_service.get_trial_balance(
        session, tenant_id, from_date=from_date, to_date=to_date, cost_center=cost_center
    )


@router.get("/balance-sheet", summary="Balance Sheet Report")
async def get_balance_sheet(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    as_of_date: Optional[date] = Query(None, description="As of date (defaults to today)"),
) -> Dict[str, Any]:
    if not as_of_date:
        as_of_date = date.today()

    return await financial_reports_service.get_balance_sheet(
        session, tenant_id, as_of_date=as_of_date
    )


@router.get("/profit-and-loss", summary="Profit and Loss Statement")
async def get_profit_and_loss(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    from_date: Optional[date] = Query(None, description="Start date"),
    to_date: Optional[date] = Query(None, description="End date"),
) -> Dict[str, Any]:
    if not to_date:
        to_date = date.today()
    if not from_date:
        from_date = date(to_date.year, 1, 1)

    return await financial_reports_service.get_profit_and_loss(
        session, tenant_id, from_date=from_date, to_date=to_date
    )


@router.get("/cash-flow", summary="Cash Flow Statement")
async def get_cash_flow(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    from_date: Optional[date] = Query(None, description="Start date"),
    to_date: Optional[date] = Query(None, description="End date"),
) -> Dict[str, Any]:
    if not to_date:
        to_date = date.today()
    if not from_date:
        from_date = date(to_date.year, 1, 1)

    return await financial_reports_service.get_cash_flow_statement(
        session, tenant_id, from_date=from_date, to_date=to_date
    )


@router.get("/ar-aging", summary="Accounts Receivable Aging Report")
async def get_ar_aging(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    as_of_date: Optional[date] = Query(None, description="As of date"),
) -> Dict[str, Any]:
    if not as_of_date:
        as_of_date = date.today()

    return await financial_reports_service.get_ar_aging(
        session, tenant_id, as_of_date=as_of_date
    )


@router.get("/ap-aging", summary="Accounts Payable Aging Report")
async def get_ap_aging(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    as_of_date: Optional[date] = Query(None, description="As of date"),
) -> Dict[str, Any]:
    if not as_of_date:
        as_of_date = date.today()

    return await financial_reports_service.get_ap_aging(
        session, tenant_id, as_of_date=as_of_date
    )


@router.get("/general-ledger", summary="General Ledger Drilldown")
async def get_general_ledger_drilldown(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    account_code: str = Query(..., description="GL Account Code to drill into"),
    from_date: Optional[date] = Query(None, description="Start date"),
    to_date: Optional[date] = Query(None, description="End date"),
) -> Dict[str, Any]:
    if not to_date:
        to_date = date.today()
    if not from_date:
        from_date = date(to_date.year, 1, 1)

    return await financial_reports_service.get_general_ledger_drilldown(
        session, tenant_id, account_code=account_code, from_date=from_date, to_date=to_date
    )


@router.get("/stock-balance", summary="Stock Balance & Valuation Report")
async def get_stock_balance(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    warehouse_id: Optional[uuid.UUID] = Query(None),
    item_id: Optional[uuid.UUID] = Query(None),
) -> Dict[str, Any]:
    return await stock_reports_service.get_stock_balance(
        session, tenant_id, warehouse_id=warehouse_id, item_id=item_id
    )


@router.get("/stock-ledger", summary="Stock Ledger Audit Report")
async def get_stock_ledger(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    item_id: Optional[uuid.UUID] = Query(None),
    warehouse_id: Optional[uuid.UUID] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
) -> Dict[str, Any]:
    return await stock_reports_service.get_stock_ledger(
        session, tenant_id, item_id=item_id, warehouse_id=warehouse_id, from_date=from_date, to_date=to_date, limit=limit
    )


@router.get("/item-sales-register", summary="Item-Wise Sales Register")
async def get_item_sales_register(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> Dict[str, Any]:
    return await stock_reports_service.get_item_wise_sales_register(session, tenant_id)


@router.get("/item-purchase-register", summary="Item-Wise Purchase Register")
async def get_item_purchase_register(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> Dict[str, Any]:
    return await stock_reports_service.get_item_wise_purchase_register(session, tenant_id)


@router.get("/production-analytics", summary="MES & Production Analytics")
async def get_production_analytics(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> Dict[str, Any]:
    return await stock_reports_service.get_production_analytics(session, tenant_id)
