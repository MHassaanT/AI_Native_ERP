"""Currency Exchange Rates and Revaluation API."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.workflows.currency import exchange_service

router = APIRouter(prefix="/currency", tags=["Currency Exchange & Revaluation"])


class SetExchangeRateSchema(BaseModel):
    from_currency: str
    to_currency: str
    exchange_rate: Decimal = Field(gt=0)
    effective_date: Optional[date] = None


class RunRevaluationSchema(BaseModel):
    posting_date: Optional[date] = None
    base_currency: str = "USD"
    notes: Optional[str] = None


@router.post("/rates", status_code=status.HTTP_201_CREATED, summary="Set Exchange Rate")
async def set_exchange_rate(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    payload: SetExchangeRateSchema,
) -> Dict[str, Any]:
    rate = await exchange_service.set_exchange_rate(
        session=session,
        tenant_id=tenant_id,
        from_currency=payload.from_currency,
        to_currency=payload.to_currency,
        exchange_rate=payload.exchange_rate,
        effective_date=payload.effective_date,
    )
    return {
        "rate_id": str(rate.rate_id),
        "from_currency": rate.from_currency,
        "to_currency": rate.to_currency,
        "exchange_rate": rate.exchange_rate,
        "effective_date": rate.effective_date,
    }


@router.get("/rates", summary="List Exchange Rates")
async def list_exchange_rates(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> List[Dict[str, Any]]:
    rates = await exchange_service.list_exchange_rates(session, tenant_id)
    return [
        {
            "rate_id": str(r.rate_id),
            "from_currency": r.from_currency,
            "to_currency": r.to_currency,
            "exchange_rate": r.exchange_rate,
            "effective_date": r.effective_date,
        }
        for r in rates
    ]


@router.get("/rates/latest", summary="Get Latest Rate for Pair")
async def get_latest_rate(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    from_currency: str = Query(..., description="From currency code"),
    to_currency: str = Query(..., description="To currency code"),
    as_of_date: Optional[date] = Query(None),
) -> Dict[str, Any]:
    rate = await exchange_service.get_latest_rate(
        session, tenant_id, from_currency=from_currency, to_currency=to_currency, as_of_date=as_of_date
    )
    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "exchange_rate": rate,
    }


@router.post("/revaluation", status_code=status.HTTP_201_CREATED, summary="Execute Exchange Rate Revaluation")
async def execute_revaluation(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
    payload: RunRevaluationSchema,
) -> Dict[str, Any]:
    posting_date = payload.posting_date or date.today()
    rev = await exchange_service.execute_exchange_revaluation(
        session=session,
        tenant_id=tenant_id,
        posting_date=posting_date,
        base_currency=payload.base_currency,
        notes=payload.notes,
    )
    return {
        "revaluation_id": str(rev.revaluation_id),
        "revaluation_number": rev.revaluation_number,
        "posting_date": rev.posting_date,
        "total_gain_loss": rev.total_gain_loss,
        "journal_entry_id": str(rev.journal_entry_id) if rev.journal_entry_id else None,
        "notes": rev.notes,
    }


@router.get("/revaluation", summary="List Exchange Rate Revaluations")
async def list_revaluations(
    session: DbSessionDep,
    tenant_id: TenantIdDep,
) -> List[Dict[str, Any]]:
    revs = await exchange_service.list_revaluations(session, tenant_id)
    return [
        {
            "revaluation_id": str(r.revaluation_id),
            "revaluation_number": r.revaluation_number,
            "posting_date": r.posting_date,
            "total_gain_loss": r.total_gain_loss,
            "journal_entry_id": str(r.journal_entry_id) if r.journal_entry_id else None,
            "notes": r.notes,
        }
        for r in revs
    ]
