"""Item Attributes and Multi-Variant Catalog Service."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, ItemAttribute, ItemAttributeValue


class VariantService:
    """Core domain logic for Product Variant generation and attribute matrix."""

    async def create_attribute(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        attribute_name: str,
        values: list[dict[str, str]] | None = None,
    ) -> ItemAttribute:
        """Creates an attribute template (e.g. Size, Color) with allowed values."""
        attr = ItemAttribute(
            tenant_id=tenant_id,
            attribute_name=attribute_name.strip(),
        )
        session.add(attr)
        await session.flush()

        if values:
            for val in values:
                iav = ItemAttributeValue(
                    tenant_id=tenant_id,
                    attribute_id=attr.attribute_id,
                    attribute_value=val["attribute_value"].strip(),
                    abbr=val.get("abbr"),
                )
                session.add(iav)

        await session.flush()
        return await self.get_attribute(session, tenant_id, attr.attribute_id)  # type: ignore

    async def get_attribute(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        attribute_id: uuid.UUID,
    ) -> ItemAttribute | None:
        """Fetches attribute with its values."""
        stmt = (
            select(ItemAttribute)
            .options(selectinload(ItemAttribute.values))
            .where(
                ItemAttribute.tenant_id == tenant_id,
                ItemAttribute.attribute_id == attribute_id,
            )
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_attributes(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[ItemAttribute]:
        """Lists all product attributes for tenant."""
        stmt = (
            select(ItemAttribute)
            .options(selectinload(ItemAttribute.values))
            .where(ItemAttribute.tenant_id == tenant_id)
            .order_by(ItemAttribute.attribute_name.asc())
        )
        return list((await session.execute(stmt)).scalars().all())

    async def generate_item_variants(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        template_item_id: uuid.UUID,
        variant_definitions: list[dict[str, Any]],
    ) -> list[Item]:
        """Generates concrete variant SKU items from a template product."""
        template = await session.get(Item, template_item_id)
        if not template or template.tenant_id != tenant_id:
            raise ValueError(f"Template item {template_item_id} not found.")

        template.has_variants = True
        created_variants: list[Item] = []

        for vdef in variant_definitions:
            variant_code = vdef.get("item_code")
            if not variant_code:
                # Auto-generate suffix based on attributes: e.g. TSHIRT-BASE-XL-BLK
                attr_suffix = "-".join(str(val) for val in vdef.get("attributes", {}).values())
                variant_code = f"{template.item_code}-{attr_suffix}".upper()

            variant_name = vdef.get("item_name")
            if not variant_name:
                attr_str = ", ".join(f"{k}: {v}" for k, v in vdef.get("attributes", {}).items())
                variant_name = f"{template.item_name} ({attr_str})"

            variant_item = Item(
                tenant_id=tenant_id,
                item_code=variant_code,
                item_name=variant_name,
                description=template.description,
                stock_uom=template.stock_uom,
                is_stock_item=template.is_stock_item,
                is_sales_item=template.is_sales_item,
                is_purchase_item=template.is_purchase_item,
                valuation_method=template.valuation_method,
                standard_rate=Decimal(str(vdef.get("standard_rate", template.standard_rate))),
                reorder_level=template.reorder_level,
                is_active=True,
                has_variants=False,
                variant_of=template.item_id,
                variant_attributes=vdef.get("attributes", {}),
                has_batch_no=template.has_batch_no,
                has_serial_no=template.has_serial_no,
            )
            session.add(variant_item)
            created_variants.append(variant_item)

        await session.flush()
        return created_variants

    async def list_variants_of_item(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        template_item_id: uuid.UUID,
    ) -> list[Item]:
        """Lists all variants belonging to a template item."""
        stmt = (
            select(Item)
            .where(Item.tenant_id == tenant_id, Item.variant_of == template_item_id)
            .order_by(Item.item_code.asc())
        )
        return list((await session.execute(stmt)).scalars().all())


variant_service = VariantService()
