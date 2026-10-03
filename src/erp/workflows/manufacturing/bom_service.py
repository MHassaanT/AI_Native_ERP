"""BOM and Routing Service: Multi-level BOM hierarchy, scrap tracking, and unit cost rollup."""

from decimal import Decimal
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item
from erp.db.models.manufacturing import (
    BOM,
    BOMItem,
    BOMOperation,
    BOMScrapItem,
    Operation,
    Routing,
    RoutingOperation,
    Workstation,
)

logger = logging.getLogger(__name__)


class BOMService:
    """Core domain logic for Operations, Routings, and Multi-Level Bills of Materials."""

    # --- Operation Catalog ---

    async def create_operation(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        operation_name: str,
        description: str | None = None,
        default_workstation_id: uuid.UUID | None = None,
    ) -> Operation:
        """Registers a manufacturing operation in the standard master catalog."""
        op = Operation(
            tenant_id=tenant_id,
            operation_name=operation_name.strip(),
            description=description,
            default_workstation_id=default_workstation_id,
            is_active=True,
        )
        session.add(op)
        await session.flush()
        return op

    async def list_operations(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[Operation]:
        """Lists operations for tenant."""
        stmt = (
            select(Operation)
            .options(selectinload(Operation.default_workstation))
            .where(Operation.tenant_id == tenant_id)
        )
        if active_only:
            stmt = stmt.where(Operation.is_active.is_(True))
        stmt = stmt.order_by(Operation.operation_name.asc())
        return list((await session.execute(stmt)).scalars().all())

    # --- Routings ---

    async def create_routing(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        routing_name: str,
        description: str | None = None,
        operations: list[dict[str, Any]] | None = None,
    ) -> Routing:
        """Creates a production routing sequence."""
        routing = Routing(
            tenant_id=tenant_id,
            routing_name=routing_name.strip(),
            description=description,
            is_active=True,
        )
        session.add(routing)
        await session.flush()

        if operations:
            for idx, op_data in enumerate(operations, start=1):
                op_id = uuid.UUID(str(op_data["operation_id"])) if isinstance(op_data["operation_id"], str) else op_data["operation_id"]
                ws_id = (
                    uuid.UUID(str(op_data["workstation_id"]))
                    if op_data.get("workstation_id")
                    else None
                )
                r_op = RoutingOperation(
                    tenant_id=tenant_id,
                    routing_id=routing.routing_id,
                    operation_id=op_id,
                    workstation_id=ws_id,
                    sequence_id=op_data.get("sequence_id", idx),
                    time_in_mins=Decimal(str(op_data.get("time_in_mins", "15.0000"))),
                    hourly_rate=Decimal(str(op_data.get("hourly_rate", "0.0000"))),
                    batch_size=Decimal(str(op_data.get("batch_size", "1.0000"))),
                )
                session.add(r_op)

        await session.flush()
        return await self.get_routing(session, tenant_id, routing.routing_id)  # type: ignore

    async def get_routing(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        routing_id: uuid.UUID,
    ) -> Routing | None:
        """Retrieves a routing with all sequenced operations."""
        stmt = (
            select(Routing)
            .options(
                selectinload(Routing.operations).selectinload(RoutingOperation.operation),
                selectinload(Routing.operations).selectinload(RoutingOperation.workstation),
            )
            .where(Routing.tenant_id == tenant_id, Routing.routing_id == routing_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_routings(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[Routing]:
        """Lists all routings."""
        stmt = (
            select(Routing)
            .options(
                selectinload(Routing.operations).selectinload(RoutingOperation.operation),
                selectinload(Routing.operations).selectinload(RoutingOperation.workstation),
            )
            .where(Routing.tenant_id == tenant_id)
            .order_by(Routing.routing_name.asc())
        )
        return list((await session.execute(stmt)).scalars().all())

    # --- Bill of Materials (BOM) ---

    async def create_bom(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        bom_number: str,
        item_id: uuid.UUID,
        quantity: Decimal = Decimal("1.0000"),
        routing_id: uuid.UUID | None = None,
        with_operations: bool = False,
        is_default: bool = True,
        items: list[dict[str, Any]] | None = None,
        operations: list[dict[str, Any]] | None = None,
        scrap_items: list[dict[str, Any]] | None = None,
    ) -> BOM:
        """Creates a Bill of Materials with unit cost rollup."""
        if is_default:
            # Unset default on other BOMs for same item
            existing_defaults = (
                await session.execute(
                    select(BOM).where(
                        BOM.tenant_id == tenant_id,
                        BOM.item_id == item_id,
                        BOM.is_default.is_(True),
                    )
                )
            ).scalars().all()
            for b in existing_defaults:
                b.is_default = False

        bom = BOM(
            tenant_id=tenant_id,
            bom_number=bom_number.strip(),
            item_id=item_id,
            routing_id=routing_id,
            quantity=quantity,
            with_operations=with_operations,
            is_default=is_default,
            is_active=True,
            raw_material_cost=Decimal("0.0000"),
            operating_cost=Decimal("0.0000"),
            scrap_cost=Decimal("0.0000"),
            total_cost=Decimal("0.0000"),
        )
        session.add(bom)
        await session.flush()

        raw_material_cost = Decimal("0.0000")
        if items:
            for it in items:
                comp_item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
                sub_bom_id = uuid.UUID(str(it["bom_sub_assembly_id"])) if it.get("bom_sub_assembly_id") else None
                op_id = uuid.UUID(str(it["operation_id"])) if it.get("operation_id") else None
                qty = Decimal(str(it["quantity"]))
                rate = Decimal(str(it.get("rate", "0.0000")))
                amount = qty * rate
                raw_material_cost += amount
                scrap_pct = Decimal(str(it.get("scrap_percentage", "0.00")))

                bom_item = BOMItem(
                    tenant_id=tenant_id,
                    bom_id=bom.bom_id,
                    item_id=comp_item_id,
                    bom_sub_assembly_id=sub_bom_id,
                    operation_id=op_id,
                    quantity=qty,
                    rate=rate,
                    amount=amount,
                    scrap_percentage=scrap_pct,
                )
                session.add(bom_item)

        operating_cost = Decimal("0.0000")
        # Populate operations: explicit list or pulled from routing
        ops_to_add = operations or []
        if with_operations and not ops_to_add and routing_id:
            routing = await self.get_routing(session, tenant_id, routing_id)
            if routing and routing.operations:
                ops_to_add = [
                    {
                        "operation_id": r_op.operation_id,
                        "workstation_id": r_op.workstation_id,
                        "sequence_id": r_op.sequence_id,
                        "time_in_mins": r_op.time_in_mins,
                        "hourly_rate": r_op.hourly_rate,
                        "batch_size": r_op.batch_size,
                    }
                    for r_op in routing.operations
                ]

        if ops_to_add:
            for idx, op_data in enumerate(ops_to_add, start=1):
                op_id = uuid.UUID(str(op_data["operation_id"])) if isinstance(op_data["operation_id"], str) else op_data["operation_id"]
                ws_id = uuid.UUID(str(op_data["workstation_id"])) if op_data.get("workstation_id") else None
                mins = Decimal(str(op_data.get("time_in_mins", "15.0000")))
                hr_rate = Decimal(str(op_data.get("hourly_rate", "0.0000")))
                op_cost = (mins / Decimal("60.0000")) * hr_rate
                operating_cost += op_cost

                bom_op = BOMOperation(
                    tenant_id=tenant_id,
                    bom_id=bom.bom_id,
                    operation_id=op_id,
                    workstation_id=ws_id,
                    sequence_id=op_data.get("sequence_id", idx),
                    time_in_mins=mins,
                    hourly_rate=hr_rate,
                    operating_cost=op_cost,
                    batch_size=Decimal(str(op_data.get("batch_size", "1.0000"))),
                )
                session.add(bom_op)

        scrap_cost = Decimal("0.0000")
        if scrap_items:
            for sc in scrap_items:
                sc_item_id = uuid.UUID(str(sc["item_id"])) if isinstance(sc["item_id"], str) else sc["item_id"]
                s_qty = Decimal(str(sc.get("stock_qty", "0.0000")))
                s_rate = Decimal(str(sc.get("rate", "0.0000")))
                s_amt = s_qty * s_rate
                scrap_cost += s_amt

                bom_scrap = BOMScrapItem(
                    tenant_id=tenant_id,
                    bom_id=bom.bom_id,
                    item_id=sc_item_id,
                    stock_qty=s_qty,
                    rate=s_rate,
                    amount=s_amt,
                )
                session.add(bom_scrap)

        bom.raw_material_cost = raw_material_cost
        bom.operating_cost = operating_cost
        bom.scrap_cost = scrap_cost
        bom.total_cost = (raw_material_cost + operating_cost) - scrap_cost

        await session.flush()
        return await self.get_bom(session, tenant_id, bom.bom_id)  # type: ignore

    async def get_bom(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        bom_id: uuid.UUID,
    ) -> BOM | None:
        """Retrieves BOM with items, operations, and scrap items."""
        stmt = (
            select(BOM)
            .options(
                selectinload(BOM.items),
                selectinload(BOM.operations).selectinload(BOMOperation.operation),
                selectinload(BOM.operations).selectinload(BOMOperation.workstation),
                selectinload(BOM.scrap_items),
                selectinload(BOM.routing),
            )
            .where(BOM.tenant_id == tenant_id, BOM.bom_id == bom_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_boms(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
    ) -> list[BOM]:
        """Lists BOMs for a tenant."""
        stmt = (
            select(BOM)
            .options(
                selectinload(BOM.items),
                selectinload(BOM.operations).selectinload(BOMOperation.operation),
                selectinload(BOM.operations).selectinload(BOMOperation.workstation),
                selectinload(BOM.scrap_items),
            )
            .where(BOM.tenant_id == tenant_id)
        )
        if item_id:
            stmt = stmt.where(BOM.item_id == item_id)
        stmt = stmt.order_by(BOM.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def get_bom_tree(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        bom_id: uuid.UUID,
        current_depth: int = 0,
        max_depth: int = 5,
    ) -> dict[str, Any] | None:
        """Recursively builds multi-level BOM explosion tree."""
        if current_depth > max_depth:
            return None

        bom = await self.get_bom(session, tenant_id, bom_id)
        if not bom:
            return None

        # Fetch finished item master
        item = (
            await session.execute(
                select(Item).where(Item.tenant_id == tenant_id, Item.item_id == bom.item_id)
            )
        ).scalar_one_or_none()

        tree_node: dict[str, Any] = {
            "bom_id": str(bom.bom_id),
            "bom_number": bom.bom_number,
            "item_id": str(bom.item_id),
            "item_name": item.item_name if item else "Unknown Item",
            "item_code": item.item_code if item else "N/A",
            "quantity": float(bom.quantity),
            "raw_material_cost": float(bom.raw_material_cost),
            "operating_cost": float(bom.operating_cost),
            "scrap_cost": float(bom.scrap_cost),
            "total_cost": float(bom.total_cost),
            "depth": current_depth,
            "operations": [
                {
                    "operation_id": str(op.operation_id),
                    "operation_name": op.operation.operation_name if op.operation else "Operation",
                    "workstation_code": op.workstation.workstation_code if op.workstation else "Any",
                    "sequence_id": op.sequence_id,
                    "time_in_mins": float(op.time_in_mins),
                    "hourly_rate": float(op.hourly_rate),
                    "operating_cost": float(op.operating_cost),
                }
                for op in bom.operations
            ],
            "components": [],
        }

        # Explode child components
        for c in bom.items:
            comp_item = (
                await session.execute(
                    select(Item).where(Item.tenant_id == tenant_id, Item.item_id == c.item_id)
                )
            ).scalar_one_or_none()

            child_data: dict[str, Any] = {
                "bom_item_id": str(c.bom_item_id),
                "item_id": str(c.item_id),
                "item_name": comp_item.item_name if comp_item else "Component",
                "item_code": comp_item.item_code if comp_item else "N/A",
                "quantity": float(c.quantity),
                "rate": float(c.rate),
                "amount": float(c.amount),
                "scrap_percentage": float(c.scrap_percentage),
                "sub_assembly": None,
            }

            # Check if this component has a sub-assembly BOM
            sub_assembly_id = c.bom_sub_assembly_id
            if not sub_assembly_id:
                # Look for a default BOM for this child item
                default_sub_bom = (
                    await session.execute(
                        select(BOM).where(
                            BOM.tenant_id == tenant_id,
                            BOM.item_id == c.item_id,
                            BOM.is_default.is_(True),
                            BOM.bom_id != bom_id,  # Prevent direct circular reference
                        )
                    )
                ).scalars().first()
                if default_sub_bom:
                    sub_assembly_id = default_sub_bom.bom_id

            if sub_assembly_id and current_depth < max_depth:
                child_data["sub_assembly"] = await self.get_bom_tree(
                    session, tenant_id, sub_assembly_id, current_depth + 1, max_depth
                )

            tree_node["components"].append(child_data)

        return tree_node


bom_service = BOMService()
