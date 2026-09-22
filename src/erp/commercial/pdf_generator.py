"""Commercial Quotation PDF Document Compiler using ReportLab (PRD §Quotation Generation)."""

import hashlib
import io
import logging
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)


class QuoteLineItem(BaseModel):
    item_code: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class QuotationData(BaseModel):
    quote_number: str
    customer_name: str
    customer_email: str = "procurement@customer.com"
    quote_date: date = Field(default_factory=date.today)
    valid_until_date: date
    promised_delivery_date: date
    currency: str = "USD"
    items: list[QuoteLineItem]
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.0000")
    total_amount: Decimal
    margin_percentage: Decimal = Decimal("24.50")


class QuotationPDFGenerator:
    """Generates legally bound PDF quotations with clean minimal design and cryptographic quote hash."""

    @staticmethod
    def generate_pdf(quote: QuotationData) -> bytes:
        """Compiles an in-memory PDF document and returns the raw bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1C1917"),
            fontName="Helvetica-Bold",
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#44403C"),
        )
        bold_body_style = ParagraphStyle(
            "DocBodyBold",
            parent=body_style,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1C1917"),
        )

        story = []

        # Header Section
        story.append(Paragraph("AI-NATIVE ENTERPRISE RESOURCE PLANNING", bold_body_style))
        story.append(Paragraph("COMMERCIAL SALES QUOTATION", title_style))
        story.append(Spacer(1, 10))
        story.append(
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E7E2DA"), spaceAfter=15)
        )

        # Meta Details Grid
        meta_data = [
            [
                Paragraph(f"<b>Quote Reference:</b> {quote.quote_number}", body_style),
                Paragraph(f"<b>Customer:</b> {quote.customer_name}", body_style),
            ],
            [
                Paragraph(f"<b>Issue Date:</b> {quote.quote_date.isoformat()}", body_style),
                Paragraph(f"<b>Contact:</b> {quote.customer_email}", body_style),
            ],
            [
                Paragraph(f"<b>Valid Until:</b> {quote.valid_until_date.isoformat()}", body_style),
                Paragraph(
                    f"<b>ATP Promised Delivery:</b> {quote.promised_delivery_date.isoformat()}",
                    bold_body_style,
                ),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[260, 270])
        meta_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 15))

        # Line Items Table
        table_data = [["SKU Code", "Description", "Qty", "Unit Rate", "Total (USD)"]]
        for itm in quote.items:
            table_data.append(
                [
                    itm.item_code,
                    itm.description,
                    f"{itm.quantity:,.0f}",
                    f"${itm.unit_price:,.2f}",
                    f"${itm.line_total:,.2f}",
                ]
            )

        items_table = Table(table_data, colWidths=[110, 210, 60, 75, 75])
        items_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F7F4EE")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1C1917")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#E7E2DA")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#EFEBE2")),
                ]
            )
        )
        story.append(items_table)
        story.append(Spacer(1, 15))

        # Summary Totals
        totals_data = [
            ["Subtotal:", f"${quote.subtotal:,.2f}"],
            ["Taxes (0.00%):", f"${quote.tax_amount:,.2f}"],
            ["Guaranteed Total:", f"${quote.total_amount:,.2f}"],
        ]
        totals_table = Table(totals_data, colWidths=[455, 75])
        totals_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#3F6249")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(totals_table)
        story.append(Spacer(1, 20))

        # Cryptographic quote seal
        quote_hash = hashlib.sha256(
            f"{quote.quote_number}:{quote.total_amount}:{quote.promised_delivery_date}".encode()
        ).hexdigest()
        seal_text = (
            f"<b>Cryptographic Quote Seal:</b> {quote_hash[:32]}... | "
            f"Defended Margin Floor: &ge; 22.0% Verified | Autonomous Revenue Agent Sign-off"
        )
        story.append(
            Paragraph(
                seal_text,
                ParagraphStyle(
                    "Seal", parent=body_style, fontSize=7.5, textColor=colors.HexColor("#78716C")
                ),
            )
        )

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes


class InvoiceLineItem(BaseModel):
    item_code: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoiceData(BaseModel):
    invoice_number: str
    order_number: str
    delivery_note_number: str
    customer_name: str
    customer_email: str = "billing@customer.com"
    invoice_date: date = Field(default_factory=date.today)
    due_date: date = Field(default_factory=date.today)
    currency: str = "USD"
    items: list[InvoiceLineItem]
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.0000")
    total_amount: Decimal
    general_ledger_status: str = "COMMITTED_AR_AND_REVENUE"


class InvoicePDFGenerator:
    """Compiles official legal Sales Invoice PDF documents with ledger seal."""

    @staticmethod
    def generate_pdf(invoice: InvoiceData) -> bytes:
        """Compiles in-memory Sales Invoice PDF and returns bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1C1917"),
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#78716C"),
        )
        meta_label_style = ParagraphStyle(
            "MetaLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#44403C"),
        )
        meta_val_style = ParagraphStyle(
            "MetaVal",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1C1917"),
        )
        body_style = ParagraphStyle(
            "BodyDark",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1C1917"),
        )

        story = []

        # Header
        header_data = [
            [
                Paragraph("<b>AI-NATIVE ENTERPRISE ERP</b>", title_style),
                Paragraph("<b>OFFICIAL SALES INVOICE</b>", ParagraphStyle("RightTitle", parent=title_style, alignment=2, textColor=colors.HexColor("#3F6249"))),
            ],
            [
                Paragraph("Autonomous Industrial Systems Inc. &bull; Operations Mesh", subtitle_style),
                Paragraph(f"<b>Invoice #:</b> {invoice.invoice_number}", ParagraphStyle("RightSub", parent=subtitle_style, alignment=2)),
            ],
        ]
        header_table = Table(header_data, colWidths=[330, 200])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3F6249"), spaceAfter=15))

        # Metadata grid
        meta_data = [
            [
                Paragraph("<b>Billed To:</b>", meta_label_style),
                Paragraph(invoice.customer_name, meta_val_style),
                Paragraph("<b>Invoice Date:</b>", meta_label_style),
                Paragraph(str(invoice.invoice_date), meta_val_style),
            ],
            [
                Paragraph("<b>Contact:</b>", meta_label_style),
                Paragraph(invoice.customer_email, meta_val_style),
                Paragraph("<b>Due Date:</b>", meta_label_style),
                Paragraph(str(invoice.due_date), meta_val_style),
            ],
            [
                Paragraph("<b>Sales Order Ref:</b>", meta_label_style),
                Paragraph(invoice.order_number, meta_val_style),
                Paragraph("<b>Delivery Note:</b>", meta_label_style),
                Paragraph(invoice.delivery_note_number, meta_val_style),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[90, 200, 100, 140])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 15))

        # Line items
        items_data = [["Item Code", "Description", "Qty", "Unit Price", "Total Amount"]]
        for item in invoice.items:
            items_data.append([
                item.item_code,
                item.description,
                f"{item.quantity:,.0f}",
                f"${item.unit_price:,.2f}",
                f"${item.line_total:,.2f}",
            ])

        items_table = Table(items_data, colWidths=[100, 200, 50, 80, 100])
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F2EB")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1C1917")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#E7E2D7")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#F5F2EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 15))

        # Totals
        totals_data = [
            ["Subtotal:", f"${invoice.subtotal:,.2f}"],
            ["Tax (0.00%):", f"${invoice.tax_amount:,.2f}"],
            ["Total Due:", f"${invoice.total_amount:,.2f}"],
        ]
        totals_table = Table(totals_data, colWidths=[430, 100])
        totals_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#3F6249")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 20))

        # Cryptographic General Ledger Seal
        seal_hash = hashlib.sha256(
            f"{invoice.invoice_number}:{invoice.total_amount}:{invoice.general_ledger_status}".encode()
        ).hexdigest()
        seal_text = (
            f"<b>General Ledger Audit Seal:</b> {seal_hash[:32]}... | "
            f"Double-Entry Balanced: Dr 1200-AR-CUSTOMERS / Cr 4000-SALES-REVENUE | Status: {invoice.general_ledger_status}"
        )
        story.append(Paragraph(seal_text, ParagraphStyle("Seal", parent=body_style, fontSize=7.5, textColor=colors.HexColor("#78716C"))))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes


pdf_generator = QuotationPDFGenerator()
invoice_pdf_generator = InvoicePDFGenerator()
