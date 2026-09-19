// Revenue & CRM RFQ Parsing Contracts (PRD §Revenue Agent)

class RFQLineItem {
  requested_sku string @description("Target SKU or descriptive item name")
  quantity float @description("Requested quantity")
  uom string @description("Units of measure (e.g. Nos, Kg, Meters)")
  target_unit_price float? @description("Target price if specified by customer")
  custom_specifications string? @description("Technical tolerances, color, or packaging requirements")
}

class RFQExtraction {
  customer_name string @description("Name or company of customer")
  customer_email string? @description("Customer contact email")
  rfq_reference string? @description("Customer RFQ reference code")
  required_delivery_date string? @description("Customer deadline formatted as YYYY-MM-DD")
  line_items RFQLineItem[]
  commercial_urgency string @description("STANDARD, EXPEDITED, or CRITICAL")
  extraction_confidence float
}

function ParseRFQDocument(rfq_text: string) -> RFQExtraction {
  client GeminiPro
  prompt #"
    You are an autonomous Revenue & Commercial Sales Agent.
    Parse the following inbound customer RFQ inquiry. Extract all target line items, requested quantities, technical specifications, and timeline constraints.

    Customer RFQ Text:
    {{ rfq_text }}

    {{ ctx.output_format }}
  "#
}
