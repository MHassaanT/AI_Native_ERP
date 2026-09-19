"""Open-Banking Feed Ingestor (PRD §Bank Reconciliation)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RawBankTransaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: f"bank_tx_{uuid.uuid4().hex[:10]}")
    account_number: str
    booking_date: date
    value_date: date
    amount: Decimal
    currency: str = "USD"
    counterparty_name: str
    counterparty_iban: str | None = None
    remittance_information: str = ""
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BankFeedIngestor:
    """Ingests raw transactions from open-banking webhooks and ISO 20022 / CAMT feeds."""

    @staticmethod
    def parse_webhook_payload(payload: dict) -> RawBankTransaction:
        """Parses standardized JSON open-banking webhook payload."""
        return RawBankTransaction(
            transaction_id=payload.get("transaction_id", f"bank_tx_{uuid.uuid4().hex[:10]}"),
            account_number=payload.get("account_number", "ACC-OPERATING-01"),
            booking_date=date.fromisoformat(payload.get("booking_date", date.today().isoformat())),
            value_date=date.fromisoformat(payload.get("value_date", date.today().isoformat())),
            amount=Decimal(str(payload["amount"])),
            currency=payload.get("currency", "USD"),
            counterparty_name=payload["counterparty_name"],
            counterparty_iban=payload.get("counterparty_iban"),
            remittance_information=payload.get("remittance_information", ""),
        )


bank_feed_ingestor = BankFeedIngestor()
