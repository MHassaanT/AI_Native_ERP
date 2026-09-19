"""Exceptions raised by the Deterministic Ledger Engine."""


class LedgerError(Exception):
    """Base exception for all ledger engine operations."""

    pass


class ZeroSumViolation(LedgerError):
    """Raised when sum(debits) does not equal sum(credits)."""

    def __init__(self, debit_sum, credit_sum, difference):
        self.debit_sum = debit_sum
        self.credit_sum = credit_sum
        self.difference = difference
        super().__init__(
            f"Zero-sum invariant violated: debits={debit_sum}, credits={credit_sum}, difference={difference}"
        )


class SingleSidedViolation(LedgerError):
    """Raised when a single line item contains both debit and credit or neither."""

    pass


class NegativeAmountViolation(LedgerError):
    """Raised when an entry has negative debit or credit."""

    pass


class PeriodLockedError(LedgerError):
    """Raised when posting date falls into a locked fiscal period."""

    def __init__(self, posting_date, fiscal_year, fiscal_period):
        self.posting_date = posting_date
        self.fiscal_year = fiscal_year
        self.fiscal_period = fiscal_period
        super().__init__(
            f"Cannot post to locked fiscal period: year={fiscal_year}, period={fiscal_period}, date={posting_date}"
        )


class AccountNotFoundError(LedgerError):
    """Raised when account_code does not exist or is inactive in Chart of Accounts."""

    def __init__(self, account_code):
        self.account_code = account_code
        super().__init__(f"Account code not found or inactive: '{account_code}'")


class CostCenterNotFoundError(LedgerError):
    """Raised when cost_center does not exist or is inactive."""

    def __init__(self, cost_center):
        self.cost_center = cost_center
        super().__init__(f"Cost center not found or inactive: '{cost_center}'")


class AutonomyCeilingExceeded(LedgerError):
    """Raised when transaction total exceeds agent autonomy ceiling and lacks human approval."""

    def __init__(self, total_amount, ceiling_amount, tier):
        self.total_amount = total_amount
        self.ceiling_amount = ceiling_amount
        self.tier = tier
        super().__init__(
            f"Autonomy ceiling exceeded for {tier}: amount={total_amount} > ceiling={ceiling_amount}. Requires human authorization."
        )
