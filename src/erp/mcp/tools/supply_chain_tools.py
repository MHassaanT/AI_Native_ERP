"""Supply Chain and ROP MCP Tool Bindings."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.supply_chain.rop_engine import rop_engine


async def tool_calculate_dynamic_rop(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for calculating dynamic Reorder Point (ROP) with Z=2.33 safety stock."""
    item_code = arguments["item_code"]
    mu_d = Decimal(str(arguments["daily_demand_mean"]))
    sigma_d = Decimal(str(arguments["daily_demand_std"]))
    mu_l = Decimal(str(arguments["lead_time_mean_days"]))
    sigma_l = Decimal(str(arguments["lead_time_std_days"]))

    res = rop_engine.calculate_rop(
        item_code=item_code,
        mu_d=mu_d,
        sigma_d=sigma_d,
        mu_l=mu_l,
        sigma_l=sigma_l,
    )
    return res.model_dump(mode="json")
