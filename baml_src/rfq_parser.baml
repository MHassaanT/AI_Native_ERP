// BAML Contract: High-Precision RFQ & Commercial Inquiry Extraction (PRD §Revenue & CRM Agent)
// Enforces compile-time Schema-Aligned Parsing (SAP) over LLM outputs.

class RFQLineItem {
    item_code string? @description("Matched internal inventory SKU or part number")
    description string @description("Customer specification, materials, tolerances")
    quantity float @description("Requested production units")
    target_delivery_date string? @description("Target completion date in ISO-8601 YYYY-MM-DD")
    target_unit_budget float? @description("Target price or budget indicated by customer")
}

class RFQDocumentExtraction {
    customer_name string @description("Company or organization requesting the quote")
    customer_email string @description("Sender or reply-to email address")
    commercial_urgency string @description("STANDARD, EXPEDITED, or AOG_EMERGENCY")
    line_items RFQLineItem[] @description("Extracted line item requirements")
    technical_specifications string[] @description("Key manufacturing tolerances and standards (e.g. AS9100, IP67)")
    target_delivery_deadline string? @description("Global deadline constraint")
    extraction_confidence float @description("Extraction confidence score between 0.0 and 1.0")
}

function ExtractRFQMetadata(inquiry_email_body: string, attachment_document: image?) -> RFQDocumentExtraction {
    client "google/gemini-3.6-flash"
    prompt #"
        You are an autonomous Revenue & CRM Specialist embedded in an AI-Native ERP.
        Parse the customer's inbound commercial RFQ email and attached engineering specifications.
        Extract all line items, quantities, material grades, and delivery deadlines.

        Inquiry Email Text:
        {{ inquiry_email_body }}

        Attached Drawing / Spec:
        {{ attachment_document }}

        {{ ctx.output_format }}
    "#
}
