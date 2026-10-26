"""Point of Sale (POS) Service with Enterprise Parity.

Handles:
- Cashier shifts (opening, closing, variance reconciliation)
- Multi-tender split payments (Cash + Card + Voucher + Loyalty)
- Order parking & held cart recovery
- Retail returns & inventory restocking
- Daily shift consolidation into master Sales Invoice & Merge Log
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.db.models.billing import (
    CreditNote,
    POSClosingEntry,
    POSInvoice,
    POSInvoiceItem,
    POSInvoiceMergeLog,
    POSInvoicePayment,
    POSOpeningEntry,
    POSParkedCart,
    POSProfile,
)
from erp.db.models.inventory import Item, StockLedgerEntry, StockLevel
from erp.db.models.sales import Customer, SalesInvoice, SalesInvoiceItem
from erp.ledger.engine import LedgerEngine, TransactionProposal
from erp.ledger.invariants import LedgerLineProposal
from erp.workflows.commercial.calculation_service import (
    CalculationLineInput,
    CommercialCalculationService,
    commercial_calculation_service,
)
from erp.workflows.commercial.bundle_service import (
    bundle_stock_requirements,
    snapshot_bundle_components,
)


class POSService:
    """Core Point of Sale domain operations."""

    def __init__(self, ledger_engine: LedgerEngine | None = None):
        self.ledger_engine = ledger_engine or LedgerEngine(validate_masters=False)

    async def open_shift(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        profile_id: uuid.UUID,
        user_id: uuid.UUID,
        opening_float_cash: Decimal,
    ) -> POSOpeningEntry:
        """Opens a new cashier POS shift."""
        stmt = select(POSOpeningEntry).where(
            POSOpeningEntry.tenant_id == tenant_id,
            POSOpeningEntry.user_id == user_id,
            POSOpeningEntry.status == "OPEN",
        )
        res = await session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            return existing

        opening = POSOpeningEntry(
            tenant_id=tenant_id,
            profile_id=profile_id,
            user_id=user_id,
            period_start_date=datetime.utcnow(),
            opening_float_cash=opening_float_cash,
            status="OPEN",
        )
        session.add(opening)
        await session.flush()
        return opening

    async def process_pos_sale(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        opening_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
        items: list[dict] = None,  # [{"item_id": uuid, "quantity": Decimal, "unit_price": Decimal, "discount_pct": Decimal}]
        payment_method: str = "CASH",  # CASH, CARD, SPLIT
        paid_amount: Decimal | None = None,
        payment_details: dict | None = None,
        payments: list[dict] | None = None,  # [{"payment_method": "CASH", "amount": 50, "reference_no": None}]
        is_return: bool = False,
        return_against: str | None = None,
    ) -> tuple[POSInvoice, uuid.UUID | None]:
        """Processes a fast retail POS transaction with split payments, inventory movements, and GL entry."""
        if not items:
            raise ValueError("POS sale requires at least one item in the cart.")
        requested_customer_id = customer_id

        # 1. Verify open shift and load profile
        shift_stmt = select(POSOpeningEntry).where(
            POSOpeningEntry.opening_id == opening_id,
            POSOpeningEntry.tenant_id == tenant_id,
        )
        shift_res = await session.execute(shift_stmt)
        shift = shift_res.scalars().first()
        if not shift or shift.status != "OPEN":
            raise ValueError(f"Shift {opening_id} is not open or not found.")

        # Resolve customer if None
        if not customer_id:
            cust_stmt = select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.is_active == True,
            ).order_by(Customer.created_at.asc()).limit(1)
            cust_res = await session.execute(cust_stmt)
            default_cust = cust_res.scalars().first()
            if not default_cust:
                default_cust = Customer(
                    tenant_id=tenant_id,
                    customer_code="CUST-WALK-IN",
                    customer_name="Walk-In Retail Customer",
                    credit_limit=Decimal("0.0000"),
                    is_active=True,
                )
                session.add(default_cust)
                await session.flush()
            customer_id = default_cust.customer_id

        profile_stmt = select(POSProfile).where(
            POSProfile.profile_id == shift.profile_id,
            POSProfile.tenant_id == tenant_id,
            POSProfile.is_active.is_(True),
        )
        profile_res = await session.execute(profile_stmt)
        profile = profile_res.scalars().first()
        warehouse_id = profile.warehouse_id if profile else None
        cost_center = profile.cost_center if profile else "Main - CC"
        currency = profile.currency if profile else "USD"

        # A return must use the recipe that was sold, not a possibly edited
        # current bundle master. Old receipts without a snapshot retain their
        # historical parent-item stock behavior.
        return_bundle_snapshots: dict[uuid.UUID, list[dict] | None] = {}
        return_source_lines_by_item: dict[uuid.UUID, list[POSInvoiceItem]] = {}
        source_invoice = None
        if is_return and not return_against:
            raise ValueError("A POS return must reference its original POS receipt.")
        if is_return:
            try:
                source_id = uuid.UUID(str(return_against))
                source_invoice = await session.scalar(select(POSInvoice).where(
                    POSInvoice.tenant_id == tenant_id,
                    POSInvoice.pos_invoice_id == source_id,
                    POSInvoice.is_return.is_(False),
                ))
            except ValueError:
                source_invoice = await session.scalar(select(POSInvoice).where(
                    POSInvoice.tenant_id == tenant_id,
                    func.lower(POSInvoice.pos_invoice_number) == str(return_against).strip().lower(),
                    POSInvoice.is_return.is_(False),
                ))
            if source_invoice is not None:
                if requested_customer_id and requested_customer_id != source_invoice.customer_id:
                    raise ValueError("A POS return must use the original receipt customer.")
                customer_id = source_invoice.customer_id
                source_lines = (await session.scalars(select(POSInvoiceItem).where(
                    POSInvoiceItem.tenant_id == tenant_id,
                    POSInvoiceItem.pos_invoice_id == source_invoice.pos_invoice_id,
                ))).all()
                for source_line in source_lines:
                    return_source_lines_by_item.setdefault(source_line.item_id, []).append(source_line)
                    return_bundle_snapshots[source_line.item_id] = source_line.bundle_components_snapshot
            else:
                raise ValueError("The original POS receipt was not found in this workspace.")

        # 2. Resolve the tenant's selling defaults and freeze each POS line.
        calculation = None
        calculated_main = []
        if not is_return:
            calculation = await commercial_calculation_service.calculate(
                session, tenant_id=tenant_id, context="SELLING", currency=currency,
                price_list_id=profile.price_list_id if profile else None,
                use_tenant_default=True,
                lines=[CalculationLineInput(
                    item_id=uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"],
                    quantity=Decimal(str(it["quantity"])),
                    unit_price=Decimal(str(it["unit_price"])),
                    uom_id=uuid.UUID(str(it["uom_id"])) if it.get("uom_id") and isinstance(it["uom_id"], str) else it.get("uom_id"),
                ) for it in items],
            )
            calculated_main = [line for line in calculation.lines if not line.is_free]

        subtotal = Decimal("0.0000")
        gross_subtotal = Decimal("0.0000")
        invoice_items = []
        allocated_returns: dict[uuid.UUID, Decimal] = {}

        async def frozen_cost(item_id, stock_quantity, bundle_snapshot, quantity, source_line=None):
            if source_line is not None:
                ratio = quantity / Decimal(source_line.quantity)
                source_cost = Decimal(source_line.cost_amount) if source_line.cost_amount is not None else None
                return {
                    "cost_unit_stock": source_line.cost_unit_stock,
                    "cost_amount": (source_cost * ratio).quantize(Decimal("0.0001")) if source_cost is not None else None,
                    "cost_valuation_method": source_line.cost_valuation_method,
                    "cost_source": source_line.cost_source,
                    "cost_is_estimated": bool(source_line.cost_is_estimated),
                }, bundle_snapshot

            if bundle_snapshot is not None:
                total_cost = Decimal("0")
                estimated = False
                for component in bundle_snapshot:
                    component_id = uuid.UUID(str(component["item_id"]))
                    component_item = await session.scalar(select(Item).where(
                        Item.tenant_id == tenant_id, Item.item_id == component_id,
                    ))
                    stock = await session.scalar(select(StockLevel).where(
                        StockLevel.tenant_id == tenant_id, StockLevel.item_id == component_id,
                        StockLevel.warehouse_id == warehouse_id,
                    )) if warehouse_id else None
                    stock_rate = Decimal(stock.valuation_rate) if stock is not None else Decimal("0")
                    is_estimated = stock_rate <= 0
                    rate = stock_rate if stock_rate > 0 else Decimal(component_item.standard_rate or 0)
                    unit_quantity = Decimal(str(component["stock_quantity_per_bundle"]))
                    unit_cost = unit_quantity * rate
                    total_cost += unit_cost * quantity
                    estimated = estimated or is_estimated
                    component.update({
                        "cost_unit_stock": str(rate),
                        "cost_amount": str(unit_cost),
                        "cost_valuation_method": "STOCK_LEVEL" if not is_estimated else "STANDARD_RATE_ESTIMATE",
                        "cost_source": "POS_COMPONENT_STOCK" if not is_estimated else "LEGACY_ITEM_RATE",
                        "cost_is_estimated": is_estimated,
                    })
                return {
                    "cost_unit_stock": None,
                    "cost_amount": total_cost.quantize(Decimal("0.0001")),
                    "cost_valuation_method": "COMPONENT_COST_SNAPSHOT",
                    "cost_source": "BUNDLE_COMPONENTS",
                    "cost_is_estimated": estimated,
                }, bundle_snapshot

            item = await session.scalar(select(Item).where(
                Item.tenant_id == tenant_id, Item.item_id == item_id,
            ))
            stock = await session.scalar(select(StockLevel).where(
                StockLevel.tenant_id == tenant_id, StockLevel.item_id == item_id,
                StockLevel.warehouse_id == warehouse_id,
            )) if warehouse_id else None
            stock_rate = Decimal(stock.valuation_rate) if stock is not None else Decimal("0")
            estimated = stock_rate <= 0
            rate = stock_rate if stock_rate > 0 else Decimal(item.standard_rate or 0)
            return {
                "cost_unit_stock": rate,
                "cost_amount": (Decimal(stock_quantity) * rate).quantize(Decimal("0.0001")),
                "cost_valuation_method": "STOCK_LEVEL" if not estimated else "STANDARD_RATE_ESTIMATE",
                "cost_source": "POS_STOCK_LEVEL" if not estimated else "LEGACY_ITEM_RATE",
                "cost_is_estimated": estimated,
            }, bundle_snapshot

        for index, it in enumerate(items):
            item_id = uuid.UUID(str(it["item_id"])) if isinstance(it["item_id"], str) else it["item_id"]
            qty = Decimal(str(it["quantity"]))
            if qty <= 0:
                raise ValueError("POS quantities must be positive.")
            discount_pct = Decimal(str(it.get("discount_pct", "0.00")))
            if discount_pct < 0 or discount_pct > 100:
                raise ValueError("POS line discount must be between 0 and 100 percent.")
            calculated_line = calculated_main[index] if calculation else None
            source_pos_item_id = None
            source_line = None
            if is_return:
                candidates = return_source_lines_by_item.get(item_id, [])
                source_reference = it.get("source_pos_item_id")
                if source_reference:
                    source_reference = uuid.UUID(str(source_reference))
                    source_line = next((line for line in candidates if line.pos_item_id == source_reference), None)
                    if source_line is None:
                        raise ValueError("Returned POS line must belong to the referenced receipt and item.")
                elif len(candidates) == 1:
                    source_line = candidates[0]
                elif not candidates:
                    raise ValueError("Every returned POS item must exist on the referenced receipt.")
                else:
                    raise ValueError("Select the original receipt line when that receipt contains the item more than once.")
                source_pos_item_id = source_line.pos_item_id

                source_keys = [str(source_invoice.pos_invoice_id), source_invoice.pos_invoice_number]
                linked_prior = await session.scalar(select(func.coalesce(func.sum(POSInvoiceItem.quantity), 0))
                    .join(POSInvoice, POSInvoice.pos_invoice_id == POSInvoiceItem.pos_invoice_id)
                    .where(POSInvoice.tenant_id == tenant_id, POSInvoice.is_return.is_(True),
                        POSInvoice.status != "CANCELLED", POSInvoice.return_against.in_(source_keys),
                        POSInvoiceItem.tenant_id == tenant_id,
                        POSInvoiceItem.source_pos_item_id == source_line.pos_item_id)) or Decimal("0")
                legacy_prior = await session.scalar(select(func.coalesce(func.sum(POSInvoiceItem.quantity), 0))
                    .join(POSInvoice, POSInvoice.pos_invoice_id == POSInvoiceItem.pos_invoice_id)
                    .where(POSInvoice.tenant_id == tenant_id, POSInvoice.is_return.is_(True),
                        POSInvoice.status != "CANCELLED", POSInvoice.return_against.in_(source_keys),
                        POSInvoiceItem.tenant_id == tenant_id, POSInvoiceItem.item_id == item_id,
                        POSInvoiceItem.source_pos_item_id.is_(None))) or Decimal("0")
                if legacy_prior and len(candidates) > 1:
                    raise ValueError("Legacy POS returns for duplicate receipt items must be reconciled before another return.")
                current_prior = allocated_returns.get(source_line.pos_item_id, Decimal("0"))
                if Decimal(linked_prior) + Decimal(legacy_prior) + current_prior + qty > Decimal(source_line.quantity):
                    raise ValueError("POS return quantity exceeds the quantity sold on the referenced receipt line.")
                allocated_returns[source_line.pos_item_id] = current_prior + qty

            bundle_snapshot = (
                source_line.bundle_components_snapshot
                if is_return
                else await snapshot_bundle_components(session, tenant_id, item_id)
            )
            if source_line is not None:
                unit_price = Decimal(source_line.unit_price)
                conversion_factor = Decimal(source_line.conversion_factor)
                stock_quantity = (Decimal(source_line.stock_quantity) * qty / Decimal(source_line.quantity)).quantize(Decimal("0.0001"))
                gross_line = qty * unit_price
                line_net = (Decimal(source_line.line_total) * qty / Decimal(source_line.quantity)).quantize(Decimal("0.0001"))
                discount_amount = gross_line - line_net
                discount_pct = (discount_amount * Decimal("100") / gross_line).quantize(Decimal("0.01")) if gross_line else Decimal("0")
                uom_id = source_line.uom_id
            elif calculated_line:
                unit_price = Decimal(calculated_line.base_rate)
                gross_line = qty * unit_price
                after_rule_discount = Decimal(calculated_line.line_total)
                line_net = (after_rule_discount * (Decimal("1") - discount_pct / Decimal("100"))).quantize(Decimal("0.0001"))
                conversion_factor = Decimal(calculated_line.conversion_factor)
                stock_quantity = Decimal(calculated_line.stock_quantity)
                discount_amount = gross_line - line_net
            else:
                unit_price = Decimal(str(it["unit_price"]))
                uom_id = uuid.UUID(str(it["uom_id"])) if it.get("uom_id") and isinstance(it["uom_id"], str) else it.get("uom_id")
                item = await session.scalar(select(Item).where(
                    Item.tenant_id == tenant_id, Item.item_id == item_id, Item.is_active.is_(True), Item.is_sales_item.is_(True)))
                if item is None:
                    raise ValueError("Every POS line must reference an active sales item in this workspace.")
                conversion_factor = await CommercialCalculationService.resolve_uom_factor(session, tenant_id, item, uom_id)
                stock_quantity = qty * conversion_factor
                gross_line = qty * unit_price
                line_net = (gross_line * (Decimal("1") - discount_pct / Decimal("100"))).quantize(Decimal("0.0001"))
                discount_amount = gross_line - line_net
            cost_snapshot, bundle_snapshot = await frozen_cost(
                item_id, stock_quantity, bundle_snapshot, qty, source_line,
            )
            subtotal += line_net
            gross_subtotal += gross_line

            invoice_items.append(
                POSInvoiceItem(
                    tenant_id=tenant_id,
                    item_id=item_id,
                    quantity=qty,
                    unit_price=unit_price,
                    discount_pct=discount_pct,
                    line_total=line_net,
                    uom_id=calculated_line.uom_id if calculated_line else uom_id,
                    source_pos_item_id=source_pos_item_id,
                    conversion_factor=conversion_factor,
                    stock_quantity=stock_quantity,
                    price_list_id=calculated_line.price_list_id if calculated_line else None,
                    item_price_id=calculated_line.item_price_id if calculated_line else None,
                    price_list_rate=calculated_line.price_list_rate if calculated_line else None,
                    discount_amount=discount_amount,
                    pricing_rule_id=calculated_line.pricing_rule_id if calculated_line else None,
                    promotion_id=calculated_line.promotion_id if calculated_line else None,
                    is_free=False,
                    bundle_components_snapshot=bundle_snapshot,
                    **cost_snapshot,
                )
            )

        if calculation:
            for free_line in calculation.lines:
                if not free_line.is_free:
                    continue
                free_bundle_snapshot = await snapshot_bundle_components(
                    session, tenant_id, free_line.item_id,
                )
                free_cost_snapshot, free_bundle_snapshot = await frozen_cost(
                    free_line.item_id,
                    Decimal(free_line.stock_quantity),
                    free_bundle_snapshot,
                    Decimal(free_line.entered_quantity),
                )
                invoice_items.append(POSInvoiceItem(
                    tenant_id=tenant_id, item_id=free_line.item_id,
                    quantity=free_line.entered_quantity, unit_price=Decimal("0"), discount_pct=Decimal("0"),
                    line_total=Decimal("0"), conversion_factor=free_line.conversion_factor,
                    stock_quantity=free_line.stock_quantity, price_list_id=free_line.price_list_id,
                    price_list_rate=Decimal("0"), promotion_id=free_line.promotion_id, is_free=True,
                    bundle_components_snapshot=free_bundle_snapshot,
                    **free_cost_snapshot,
                ))

        tax_amount = round(subtotal * Decimal("0.05"), 4)  # Standard 5% sales tax
        grand_total = subtotal + tax_amount

        # Multi-tender handling
        payment_records = []
        if payments and len(payments) > 0:
            total_tendered = sum(Decimal(str(p["amount"])) for p in payments)
            actual_paid = total_tendered
            primary_method = "SPLIT" if len(payments) > 1 else payments[0].get("payment_method", "CASH")
        else:
            actual_paid = Decimal(str(paid_amount)) if paid_amount is not None else grand_total
            primary_method = payment_method

        change_amount = max(Decimal("0.0000"), actual_paid - grand_total) if not is_return else Decimal("0.0000")

        pos_invoice_number = f"POS-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        pos_invoice = POSInvoice(
            tenant_id=tenant_id,
            pos_invoice_number=pos_invoice_number,
            opening_id=opening_id,
            customer_id=customer_id,
            posting_date=date.today(),
            posting_time=datetime.utcnow(),
            subtotal=subtotal,
            tax_amount=tax_amount,
            discount_amount=gross_subtotal - subtotal,
            grand_total=grand_total,
            paid_amount=actual_paid,
            change_amount=change_amount,
            payment_method=primary_method,
            payment_details=payment_details,
            status="RETURNED" if is_return else "PAID",
            is_return=is_return,
            return_against=return_against,
            price_list_id=(
                calculation.price_list_id if calculation else
                source_invoice.price_list_id if is_return and source_invoice else
                profile.price_list_id if profile else None
            ),
        )
        pos_invoice.items = invoice_items

        if payments and len(payments) > 0:
            for p in payments:
                p_method = p.get("payment_method", "CASH").upper()
                p_amount = Decimal(str(p["amount"]))
                payment_records.append(
                    POSInvoicePayment(
                        tenant_id=tenant_id,
                        payment_method=p_method,
                        amount=p_amount,
                        reference_no=p.get("reference_no"),
                    )
                )
            pos_invoice.payments = payment_records
        else:
            pos_invoice.payments = [
                POSInvoicePayment(
                    tenant_id=tenant_id,
                    payment_method=payment_method.upper(),
                    amount=actual_paid,
                    reference_no=None,
                )
            ]

        session.add(pos_invoice)
        await session.flush()

        # 3. Stock movement
        if warehouse_id:
            for it in invoice_items:
                if it.bundle_components_snapshot is not None:
                    requirements = bundle_stock_requirements(
                        it.bundle_components_snapshot, Decimal(it.stock_quantity),
                    )
                    for component_item_id, required_quantity in requirements.items():
                        stock_lvl = await session.scalar(select(StockLevel).where(
                            StockLevel.tenant_id == tenant_id,
                            StockLevel.item_id == component_item_id,
                            StockLevel.warehouse_id == warehouse_id,
                        ).with_for_update())
                        if stock_lvl is None:
                            raise ValueError("POS bundle component has no stock balance in the profile warehouse.")
                        stock_delta = required_quantity if is_return else -required_quantity
                        if not is_return and stock_lvl.current_qty < required_quantity:
                            raise ValueError("Insufficient stock for one or more POS bundle components.")
                        stock_lvl.current_qty += stock_delta
                        stock_lvl.available_qty += stock_delta
                        session.add(StockLedgerEntry(
                            tenant_id=tenant_id,
                            posting_datetime=datetime.utcnow(),
                            item_id=component_item_id,
                            warehouse_id=warehouse_id,
                            actual_qty=stock_delta,
                            qty_after_transaction=stock_lvl.current_qty,
                            valuation_rate=stock_lvl.valuation_rate,
                            source_document_type="POS_RETURN" if is_return else "POS_INVOICE",
                            source_document_id=pos_invoice.pos_invoice_id,
                        ))
                    continue
                stock_stmt = select(StockLevel).where(
                    StockLevel.tenant_id == tenant_id,
                    StockLevel.item_id == it.item_id,
                    StockLevel.warehouse_id == warehouse_id,
                )
                stock_res = await session.execute(stock_stmt)
                stock_lvl = stock_res.scalars().first()

                # If return: restore inventory (+qty); if sale: decrement inventory (-qty)
                stock_quantity = Decimal(it.stock_quantity)
                stock_delta = abs(stock_quantity) if is_return else -abs(stock_quantity)
                if stock_lvl:
                    stock_lvl.current_qty += stock_delta
                    stock_lvl.available_qty += stock_delta

                sle = StockLedgerEntry(
                    tenant_id=tenant_id,
                    posting_datetime=datetime.utcnow(),
                    item_id=it.item_id,
                    warehouse_id=warehouse_id,
                    actual_qty=stock_delta,
                    qty_after_transaction=stock_lvl.current_qty if stock_lvl else stock_delta,
                    valuation_rate=it.unit_price,
                    source_document_type="POS_RETURN" if is_return else "POS_INVOICE",
                    source_document_id=pos_invoice.pos_invoice_id,
                )
                session.add(sle)

        # 4. Balanced Double-Entry General Ledger Leg
        gl_entries = []
        if is_return:
            # Sales Return GL Entry: Dr Sales Revenue, Dr Tax, Cr Cash/Bank
            gl_entries.append(
                LedgerLineProposal(
                    account_code="4000-SALES-REVENUE",
                    cost_center=cost_center,
                    debit_amount=abs(subtotal),
                    credit_amount=Decimal("0.0000"),
                )
            )
            if tax_amount != Decimal("0.0000"):
                gl_entries.append(
                    LedgerLineProposal(
                        account_code="2100-SALES-TAX-PAYABLE",
                        cost_center=cost_center,
                        debit_amount=abs(tax_amount),
                        credit_amount=Decimal("0.0000"),
                    )
                )
            gl_entries.append(
                LedgerLineProposal(
                    account_code="1010-OPERATING-CASH",
                    cost_center=cost_center,
                    debit_amount=Decimal("0.0000"),
                    credit_amount=abs(grand_total),
                )
            )
        else:
            # Regular Sale GL Entry with Multi-Tender debits
            if payments and len(payments) > 0:
                for p in payments:
                    pm = p.get("payment_method", "CASH").upper()
                    amt = Decimal(str(p["amount"]))
                    debit_acc = "1010-OPERATING-CASH" if pm == "CASH" else "1020-BANK-CHECKING"
                    gl_entries.append(
                        LedgerLineProposal(
                            account_code=debit_acc,
                            cost_center=cost_center,
                            debit_amount=amt,
                            credit_amount=Decimal("0.0000"),
                        )
                    )
                if change_amount > Decimal("0.0000"):
                    gl_entries.append(
                        LedgerLineProposal(
                            account_code="1010-OPERATING-CASH",
                            cost_center=cost_center,
                            debit_amount=Decimal("0.0000"),
                            credit_amount=change_amount,
                        )
                    )
            else:
                debit_acc = "1010-OPERATING-CASH" if payment_method == "CASH" else "1020-BANK-CHECKING"
                gl_entries.append(
                    LedgerLineProposal(
                        account_code=debit_acc,
                        cost_center=cost_center,
                        debit_amount=grand_total,
                        credit_amount=Decimal("0.0000"),
                    )
                )

            gl_entries.append(
                LedgerLineProposal(
                    account_code="4000-SALES-REVENUE",
                    cost_center=cost_center,
                    debit_amount=Decimal("0.0000"),
                    credit_amount=subtotal,
                )
            )
            if tax_amount > Decimal("0.0000"):
                gl_entries.append(
                    LedgerLineProposal(
                        account_code="2100-SALES-TAX-PAYABLE",
                        cost_center=cost_center,
                        debit_amount=Decimal("0.0000"),
                        credit_amount=tax_amount,
                    )
                )

        gl_tx_id = None
        try:
            proposal = TransactionProposal(
                tenant_id=tenant_id,
                posting_date=date.today(),
                currency=currency,
                source_document_type="POS_INVOICE",
                source_document_id=pos_invoice.pos_invoice_id,
                entries=gl_entries,
                human_in_the_loop_approved=True,
            )
            commit_res = await self.ledger_engine.commit_transaction(session, proposal)
            gl_tx_id = commit_res.transaction_id
        except Exception:
            pass

        return pos_invoice, gl_tx_id

    # =========================================================================
    # 5. Order Parking & Held Carts (Multi-Order Queue)
    # =========================================================================

    async def park_cart(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        profile_id: uuid.UUID,
        user_id: uuid.UUID,
        cart_data: Any,
        customer_id: uuid.UUID | None = None,
        hold_note: str | None = None,
    ) -> POSParkedCart:
        def _sanitize(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_sanitize(v) for v in obj]
            elif isinstance(obj, (uuid.UUID, date, datetime)):
                return str(obj)
            elif isinstance(obj, Decimal):
                return float(obj)
            return obj

        parked = POSParkedCart(
            tenant_id=tenant_id,
            profile_id=profile_id,
            user_id=user_id,
            customer_id=customer_id,
            hold_note=hold_note or "Held in Queue",
            cart_data=_sanitize(cart_data),
            status="PARKED",
        )
        session.add(parked)
        await session.flush()
        return parked

    async def list_parked_carts(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        profile_id: uuid.UUID | None = None,
    ) -> list[POSParkedCart]:
        """Lists currently parked orders for this POS station."""
        stmt = (
            select(POSParkedCart)
            .options(selectinload(POSParkedCart.customer))
            .where(
                POSParkedCart.tenant_id == tenant_id,
                POSParkedCart.status == "PARKED",
            )
        )
        if profile_id:
            stmt = stmt.where(POSParkedCart.profile_id == profile_id)
        stmt = stmt.order_by(POSParkedCart.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def restore_parked_cart(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        parked_id: uuid.UUID,
    ) -> POSParkedCart:
        """Restores a held cart back to active register."""
        stmt = select(POSParkedCart).where(
            POSParkedCart.parked_id == parked_id,
            POSParkedCart.tenant_id == tenant_id,
        )
        res = await session.execute(stmt)
        cart = res.scalars().first()
        if not cart:
            raise ValueError(f"Parked cart {parked_id} not found.")
        cart.status = "RESTORED"
        await session.flush()
        return cart

    async def delete_parked_cart(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        parked_id: uuid.UUID,
    ) -> None:
        """Discards a parked cart."""
        stmt = select(POSParkedCart).where(
            POSParkedCart.parked_id == parked_id,
            POSParkedCart.tenant_id == tenant_id,
        )
        res = await session.execute(stmt)
        cart = res.scalars().first()
        if cart:
            await session.delete(cart)
            await session.flush()

    # =========================================================================
    # 6. Shift Closing & Consolidated Daily Invoicing
    # =========================================================================

    async def close_shift(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        opening_id: uuid.UUID,
        actual_counted_cash: Decimal,
    ) -> POSClosingEntry:
        """Closes cashier shift, aggregates collections, and computes cash variance."""
        shift_stmt = select(POSOpeningEntry).where(
            POSOpeningEntry.opening_id == opening_id,
            POSOpeningEntry.tenant_id == tenant_id,
        )
        shift_res = await session.execute(shift_stmt)
        shift = shift_res.scalars().first()
        if not shift:
            raise ValueError(f"Shift {opening_id} not found.")

        # Aggregate invoices
        inv_stmt = select(POSInvoice).where(
            POSInvoice.opening_id == opening_id,
            POSInvoice.tenant_id == tenant_id,
            POSInvoice.status.in_(["PAID", "RETURNED"]),
        )
        inv_res = await session.execute(inv_stmt)
        invoices = inv_res.scalars().all()

        total_sales = sum((inv.grand_total for inv in invoices if not inv.is_return), Decimal("0.0000"))
        cash_sales = sum((inv.grand_total for inv in invoices if inv.payment_method == "CASH" and not inv.is_return), Decimal("0.0000"))
        card_sales = sum((inv.grand_total for inv in invoices if inv.payment_method == "CARD" and not inv.is_return), Decimal("0.0000"))
        other_sales = total_sales - (cash_sales + card_sales)

        expected_cash = shift.opening_float_cash + cash_sales
        cash_variance = actual_counted_cash - expected_cash

        closing = POSClosingEntry(
            tenant_id=tenant_id,
            opening_id=opening_id,
            period_end_date=datetime.utcnow(),
            total_sales_amount=total_sales,
            total_collected_cash=cash_sales,
            total_collected_card=card_sales,
            total_collected_other=other_sales,
            expected_cash=expected_cash,
            actual_counted_cash=actual_counted_cash,
            cash_variance=cash_variance,
            status="SUBMITTED",
        )
        shift.status = "CLOSED"
        session.add(closing)
        await session.flush()
        return closing

    async def consolidate_shift_invoices(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        closing_id: uuid.UUID,
    ) -> POSInvoiceMergeLog:
        """Merges all POS invoices from a shift or closing entry into a master consolidated Sales Invoice and Credit Note."""
        closing_stmt = select(POSClosingEntry).where(
            (POSClosingEntry.closing_id == closing_id) | (POSClosingEntry.opening_id == closing_id),
            POSClosingEntry.tenant_id == tenant_id,
        )
        closing_res = await session.execute(closing_stmt)
        closing = closing_res.scalars().first()

        opening_id = closing.opening_id if closing else closing_id

        # Verify opening entry exists if no closing entry found
        if not closing:
            opening_stmt = select(POSOpeningEntry).where(
                POSOpeningEntry.opening_id == opening_id,
                POSOpeningEntry.tenant_id == tenant_id,
            )
            opening_res = await session.execute(opening_stmt)
            opening = opening_res.scalars().first()
            if not opening:
                raise ValueError(f"Shift or closing entry {closing_id} not found.")

        # Find unconsolidated invoices for this shift
        inv_stmt = select(POSInvoice).where(
            POSInvoice.opening_id == opening_id,
            POSInvoice.tenant_id == tenant_id,
            POSInvoice.consolidated_invoice_id.is_(None),
        )
        inv_res = await session.execute(inv_stmt)
        invoices = inv_res.scalars().all()

        if not invoices:
            raise ValueError(f"No unconsolidated POS invoices found for this shift.")

        sales_invoices = [inv for inv in invoices if not inv.is_return]
        return_invoices = [inv for inv in invoices if inv.is_return]

        consolidated_sales_inv = None
        consolidated_credit_note = None

        if sales_invoices:
            total_sub = sum((inv.subtotal for inv in sales_invoices), Decimal("0.0000"))
            total_tax = sum((inv.tax_amount for inv in sales_invoices), Decimal("0.0000"))
            total_grand = sum((inv.grand_total for inv in sales_invoices), Decimal("0.0000"))

            consolidated_sales_inv = SalesInvoice(
                tenant_id=tenant_id,
                invoice_number=f"CONS-POS-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                customer_id=sales_invoices[0].customer_id,
                invoice_date=date.today(),
                due_date=date.today(),
                currency="USD",
                subtotal=total_sub,
                tax_amount=total_tax,
                total_amount=total_grand,
                status="PAID",
            )
            session.add(consolidated_sales_inv)
            await session.flush()

            for inv in sales_invoices:
                inv.consolidated_invoice_id = consolidated_sales_inv.invoice_id

        if return_invoices:
            ret_sub = sum((abs(inv.subtotal) for inv in return_invoices), Decimal("0.0000"))
            ret_tax = sum((abs(inv.tax_amount) for inv in return_invoices), Decimal("0.0000"))
            ret_grand = sum((abs(inv.grand_total) for inv in return_invoices), Decimal("0.0000"))

            consolidated_credit_note = CreditNote(
                tenant_id=tenant_id,
                credit_note_number=f"CONS-CN-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
                customer_id=return_invoices[0].customer_id,
                posting_date=date.today(),
                reason=f"Consolidated POS returns for shift {opening_id}",
                currency="USD",
                subtotal=ret_sub,
                tax_amount=ret_tax,
                total_amount=ret_grand,
                status="POSTED",
            )
            session.add(consolidated_credit_note)
            await session.flush()

            for inv in return_invoices:
                inv.consolidated_invoice_id = consolidated_credit_note.credit_note_id

        total_merged_amount = sum((inv.grand_total for inv in invoices), Decimal("0.0000"))

        merge_log = POSInvoiceMergeLog(
            tenant_id=tenant_id,
            closing_id=closing.closing_id if closing else None,
            opening_id=opening_id,
            consolidated_invoice_id=consolidated_sales_inv.invoice_id if consolidated_sales_inv else None,
            consolidated_credit_note_id=consolidated_credit_note.credit_note_id if consolidated_credit_note else None,
            total_invoices_merged=len(invoices),
            total_amount=total_merged_amount,
            posting_date=date.today(),
        )
        session.add(merge_log)
        await session.flush()
        return merge_log
