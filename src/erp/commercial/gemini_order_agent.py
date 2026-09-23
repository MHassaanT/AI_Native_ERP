"""Gemini-powered Inbound Email Order Analysis & Catalog Grounding Agent."""

import json
import logging
import os
import re
from typing import Any
import uuid

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.config import settings
from erp.db.models.inventory import Item, StockLevel, Warehouse
from erp.db.session import async_session_factory

logger = logging.getLogger(__name__)


class AnalyzedItemLine(BaseModel):
    """Structured line item extracted from email and matched against product catalog."""

    raw_item_query: str
    requested_qty: float
    matched_item_code: str | None = None
    matched_item_name: str | None = None
    item_id: str | None = None
    catalog_status: str = Field(
        default="NOT_IN_CATALOG",
        description="'EXACT_MATCH', 'FUZZY_MATCH', or 'NOT_IN_CATALOG'",
    )
    unit_price: float = 0.0
    line_total: float = 0.0
    available_stock: float = 0.0
    is_in_stock: bool = False


class EmailOrderAnalysis(BaseModel):
    """Complete structured commercial analysis of an inbound email."""

    is_order: bool = False
    intent: str = Field(
        default="INQUIRY",
        description="'ORDER', 'RFQ', 'INQUIRY', 'SUPPLIER_BILL', or 'OTHER'",
    )
    confidence: float = 0.90
    customer_name: str = "Commercial Client"
    customer_email: str = "customer@client.com"
    po_reference: str = "PO-INBOUND"
    items: list[AnalyzedItemLine] = []
    can_fulfill: bool = False
    fulfillment_action: str = Field(
        default="NON_ORDER_INQUIRY",
        description="'FULFILL_AND_INVOICE', 'ITEM_NOT_IN_CATALOG', 'BACKORDER_SHORTAGE', or 'NON_ORDER_INQUIRY'",
    )
    total_price: float = 0.0
    explanation: str = ""
    recommended_alternatives: list[dict[str, Any]] = []
    draft_email_response: str = ""


