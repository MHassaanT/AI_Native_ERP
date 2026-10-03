"""Delivery Trip and Route Dispatch Service."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.logistics import DeliveryStop, DeliveryTrip
from erp.db.models.sales import DeliveryNote


class DeliveryTripService:
    """Core domain logic for Delivery Trips and multi-stop logistics dispatch."""

    async def create_delivery_trip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        trip_number: str,
        driver_name: str,
        vehicle_number: str,
        departure_datetime: datetime | None = None,
        total_distance_km: Decimal = Decimal("0.00"),
        stops: list[dict[str, Any]] | None = None,
    ) -> DeliveryTrip:
        """Plans a new multi-stop delivery dispatch route."""
        trip = DeliveryTrip(
            tenant_id=tenant_id,
            trip_number=trip_number,
            driver_name=driver_name,
            vehicle_number=vehicle_number,
            departure_datetime=departure_datetime,
            status="DRAFT",
            total_distance_km=total_distance_km,
        )
        session.add(trip)
        await session.flush()

        if stops:
            for idx, st in enumerate(stops, start=1):
                stop = DeliveryStop(
                    tenant_id=tenant_id,
                    trip_id=trip.trip_id,
                    delivery_note_id=(
                        uuid.UUID(str(st["delivery_note_id"]))
                        if st.get("delivery_note_id")
                        else None
                    ),
                    customer_id=(
                        uuid.UUID(str(st["customer_id"]))
                        if st.get("customer_id")
                        else None
                    ),
                    address=st["address"],
                    stop_sequence=st.get("stop_sequence", idx),
                    status="PENDING",
                )
                session.add(stop)

        await session.flush()
        return await self.get_delivery_trip(session, tenant_id, trip.trip_id)  # type: ignore

    async def dispatch_trip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        trip_id: uuid.UUID,
    ) -> DeliveryTrip:
        """Dispatches vehicle on the delivery route."""
        trip = await self.get_delivery_trip(session, tenant_id, trip_id)
        if not trip:
            raise ValueError(f"Delivery Trip {trip_id} not found.")
        trip.status = "IN_TRANSIT"
        if not trip.departure_datetime:
            trip.departure_datetime = datetime.now(timezone.utc)
        await session.flush()
        return trip

    async def complete_stop(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        trip_id: uuid.UUID,
        stop_id: uuid.UUID,
        customer_signature: str | None = None,
    ) -> DeliveryStop:
        """Records arrival and completion of an individual delivery stop."""
        stmt = select(DeliveryStop).where(
            DeliveryStop.tenant_id == tenant_id,
            DeliveryStop.trip_id == trip_id,
            DeliveryStop.stop_id == stop_id,
        )
        stop = (await session.execute(stmt)).scalar_one_or_none()
        if not stop:
            raise ValueError(f"Delivery Stop {stop_id} not found on trip {trip_id}.")

        stop.status = "DELIVERED"
        stop.arrival_datetime = datetime.now(timezone.utc)
        stop.customer_signature = customer_signature or "SIGNED"

        # Update linked Delivery Note if exists
        if stop.delivery_note_id:
            dn = await session.get(DeliveryNote, stop.delivery_note_id)
            if dn:
                dn.status = "DELIVERED"

        await session.flush()
        return stop

    async def complete_trip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        trip_id: uuid.UUID,
    ) -> DeliveryTrip:
        """Marks the entire delivery trip as COMPLETED."""
        trip = await self.get_delivery_trip(session, tenant_id, trip_id)
        if not trip:
            raise ValueError(f"Delivery Trip {trip_id} not found.")
        trip.status = "COMPLETED"
        await session.flush()
        return trip

    async def get_delivery_trip(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        trip_id: uuid.UUID,
    ) -> DeliveryTrip | None:
        """Fetches delivery trip with stops and customer linkages."""
        stmt = (
            select(DeliveryTrip)
            .options(
                selectinload(DeliveryTrip.stops).selectinload(DeliveryStop.delivery_note),
                selectinload(DeliveryTrip.stops).selectinload(DeliveryStop.customer),
            )
            .where(DeliveryTrip.tenant_id == tenant_id, DeliveryTrip.trip_id == trip_id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_delivery_trips(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[DeliveryTrip]:
        """Lists delivery trips for tenant."""
        stmt = (
            select(DeliveryTrip)
            .options(
                selectinload(DeliveryTrip.stops).selectinload(DeliveryStop.delivery_note),
                selectinload(DeliveryTrip.stops).selectinload(DeliveryStop.customer),
            )
            .where(DeliveryTrip.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(DeliveryTrip.status == status.upper())
        stmt = stmt.order_by(DeliveryTrip.created_at.desc())
        return list((await session.execute(stmt)).scalars().all())


delivery_trip_service = DeliveryTripService()
