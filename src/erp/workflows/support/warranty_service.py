"""Domain Service for Serial Number Warranty Claims & Entitlement Verification."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.inventory import Item, SerialNo
from erp.db.models.sales import Customer
from erp.db.models.support import WarrantyClaim


class WarrantyService:
    """Enterprise warranty entitlement checking and RMA claim processing."""

    async def verify_serial_warranty(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        serial_number: str,
    ) -> dict[str, Any]:
        """Validates whether a serial number is registered, active, and within warranty coverage."""
        clean_num = serial_number.strip().upper()
        stmt = (
            select(SerialNo)
            .options(selectinload(SerialNo.item))
            .where(SerialNo.tenant_id == tenant_id, SerialNo.serial_number == clean_num)
        )
        serial = (await session.execute(stmt)).scalar_one_or_none()

        if not serial:
            return {
                "serial_number": clean_num,
                "is_registered": False,
                "warranty_status": "NO_WARRANTY",
                "message": f"Serial number '{clean_num}' is not registered in the system.",
                "item_id": None,
                "item_code": None,
                "item_name": None,
                "warranty_expiry_date": None,
            }

        expiry = serial.warranty_expiry_date
        today = date.today()

        if expiry:
            if expiry >= today:
                status = "IN_WARRANTY"
                msg = f"Active warranty coverage until {expiry.isoformat()}."
            else:
                status = "OUT_OF_WARRANTY"
                msg = f"Warranty coverage expired on {expiry.isoformat()}."
        else:
            status = "NO_WARRANTY"
            msg = "Unit does not have warranty terms configured."

        return {
            "serial_id": str(serial.serial_id),
            "serial_number": serial.serial_number,
            "is_registered": True,
            "warranty_status": status,
            "message": msg,
            "item_id": str(serial.item_id),
            "item_code": serial.item.item_code if serial.item else "N/A",
            "item_name": serial.item.item_name if serial.item else "Unknown Item",
            "warranty_expiry_date": expiry.isoformat() if expiry else None,
            "lifecycle_status": serial.status,
        }

    async def create_warranty_claim(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        claim_number: str,
        customer_id: uuid.UUID,
        serial_number: str,
        complaint_description: str,
        resolution_type: str = "REPAIR",
        item_id: uuid.UUID | None = None,
    ) -> WarrantyClaim:
        """Files a new warranty claim and automatically evaluates warranty entitlement."""
        veri = await self.verify_serial_warranty(session, tenant_id, serial_number)

        resolved_item_id = item_id
        serial_id = None
        if veri["is_registered"]:
            serial_id = uuid.UUID(veri["serial_id"])
            if not resolved_item_id and veri["item_id"]:
                resolved_item_id = uuid.UUID(veri["item_id"])

        if not resolved_item_id:
            # Fallback to first active item if unlinked
            first_item = (
                await session.execute(select(Item).where(Item.tenant_id == tenant_id).limit(1))
            ).scalars().first()
            if not first_item:
                raise ValueError("No inventory items found to attach warranty claim.")
            resolved_item_id = first_item.item_id

        claim = WarrantyClaim(
            tenant_id=tenant_id,
            claim_number=claim_number.strip().upper(),
            customer_id=customer_id,
            item_id=resolved_item_id,
            serial_id=serial_id,
            serial_number=serial_number.strip().upper(),
            claim_date=date.today(),
            status="OPEN",
            complaint_description=complaint_description.strip(),
            resolution_type=resolution_type.strip().upper(),
            warranty_status=veri["warranty_status"],
            warranty_expiry_date=date.fromisoformat(veri["warranty_expiry_date"])
            if veri.get("warranty_expiry_date")
            else None,
        )
        session.add(claim)
        await session.commit()
        await session.refresh(claim)
        return claim

    async def list_warranty_claims(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[WarrantyClaim]:
        """Lists warranty claims with customer and item relations."""
        stmt = (
            select(WarrantyClaim)
            .options(
                selectinload(WarrantyClaim.customer),
                selectinload(WarrantyClaim.item),
                selectinload(WarrantyClaim.serial),
            )
            .where(WarrantyClaim.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(WarrantyClaim.status == status.strip().upper())
        stmt = stmt.order_by(WarrantyClaim.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())

    async def resolve_warranty_claim(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        claim_id: uuid.UUID,
        resolution_details: str,
        resolution_type: str | None = None,
        new_status: str = "RESOLVED",
    ) -> WarrantyClaim:
        """Closes or updates a claim with replacement/repair authorization."""
        stmt = (
            select(WarrantyClaim)
            .options(
                selectinload(WarrantyClaim.customer),
                selectinload(WarrantyClaim.item),
            )
            .where(WarrantyClaim.tenant_id == tenant_id, WarrantyClaim.claim_id == claim_id)
        )
        claim = (await session.execute(stmt)).scalar_one_or_none()
        if not claim:
            raise ValueError(f"Warranty Claim '{claim_id}' not found.")

        claim.status = new_status.strip().upper()
        claim.resolution_details = resolution_details.strip()
        if resolution_type:
            claim.resolution_type = resolution_type.strip().upper()

        await session.commit()
        await session.refresh(claim)
        return claim


warranty_service = WarrantyService()
