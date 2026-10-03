"""Multi-Company Group Consolidation API."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.companies import company_service

router = APIRouter(prefix="/companies", tags=["Multi-Company Consolidation"])


class CreateCompanySchema(BaseModel):
    company_name: str
    company_code: str
    default_currency: str = "USD"
    parent_company_id: Optional[uuid.UUID] = None
    is_group: bool = False
    tax_id: Optional[str] = None


class CreateInterCompanyTransactionSchema(BaseModel):
    from_company_id: uuid.UUID
    to_company_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    transaction_type: str  # INVOICE, LOAN, TRANSFER, CHARGE
    currency: str = "USD"
    reference_voucher_type: Optional[str] = None
    reference_voucher_id: Optional[uuid.UUID] = None
    transaction_date: Optional[date] = None


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create Company")
async def create_company(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    payload: CreateCompanySchema,
) -> Dict[str, Any]:
    comp = await company_service.create_company(
        session=session,
        tenant_id=tenant_id,
        company_name=payload.company_name,
        company_code=payload.company_code,
        default_currency=payload.default_currency,
        parent_company_id=payload.parent_company_id,
        is_group=payload.is_group,
        tax_id=payload.tax_id,
    )
    return {
        "company_id": str(comp.company_id),
        "company_name": comp.company_name,
        "company_code": comp.company_code,
        "default_currency": comp.default_currency,
        "is_group": comp.is_group,
        "parent_company_id": str(comp.parent_company_id) if comp.parent_company_id else None,
    }


@router.get("", summary="List Companies and Structure")
async def list_companies(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> List[Dict[str, Any]]:
    comps = await company_service.list_companies(session, tenant_id)
    return [
        {
            "company_id": str(c.company_id),
            "company_name": c.company_name,
            "company_code": c.company_code,
            "default_currency": c.default_currency,
            "parent_company_id": str(c.parent_company_id) if c.parent_company_id else None,
            "is_group": c.is_group,
            "tax_id": c.tax_id,
            "is_active": c.is_active,
            "subsidiaries": [
                {
                    "company_id": str(s.company_id),
                    "company_name": s.company_name,
                    "company_code": s.company_code,
                }
                for s in c.subsidiaries
            ],
        }
        for c in comps
    ]


@router.post("/transactions", status_code=status.HTTP_201_CREATED, summary="Record Inter-Company Transaction")
async def create_inter_company_tx(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    payload: CreateInterCompanyTransactionSchema,
) -> Dict[str, Any]:
    tx = await company_service.record_inter_company_transaction(
        session=session,
        tenant_id=tenant_id,
        from_company_id=payload.from_company_id,
        to_company_id=payload.to_company_id,
        amount=payload.amount,
        transaction_type=payload.transaction_type,
        currency=payload.currency,
        reference_voucher_type=payload.reference_voucher_type,
        reference_voucher_id=payload.reference_voucher_id,
        transaction_date=payload.transaction_date,
    )
    return {
        "transaction_id": str(tx.transaction_id),
        "from_company_id": str(tx.from_company_id),
        "to_company_id": str(tx.to_company_id),
        "amount": tx.amount,
        "currency": tx.currency,
        "transaction_type": tx.transaction_type,
        "is_eliminated": tx.is_eliminated,
    }


@router.get("/transactions", summary="List Inter-Company Transactions")
async def list_inter_company_tx(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    is_eliminated: Optional[bool] = Query(None),
) -> List[Dict[str, Any]]:
    txs = await company_service.list_inter_company_transactions(session, tenant_id, is_eliminated=is_eliminated)
    return [
        {
            "transaction_id": str(t.transaction_id),
            "from_company_id": str(t.from_company_id),
            "from_company_name": t.from_company.company_name if t.from_company else None,
            "to_company_id": str(t.to_company_id),
            "to_company_name": t.to_company.company_name if t.to_company else None,
            "amount": t.amount,
            "currency": t.currency,
            "transaction_type": t.transaction_type,
            "transaction_date": t.transaction_date,
            "is_eliminated": t.is_eliminated,
        }
        for t in txs
    ]


@router.get("/consolidated-trial-balance", summary="Consolidated Trial Balance with Eliminations")
async def get_consolidated_trial_balance(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
) -> Dict[str, Any]:
    if not to_date:
        to_date = date.today()
    if not from_date:
        from_date = date(to_date.year, 1, 1)

    return await company_service.get_consolidated_trial_balance(
        session, tenant_id, from_date=from_date, to_date=to_date
    )
