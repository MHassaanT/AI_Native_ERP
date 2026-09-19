// Expense Claim Receipt Extraction Contracts (PRD §Workforce Agent)

class ExpenseItemExtraction {
  merchant_name string @description("Name of merchant or establishment")
  category string @description("MEALS, LODGING, TRANSPORT, SUPPLIES, or OTHER")
  transaction_date string @description("ISO-8601 date YYYY-MM-DD")
  currency string @description("ISO currency code")
  total_amount float @description("Total receipt charge amount")
  tax_amount float @description("Taxes included on receipt")
  contains_alcohol bool @description("Flag if itemized charges contain alcoholic beverages")
  extraction_confidence float @description("Confidence score between 0.0 and 1.0")
}

function ExtractReceiptMetadata(receipt_text: string) -> ExpenseItemExtraction {
  client GeminiFlash
  prompt #"
    You are an automated corporate expense audit specialist.
    Extract structural metadata from the following receipt text, checking for compliance with standard corporate policies.

    Receipt Context:
    {{ receipt_text }}

    {{ ctx.output_format }}
  "#
}
