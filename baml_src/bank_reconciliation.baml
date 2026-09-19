// Continuous Bank Reconciliation Contracts (PRD §Bank Reconciliation)

class BankTransactionExtraction {
  counterparty_name string @description("Normalized recipient or payer entity name")
  reference_code string? @description("Invoice, order, or mandate reference extracted from narrative")
  remittance_purpose string @description("Description of payment purpose")
  confidence_score float @description("Confidence score between 0.0 and 1.0")
}

function ExtractBankRemittance(transaction_narrative: string) -> BankTransactionExtraction {
  client GeminiFlash
  prompt #"
    You are an automated open-banking treasury matching specialist.
    Analyze the following raw bank transaction statement narrative. Extract the normalized counterparty name and any embedded invoice or reference codes.

    Bank Narrative:
    {{ transaction_narrative }}

    {{ ctx.output_format }}
  "#
}