class GeminiEmailOrderAnalyzer:
    """Analyzes customer emails via Gemini 2.0 Flash grounded in the tenant's actual PostgreSQL catalog."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    @property
    def api_key(self) -> str | None:
        return (
            self._api_key
            or os.environ.get("GEMINI_API_KEY")
            or getattr(settings, "GEMINI_API_KEY", None)
            or None
        )

    async def fetch_tenant_catalog(
        self, tenant_id: uuid.UUID, session: AsyncSession | None = None
    ) -> list[dict[str, Any]]:
        """Retrieves tenant's real active product catalog and available warehouse inventory."""

        async def _query(s: AsyncSession) -> list[dict[str, Any]]:
            items_stmt = select(Item).where(Item.tenant_id == tenant_id, Item.is_active.is_(True))
            items = (await s.execute(items_stmt)).scalars().all()

            wh_stmt = select(Warehouse).where(
                Warehouse.tenant_id == tenant_id, Warehouse.is_active.is_(True)
            )
            all_whs = (await s.execute(wh_stmt)).scalars().all()
            default_wh = all_whs[0] if all_whs else None

            catalog_list = []
            for it in items:
                # Query stock across all active warehouses for this item
                stk_stmt = (
                    select(StockLevel, Warehouse)
                    .join(Warehouse, Warehouse.warehouse_id == StockLevel.warehouse_id)
                    .where(
                        StockLevel.tenant_id == tenant_id,
                        StockLevel.item_id == it.item_id,
                        Warehouse.is_active.is_(True),
                    )
                )
                stk_rows = (await s.execute(stk_stmt)).all()
                total_avail = sum(float(r[0].available_qty) for r in stk_rows)
                total_curr = sum(float(r[0].current_qty) for r in stk_rows)

                best_wh = next((r[1] for r in stk_rows if r[0].available_qty > 0), default_wh)
                wh_id = str(best_wh.warehouse_id) if best_wh else None
                wh_code = best_wh.warehouse_code if best_wh else "MAIN-WH"

                catalog_list.append(
                    {
                        "item_id": str(it.item_id),
                        "item_code": it.item_code,
                        "item_name": it.item_name,
                        "description": it.description or "",
                        "standard_rate": float(it.standard_rate),
                        "stock_uom": it.stock_uom,
                        "available_qty": total_avail,
                        "current_qty": total_curr,
                        "warehouse_id": wh_id,
                        "warehouse_code": wh_code,
                    }
                )
            return catalog_list

        if session is not None:
            return await _query(session)
        async with async_session_factory() as s:
            return await _query(s)

    async def analyze_inbound_email(
        self,
        tenant_id: uuid.UUID,
        sender: str,
        subject: str,
        body_text: str,
        session: AsyncSession | None = None,
    ) -> EmailOrderAnalysis:
        """Grounds email in live PostgreSQL catalog and uses Gemini (or grounded deterministic fallback) to evaluate."""
        catalog = await self.fetch_tenant_catalog(tenant_id, session)

        # Attempt Gemini 2.0 Flash if API Key is available
        key = self.api_key
        if key:
            try:
                analysis = await self._call_gemini(catalog, sender, subject, body_text, key)
                if analysis:
                    return analysis
            except Exception as e:
                logger.warning("Gemini email order analysis failed (%s); falling back to deterministic catalog matcher.", e)

        # Grounded Deterministic Catalog Fallback
        return self._deterministic_catalog_analysis(catalog, sender, subject, body_text)

    async def _call_gemini(
        self,
        catalog: list[dict[str, Any]],
        sender: str,
        subject: str,
        body_text: str,
        api_key: str,
    ) -> EmailOrderAnalysis | None:
        """Invokes Gemini 2.0 Flash / 1.5 Flash with structured JSON output schema."""
        catalog_summary = json.dumps(
            [
                {
                    "item_code": c["item_code"],
                    "item_name": c["item_name"],
                    "standard_rate": c["standard_rate"],
                    "available_qty": c["available_qty"],
                    "uom": c["stock_uom"],
                }
                for c in catalog
            ],
            indent=2,
        )

        prompt = (
            "You are the Chief Autonomous Commercial Operations Agent for an enterprise ERP.\n"
            "Analyze the following inbound email from a customer in relation to our live database catalog and inventory.\n\n"
            "=== OUR LIVE PRODUCT CATALOG & INVENTORY ===\n"
            f"{catalog_summary}\n\n"
            "=== INCOMING EMAIL ===\n"
            f"Sender: {sender}\n"
            f"Subject: {subject}\n"
            f"Body:\n{body_text}\n\n"
            "=== YOUR INSTRUCTIONS ===\n"
            "1. Determine if this email is a firm Purchase Order ('ORDER') or an RFQ, inquiry, or other.\n"
            "2. Extract customer name from sender name or sign-off (e.g. 'Hassaan Tahir') and email.\n"
            "3. Extract all requested products, quantities, and look up matching items in OUR CATALOG.\n"
            "   - If the customer requests an item NOT in our catalog (e.g. CHASHM-002 when only CHASHM-001 exists), mark catalog_status = 'NOT_IN_CATALOG', matched_item_code = null, is_in_stock = false.\n"
            "   - If the item DOES exist in our catalog, pull the catalog's standard_rate, compute line_total = quantity * standard_rate, and check if available_qty >= requested_qty.\n"
            "4. Decide can_fulfill:\n"
            "   - TRUE only if is_order=true, all items are in our catalog, and available stock >= requested quantity.\n"
            "5. Determine fulfillment_action:\n"
            "   - 'FULFILL_AND_INVOICE' if can_fulfill is true.\n"
            "   - 'ITEM_NOT_IN_CATALOG' if any item requested does not exist in our catalog.\n"
            "   - 'BACKORDER_SHORTAGE' if items exist in catalog but requested quantity exceeds available stock.\n"
            "   - 'NON_ORDER_INQUIRY' if not an order.\n"
            "6. Draft a polite, professional email response:\n"
            "   - If ITEM_NOT_IN_CATALOG: Inform the customer that the requested SKU is not in our product catalog, and present available active catalog alternatives with their prices.\n"
            "   - If FULFILL_AND_INVOICE: Confirm their order and state that their invoice PDF has been generated and attached.\n"
            "   - If BACKORDER_SHORTAGE: Inform of stock shortage and 7-day backorder replenishment timeline.\n\n"
            "Output strictly valid JSON matching this schema:\n"
            "{\n"
            '  "is_order": bool,\n'
            '  "intent": "ORDER" | "RFQ" | "INQUIRY" | "OTHER",\n'
            '  "confidence": float,\n'
            '  "customer_name": str,\n'
            '  "customer_email": str,\n'
            '  "po_reference": str,\n'
            '  "items": [\n'
            '    {\n'
            '      "raw_item_query": str,\n'
            '      "requested_qty": float,\n'
            '      "matched_item_code": str or null,\n'
            '      "matched_item_name": str or null,\n'
            '      "catalog_status": "EXACT_MATCH" | "FUZZY_MATCH" | "NOT_IN_CATALOG",\n'
            '      "unit_price": float,\n'
            '      "line_total": float,\n'
            '      "available_stock": float,\n'
            '      "is_in_stock": bool\n'
            '    }\n'
            '  ],\n'
            '  "can_fulfill": bool,\n'
            '  "fulfillment_action": "FULFILL_AND_INVOICE" | "ITEM_NOT_IN_CATALOG" | "BACKORDER_SHORTAGE" | "NON_ORDER_INQUIRY",\n'
            '  "total_price": float,\n'
            '  "explanation": str,\n'
            '  "recommended_alternatives": [{"item_code": str, "item_name": str, "standard_rate": float, "available_qty": float}],\n'
            '  "draft_email_response": str\n'
            "}"
        )

        configured_model = os.getenv("GEMINI_MODEL", getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash"))
        clean_model = configured_model.removeprefix("models/")
        candidate_models = [clean_model]
        for fallback in ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        async with httpx.AsyncClient(timeout=20.0) as client:
            for model_name in candidate_models:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    resp = await client.post(
                        endpoint,
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {
                                "response_mime_type": "application/json",
                                "temperature": 0.1,
                            },
                        },
                    )
                    if resp.status_code == 404:
                        logger.warning("Gemini model %s returned 404; trying fallback model.", model_name)
                        continue
                    if not resp.is_success:
                        logger.warning("Gemini API error (%s) for model %s: %s", resp.status_code, model_name, resp.text)
                        continue

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        logger.warning("Gemini API returned no candidates for model %s", model_name)
                        continue

                    raw_text = candidates[0]["content"]["parts"][0]["text"]
                    parsed = json.loads(raw_text)

                    # Map matched item_ids back from catalog
                    for item in parsed.get("items", []):
                        matched_code = item.get("matched_item_code")
                        if matched_code:
                            catalog_match = next((c for c in catalog if c["item_code"].lower() == matched_code.lower()), None)
                            if catalog_match:
                                item["item_id"] = catalog_match["item_id"]
                                item["unit_price"] = catalog_match["standard_rate"]
                                item["line_total"] = item["requested_qty"] * catalog_match["standard_rate"]
                                item["available_stock"] = catalog_match["available_qty"]
                                item["is_in_stock"] = catalog_match["available_qty"] >= item["requested_qty"]
                                item["catalog_status"] = "EXACT_MATCH"

                    all_cat = all(it.get("catalog_status") in ("EXACT_MATCH", "FUZZY_MATCH") for it in parsed.get("items", []))
                    all_stk = all(it.get("is_in_stock", False) for it in parsed.get("items", []))
                    parsed["can_fulfill"] = bool(parsed.get("is_order", False) and all_cat and all_stk)
                    parsed["total_price"] = sum(item.get("line_total", 0.0) for item in parsed.get("items", []))

                    return EmailOrderAnalysis(**parsed)
                except Exception as ex:
                    logger.warning("Error calling Gemini model %s: %s", model_name, ex)
                    continue

            return None

    def _deterministic_catalog_analysis(
        self,
        catalog: list[dict[str, Any]],
        sender: str,
        subject: str,
        body_text: str,
    ) -> EmailOrderAnalysis:
        """High-precision deterministic grounded catalog matcher supporting multi-line items."""
        combined = f"{subject}\n{body_text}".strip()
        combined_lower = combined.lower()

        # 1. Detect Customer Name & Email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", sender)
        cust_email = email_match.group(0) if email_match else "customer@external.com"

        # Sign-off name or sender display name
        name_match = re.search(r"(?:regards|thanks|sincerely|cheers)[,\s]+([A-Za-z\s]{2,40})", body_text, re.IGNORECASE)
        if name_match:
            cust_name = name_match.group(1).strip().split("\n")[0].strip()
        elif "<" in sender:
            cust_name = sender.split("<")[0].strip().replace('"', "")
        elif "@" in cust_email:
            local = cust_email.split("@")[0].replace(".", " ").title()
            cust_name = local
        else:
            cust_name = "Valued Customer"

        # 2. Determine Intent
        order_keywords = ["order", "purchase order", "po#", "po-", "pieces of", "units of", "please deliver", "firm order"]
        is_order = any(k in combined_lower for k in order_keywords)
        intent = "ORDER" if is_order else ("RFQ" if "quote" in combined_lower or "rfq" in combined_lower else "INQUIRY")

        # PO reference
        po_match = re.search(r"\b(PO[-_\s]?[A-Za-z0-9-]+)\b", combined, re.IGNORECASE)
        po_ref = po_match.group(1).upper().replace(" ", "-") if po_match else f"PO-{uuid.uuid4().hex[:6].upper()}"

        # 3. Extract All Ordered Products and Quantities
        found_pairs: list[tuple[str, float]] = []

        if body_text.startswith("Subject:"):
            parts = body_text.split("\n\n", 1)
            subj = parts[0].replace("Subject:", "").strip()
            clean_body = parts[1] if len(parts) > 1 else ""
            if not subject:
                subject = subj
        else:
            clean_body = body_text

        # Prioritize body_text where order details are specified, fallback to subject+body
        text_to_scan = clean_body if len(clean_body.strip()) > 5 else combined

        # 1. Search known catalog items with strict hyphen-aware boundaries
        sorted_cat = sorted(catalog, key=lambda c: len(c["item_code"]), reverse=True)
        for c in sorted_cat:
            cat_pat = re.compile(r"(?<![-A-Za-z0-9_])" + re.escape(c["item_code"]) + r"(?![-A-Za-z0-9_])", re.IGNORECASE)
            if cat_pat.search(text_to_scan):
                before_m = re.search(r"(?<![-A-Za-z0-9_])(\d+(?:\.\d+)?)\s*(?:pieces|units|pcs|items|nos|box|boxes)?\s*(?:of)?\s*" + re.escape(c["item_code"]) + r"(?![-A-Za-z0-9_])", text_to_scan, re.IGNORECASE)
                after_m = re.search(r"(?<![-A-Za-z0-9_])" + re.escape(c["item_code"]) + r"(?![-A-Za-z0-9_])\s*[:=-]\s*(\d+(?:\.\d+)?)\s*(?:pieces|units|pcs|items|nos)?", text_to_scan, re.IGNORECASE)
                if before_m:
                    qty = float(before_m.group(1))
                    if not any(p[0].lower() == c["item_code"].lower() for p in found_pairs):
                        found_pairs.append((c["item_code"], qty))
                elif after_m:
                    qty = float(after_m.group(1))
                    if not any(p[0].lower() == c["item_code"].lower() for p in found_pairs):
                        found_pairs.append((c["item_code"], qty))
                elif not found_pairs:
                    qty_gen = re.search(r"(?<![-A-Za-z0-9_])(\d+(?:\.\d+)?)\s*(?:pieces|units|pcs|items|nos|box|boxes)", text_to_scan, re.IGNORECASE)
                    qty = float(qty_gen.group(1)) if qty_gen else 10.0
                    found_pairs.append((c["item_code"], qty))

        # 2. Search for other/unknown SKU patterns (e.g. uncatalogued items)
        pattern_qty_sku = re.compile(r"(?<![-A-Za-z0-9_])(\d+(?:\.\d+)?)\s*(?:pieces|units|pcs|items|nos|box|boxes)?\s*(?:of)?\s+([A-Za-z0-9_-]{3,30})(?![-A-Za-z0-9_])", re.IGNORECASE)
        for m in pattern_qty_sku.finditer(text_to_scan):
            qty = float(m.group(1))
            token = m.group(2).strip()
            if not token.isdigit() and not token.upper().startswith(("PO-", "INV-", "DN-", "SO-", "REF-")):
                if token.lower() not in {"order", "units", "pieces", "pcs", "prompt", "delivery", "accept", "purchase", "total", "regards", "customer", "please"}:
                    if not any(p[0].lower() == token.lower() for p in found_pairs):
                        found_pairs.append((token, qty))

        # Pattern: "<SKU> [:=-] <quantity>"
        pattern_sku_qty = re.compile(r"(?<![-A-Za-z0-9_])([A-Za-z0-9_-]{3,30})(?![-A-Za-z0-9_])\s*[:=-]\s*(\d+(?:\.\d+)?)\s*(?:pieces|units|pcs|items|nos)?", re.IGNORECASE)
        for m in pattern_sku_qty.finditer(text_to_scan):
            token = m.group(1).strip()
            qty = float(m.group(2))
            if not token.isdigit() and not token.upper().startswith(("PO-", "INV-", "DN-", "SO-", "REF-")):
                if token.lower() not in {"order", "units", "pieces", "pcs", "prompt", "delivery", "accept", "purchase", "total", "regards", "customer", "please"}:
                    if not any(p[0].lower() == token.lower() for p in found_pairs):
                        found_pairs.append((token, qty))

        # Fallback: Check combined text if body yielded nothing
        if not found_pairs:
            for c in sorted_cat:
                cat_pat = re.compile(r"(?<![-A-Za-z0-9_])" + re.escape(c["item_code"]) + r"(?![-A-Za-z0-9_])", re.IGNORECASE)
                if cat_pat.search(combined):
                    before_m = re.search(r"(?<![-A-Za-z0-9_])(\d+(?:\.\d+)?)\s*(?:pieces|units|pcs|items|nos|box|boxes)?\s*(?:of)?\s*" + re.escape(c["item_code"]) + r"(?![-A-Za-z0-9_])", combined, re.IGNORECASE)
                    qty = float(before_m.group(1)) if before_m else 10.0
                    if not any(p[0].lower() == c["item_code"].lower() for p in found_pairs):
                        found_pairs.append((c["item_code"], qty))

        # Fallback for unknown SKU tokens
        if not found_pairs:
            sku_token_match = re.search(r"\b(FG-[A-Za-z0-9-]+|[A-Za-z0-9]{2,15}(?:-[A-Za-z0-9]+)+)\b", combined)
            if sku_token_match and not sku_token_match.group(1).upper().startswith(("PO-", "INV-", "DN-", "SO-")):
                found_pairs.append((sku_token_match.group(1).strip(), 10.0))
            else:
                found_pairs.append(("UNKNOWN-ITEM", 10.0))

        # 4. Ground and Analyze Each Item Against Tenant Catalog
        items: list[AnalyzedItemLine] = []
        all_catalog_matched = True
        all_in_stock = True

        for raw_sku, qty_val in found_pairs:
            matched_cat = next((c for c in catalog if c["item_code"].strip().lower() == raw_sku.lower()), None)
            if matched_cat:
                avail = matched_cat["available_qty"]
                in_stk = avail >= qty_val
                rate = matched_cat["standard_rate"]
                lt = qty_val * rate
                if not in_stk:
                    all_in_stock = False

                items.append(
                    AnalyzedItemLine(
                        raw_item_query=raw_sku,
                        requested_qty=qty_val,
                        matched_item_code=matched_cat["item_code"],
                        matched_item_name=matched_cat["item_name"],
                        item_id=matched_cat["item_id"],
                        catalog_status="EXACT_MATCH",
                        unit_price=rate,
                        line_total=lt,
                        available_stock=avail,
                        is_in_stock=in_stk,
                    )
                )
            else:
                all_catalog_matched = False
                all_in_stock = False
                items.append(
                    AnalyzedItemLine(
                        raw_item_query=raw_sku,
                        requested_qty=qty_val,
                        matched_item_code=None,
                        matched_item_name=None,
                        item_id=None,
                        catalog_status="NOT_IN_CATALOG",
                        unit_price=0.0,
                        line_total=0.0,
                        available_stock=0.0,
                        is_in_stock=False,
                    )
                )

        total_price = sum(item.line_total for item in items)
        can_fulfill = bool(is_order and all_catalog_matched and all_in_stock)

        if not all_catalog_matched:
            action = "ITEM_NOT_IN_CATALOG"
            missing = [it.raw_item_query for it in items if it.catalog_status == "NOT_IN_CATALOG"]
            explanation = f"Requested item(s) {', '.join(missing)} do not exist in the product catalog."
            alts = [
                {
                    "item_code": c["item_code"],
                    "item_name": c["item_name"],
                    "standard_rate": c["standard_rate"],
                    "available_qty": c["available_qty"],
                }
                for c in catalog
            ]
            alt_lines = "\n".join(
                [f"- {a['item_code']}: {a['item_name']} (${a['standard_rate']:,.2f} each, {a['available_qty']:,.0f} available)" for a in alts]
            )
            draft_resp = (
                f"Dear {cust_name},\n\n"
                f"Thank you for contacting us. We received your order request for {', '.join(missing)}.\n\n"
                f"However, the following product(s) are not currently available in our product catalog: {', '.join(missing)}.\n\n"
                f"Our available products and current stock include:\n\n"
                f"{alt_lines}\n\n"
                f"Please let us know if you would like to proceed with an order for any of these available items.\n\n"
                f"Best regards,\nAutonomous Sales & Customer Success"
            )
        elif not all_in_stock:
            action = "BACKORDER_SHORTAGE"
            short_items = [it.matched_item_code for it in items if not it.is_in_stock]
            explanation = f"Stock shortage for item(s): {', '.join(short_items)}."
            draft_resp = (
                f"Dear {cust_name},\n\n"
                f"Thank you for your order. We have verified stock for your requested items.\n\n"
                f"We currently have insufficient on-hand inventory to immediately fulfill: {', '.join(short_items)}. "
                f"We have automatically placed your order on priority backorder and initiated a manufacturing replenishment. "
                f"The estimated delivery lead time is 7 business days.\n\n"
                f"Best regards,\nAutonomous Supply Chain Operations"
            )
        else:
            action = "FULFILL_AND_INVOICE"
            explanation = f"All {len(items)} requested item(s) are in catalog and in stock."
            lines_summary = "\n".join(
                f"- {it.requested_qty:,.0f} units of {it.matched_item_code} ({it.matched_item_name}) @ ${it.unit_price:,.2f} = ${it.line_total:,.2f}"
                for it in items
            )
            draft_resp = (
                f"Dear {cust_name},\n\n"
                f"Thank you for your order! We have confirmed your purchase for the following items:\n\n"
                f"{lines_summary}\n\n"
                f"Total Amount: ${total_price:,.2f} USD\n\n"
                f"Your items have been allocated from our warehouse and dispatched. Please find your official "
                f"Sales Invoice attached.\n\n"
                f"Best regards,\nAutonomous Revenue & Fulfillment Agent"
            )

        return EmailOrderAnalysis(
            is_order=is_order,
            intent=intent,
            confidence=0.92,
            customer_name=cust_name,
            customer_email=cust_email,
            po_reference=po_ref,
            items=items,
            can_fulfill=can_fulfill,
            fulfillment_action=action,
            total_price=total_price,
            explanation=explanation,
            recommended_alternatives=[
                {
                    "item_code": c["item_code"],
                    "item_name": c["item_name"],
                    "standard_rate": c["standard_rate"],
                    "available_qty": c["available_qty"],
                }
                for c in catalog
            ],
            draft_email_response=draft_resp,
        )


gemini_order_analyzer = GeminiEmailOrderAnalyzer()
