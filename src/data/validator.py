"""Data validation and integrity checks"""

import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import logging

from ..core.models import Transaction, ValidationResult
from ..core.constants import BALANCE_TOLERANCE
from ..core.exceptions import BalanceReconciliationError, ValidationError

logger = logging.getLogger(__name__)

class DataValidator:
    """
    Validates transaction data integrity including:
    - Balance reconciliation
    - Date continuity
    - Duplicate detection
    - Data quality checks
    """

    def __init__(self, transactions: List[Transaction]):
        """Initialize with transaction list"""
        self.transactions = transactions
        self.validation_result = ValidationResult(is_valid=True)

    def validate(self) -> ValidationResult:
        """
        Run all validation checks.

        Returns:
            ValidationResult with details of any issues found
        """
        logger.info(f"Starting validation of {len(self.transactions)} transactions")

        # Run validation checks
        self._check_empty_data()
        self._check_date_continuity()
        self._check_duplicates()
        self._validate_balances()
        self._check_data_quality()

        # Determine overall validity
        self.validation_result.is_valid = (
            len(self.validation_result.errors) == 0 and
            len(self.validation_result.balance_discrepancies) == 0
        )

        self._log_validation_summary()
        return self.validation_result

    def _check_empty_data(self):
        """Check if we have any data to validate"""
        if not self.transactions:
            self.validation_result.errors.append("No transactions to validate")
            self.validation_result.is_valid = False
            return

        self.validation_result.total_rows = len(self.transactions)

    def _check_date_continuity(self):
        """Check for gaps in transaction dates"""
        if len(self.transactions) < 2:
            return

        # Sort by date
        sorted_trans = sorted(self.transactions, key=lambda t: t.date)

        # Check for gaps (excluding weekends)
        gaps = []
        for i in range(1, len(sorted_trans)):
            prev_date = sorted_trans[i-1].date
            curr_date = sorted_trans[i].date

            # Calculate business days between dates
            days_diff = (curr_date - prev_date).days

            # Flag if gap is more than 5 business days (a week with weekend)
            if days_diff > 5:
                gaps.append((prev_date, curr_date))

        if gaps:
            self.validation_result.date_gaps = gaps
            for gap in gaps[:3]:  # Report first 3 gaps
                self.validation_result.warnings.append(
                    f"Date gap detected: {gap[0].strftime('%Y-%m-%d')} to "
                    f"{gap[1].strftime('%Y-%m-%d')} ({(gap[1] - gap[0]).days} days)"
                )

    def _check_duplicates(self):
        """Detect potential duplicate transactions"""
        duplicates = []
        seen = {}

        for i, trans in enumerate(self.transactions):
            # Create a key for duplicate detection
            # Same date, amount, and similar description
            key = (
                trans.date.date(),  # Just the date, not time
                float(trans.amount),
                trans.description[:20]  # First 20 chars of description
            )

            if key in seen:
                duplicates.append(i)
                trans.is_duplicate = True
                self.validation_result.warnings.append(
                    f"Potential duplicate at row {i}: {trans.date.strftime('%Y-%m-%d')} "
                    f"${trans.amount:.2f} {trans.description[:30]}"
                )
            else:
                seen[key] = i

        self.validation_result.duplicate_transactions = duplicates

    def _validate_balances(self):
        """Validate that running balance matches calculated balance"""
        # Only validate if we have balance data
        if not any(trans.balance != 0 for trans in self.transactions):
            self.validation_result.warnings.append(
                "No balance data available for reconciliation"
            )
            return

        # Sort by date for proper balance calculation
        sorted_trans = sorted(self.transactions, key=lambda t: t.date)

        # Find first transaction with a balance
        start_idx = 0
        starting_balance = None
        for i, trans in enumerate(sorted_trans):
            if trans.balance != 0:
                starting_balance = trans.balance - trans.amount
                start_idx = i
                break

        if starting_balance is None:
            self.validation_result.warnings.append(
                "Could not find starting balance for reconciliation"
            )
            return

        # Validate running balance
        running_balance = starting_balance
        discrepancies = []

        for i in range(start_idx, len(sorted_trans)):
            trans = sorted_trans[i]

            # Calculate expected balance
            running_balance += trans.amount
            expected_balance = running_balance

            # Check against actual balance if provided
            if trans.balance != 0:
                actual_balance = trans.balance
                diff = abs(float(expected_balance - actual_balance))

                if diff > BALANCE_TOLERANCE:
                    discrepancies.append(
                        (i, expected_balance, actual_balance)
                    )

                    # Update running balance to actual to continue validation
                    running_balance = actual_balance

        if discrepancies:
            self.validation_result.balance_discrepancies = discrepancies

            # Report balance discrepancies as warnings (CSV balance data often unreliable)
            self.validation_result.warnings.append(
                f"Found {len(discrepancies)} CSV balance discrepancies. "
                "This is common with bank exports and doesn't affect transaction-based analysis."
            )

            # Report first few discrepancies for debugging
            for i, (idx, expected, actual) in enumerate(discrepancies[:3]):
                self.validation_result.warnings.append(
                    f"CSV balance discrepancy at row {idx}: Expected ${float(expected):.2f}, "
                    f"got ${float(actual):.2f}, diff ${abs(float(expected - actual)):.2f}"
                )

            # Add summary if many discrepancies
            if len(discrepancies) > 3:
                self.validation_result.warnings.append(
                    f"... and {len(discrepancies) - 3} more CSV balance discrepancies"
                )

    def _check_data_quality(self):
        """Check overall data quality"""
        # Check for missing descriptions
        missing_desc = sum(1 for t in self.transactions if not t.description)
        if missing_desc > 0:
            self.validation_result.warnings.append(
                f"{missing_desc} transactions have empty descriptions"
            )

        # Check for zero amounts
        zero_amounts = sum(1 for t in self.transactions if t.amount == 0)
        if zero_amounts > 0:
            self.validation_result.warnings.append(
                f"{zero_amounts} transactions have zero amount"
            )

        # Check for extreme values (potential data errors)
        amounts = [abs(float(t.amount)) for t in self.transactions]
        if amounts:
            mean_amount = np.mean(amounts)
            std_amount = np.std(amounts)

            extreme_transactions = [
                t for t in self.transactions
                if abs(float(t.amount)) > mean_amount + (5 * std_amount)
            ]

            if extreme_transactions:
                self.validation_result.warnings.append(
                    f"{len(extreme_transactions)} transactions have extreme values "
                    f"(>5 standard deviations from mean)"
                )

        # Count valid rows
        self.validation_result.valid_rows = len(self.transactions) - len(
            self.validation_result.duplicate_transactions
        )
        self.validation_result.error_rows = len(
            self.validation_result.duplicate_transactions
        )

    def _log_validation_summary(self):
        """Log validation summary"""
        result = self.validation_result

        logger.info(f"Validation complete: {'PASSED' if result.is_valid else 'FAILED'}")
        logger.info(f"Total transactions: {result.total_rows}")
        logger.info(f"Valid transactions: {result.valid_rows}")

        if result.errors:
            logger.error(f"Found {len(result.errors)} errors:")
            for error in result.errors[:5]:
                logger.error(f"  - {error}")

        if result.warnings:
            logger.warning(f"Found {len(result.warnings)} warnings:")
            for warning in result.warnings[:5]:
                logger.warning(f"  - {warning}")

    def fix_duplicates(self, strategy: str = "keep_first") -> List[Transaction]:
        """
        Remove duplicate transactions based on strategy.

        Args:
            strategy: 'keep_first', 'keep_last', or 'interactive'

        Returns:
            List of transactions with duplicates removed
        """
        if strategy not in ["keep_first", "keep_last", "interactive"]:
            raise ValidationError(f"Invalid duplicate strategy: {strategy}")

        if not self.validation_result.duplicate_transactions:
            return self.transactions

        # Create a set of indices to remove
        to_remove = set(self.validation_result.duplicate_transactions)

        if strategy == "keep_first":
            # Keep first occurrence (duplicates already marked)
            pass
        elif strategy == "keep_last":
            # Would need to recalculate to keep last
            raise NotImplementedError("keep_last strategy not yet implemented")
        elif strategy == "interactive":
            # Would need UI for user to choose
            raise NotImplementedError("interactive strategy not yet implemented")

        # Filter out duplicates
        clean_transactions = [
            trans for i, trans in enumerate(self.transactions)
            if i not in to_remove
        ]

        logger.info(f"Removed {len(to_remove)} duplicate transactions")
        return clean_transactions

    def get_balance_report(self) -> pd.DataFrame:
        """
        Generate a balance reconciliation report.

        Returns:
            DataFrame with balance reconciliation details
        """
        if not self.transactions:
            return pd.DataFrame()

        data = []
        sorted_trans = sorted(self.transactions, key=lambda t: t.date)

        running_balance = Decimal('0')
        for trans in sorted_trans:
            running_balance += trans.amount

            data.append({
                'date': trans.date,
                'description': trans.description[:50],
                'amount': float(trans.amount),
                'calculated_balance': float(running_balance),
                'reported_balance': float(trans.balance) if trans.balance else None,
                'difference': float(trans.balance - running_balance)
                             if trans.balance else None
            })

        return pd.DataFrame(data)