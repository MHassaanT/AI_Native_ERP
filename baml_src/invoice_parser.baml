// BAML Contract: High-Precision Accounts Payable Extraction (PRD §Supply Chain & Procurement)
// Enforces compile-time Schema-Aligned Parsing (SAP) over LLM outputs.

class InvoiceLineExtraction {
    item_code string @description("Matched SKU or internal inventory identifier")
    description string @description("Line description from the invoice")
    quantity float @description("Billed units")
    unit_price float @description("Price per unit excluding taxes")
    line_total float @description("Computed net total for the line")
    tax_rate float @description("Applicable tax rate as a decimal (e.g. 0.0825 for 8.25%)")
}

class InvoiceDocumentExtraction {
    vendor_tax_id string @description("Vendor VAT, EIN, or corporate tax identifier")
    invoice_number string @description("Vendor-issued invoice reference number")
    invoice_date string @description("Document date formatted as ISO-8601 YYYY-MM-DD")
    currency string @description("Standard 3-character ISO currency code")
    subtotal float
    tax_amount float
    total_amount float
    payment_terms_days int
    line_items InvoiceLineExtraction[]
    extraction_confidence float @description("Composite extraction confidence score between 0.0 and 1.0")
}

function ExtractInvoiceMetadata(invoice_pdf: image, ocr_extracted_text: string) -> InvoiceDocumentExtraction {
    client "google/gemini-3.6-flash"
    prompt #"
        You are an autonomous Accounts Payable Specialist embedded in an AI-Native ERP.
        Analyze the attached invoice image and OCR stream. Extract all structural accounting metadata.

        OCR Context:
        {{ ocr_extracted_text }}

        Document Media:
        {{ invoice_pdf }}

        {{ ctx.output_format }}
    "#
}
