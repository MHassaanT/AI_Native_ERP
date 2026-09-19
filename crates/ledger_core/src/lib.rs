//! Deterministic Ledger Core Invariant Verification (PRD §General Ledger Engine).
//!
//! Enforces mathematical zero-sum balancing, single-sided line constraints,
//! positive non-zero amounts, and enterprise autonomy ceilings.

use rust_decimal::prelude::*;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum LedgerError {
    #[error("Empty ledger entry: at least two balanced lines required")]
    EmptyEntry,
    #[error("Zero-sum invariant violated: Debits={debit_sum}, Credits={credit_sum}, Diff={diff}")]
    ZeroSumViolation {
        debit_sum: Decimal,
        credit_sum: Decimal,
        diff: Decimal,
    },
    #[error("Negative amounts are forbidden: debit={debit}, credit={credit}")]
    NegativeAmount { debit: Decimal, credit: Decimal },
    #[error("Line item on account '{account_code}' must be strictly single-sided (debit XOR credit)")]
    SingleSidedViolation { account_code: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerLine {
    pub account_code: String,
    pub cost_center: String,
    pub debit: Decimal,
    pub credit: Decimal,
    pub currency: String,
    pub exchange_rate: Decimal,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum AutonomyTier {
    Autonomous,      // Tier 1: <= $2,500
    DualSupervisor,  // Tier 2: <= $25,000
    HumanMandatory,  // Tier 3: > $25,000
}

/// Validates that SUM(debit) == SUM(credit), strictly positive, single-sided lines.
pub fn validate_zero_sum(lines: &[LedgerLine]) -> Result<Decimal, LedgerError> {
    if lines.is_empty() {
        return Err(LedgerError::EmptyEntry);
    }

    let zero = Decimal::ZERO;
    let mut total_debits = Decimal::ZERO;
    let mut total_credits = Decimal::ZERO;

    for line in lines {
        if line.debit < zero || line.credit < zero {
            return Err(LedgerError::NegativeAmount {
                debit: line.debit,
                credit: line.credit,
            });
        }

        let has_debit = line.debit > zero;
        let has_credit = line.credit > zero;

        // Strictly single-sided: debit XOR credit
        if (has_debit && has_credit) || (!has_debit && !has_credit) {
            return Err(LedgerError::SingleSidedViolation {
                account_code: line.account_code.clone(),
            });
        }

        total_debits += line.debit;
        total_credits += line.credit;
    }

    let diff = total_debits - total_credits;
    if !diff.is_zero() {
        return Err(LedgerError::ZeroSumViolation {
            debit_sum: total_debits,
            credit_sum: total_credits,
            diff,
        });
    }

    Ok(total_debits)
}

/// Evaluates transaction autonomy tier against financial governance thresholds.
pub fn evaluate_autonomy_tier(amount: Decimal) -> AutonomyTier {
    let tier1_ceiling = Decimal::new(2500, 0);   // $2,500.00
    let tier2_ceiling = Decimal::new(25000, 0);  // $25,000.00

    if amount <= tier1_ceiling {
        AutonomyTier::Autonomous
    } else if amount <= tier2_ceiling {
        AutonomyTier::DualSupervisor
    } else {
        AutonomyTier::HumanMandatory
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_zero_sum() {
        let lines = vec![
            LedgerLine {
                account_code: "1010".into(),
                cost_center: "CC-CORP".into(),
                debit: Decimal::new(1470000, 2),
                credit: Decimal::ZERO,
                currency: "USD".into(),
                exchange_rate: Decimal::ONE,
            },
            LedgerLine {
                account_code: "2010".into(),
                cost_center: "CC-CORP".into(),
                debit: Decimal::ZERO,
                credit: Decimal::new(1470000, 2),
                currency: "USD".into(),
                exchange_rate: Decimal::ONE,
            },
        ];
        let res = validate_zero_sum(&lines);
        assert!(res.is_ok());
        assert_eq!(res.unwrap(), Decimal::new(1470000, 2));
    }

    #[test]
    fn test_unbalanced_fails() {
        let lines = vec![
            LedgerLine {
                account_code: "1010".into(),
                cost_center: "CC-CORP".into(),
                debit: Decimal::new(100, 0),
                credit: Decimal::ZERO,
                currency: "USD".into(),
                exchange_rate: Decimal::ONE,
            },
            LedgerLine {
                account_code: "2010".into(),
                cost_center: "CC-CORP".into(),
                debit: Decimal::ZERO,
                credit: Decimal::new(99, 0),
                currency: "USD".into(),
                exchange_rate: Decimal::ONE,
            },
        ];
        assert!(validate_zero_sum(&lines).is_err());
    }
}
