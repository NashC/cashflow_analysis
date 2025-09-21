"""
Flow type classifier - CRITICAL for accurate cash flow calculation.

Priority order (MUST BE ENFORCED):
1. EXCLUDED - Credit card payments, loan payments
2. INTERNAL_TRANSFER - Between own accounts
3. INCOME - Money entering system
4. EXPENSE - Money leaving system
"""

import re
from decimal import Decimal
from datetime import timedelta
from typing import List, Optional, Tuple
import logging

from ..core.models import Transaction, CategorizationResult
from ..core.constants import (
    FlowType,
    EXCLUDED_CATEGORIES,
    INTERNAL_TRANSFER_CATEGORIES,
    TRANSFER_MATCH_DAYS,
    TRANSFER_AMOUNT_TOLERANCE,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW
)

logger = logging.getLogger(__name__)

class FlowTypeClassifier:
    """
    Classifies transactions into flow types.
    This is CRITICAL for accurate net cash flow calculation.
    """

    def __init__(self, transactions: Optional[List[Transaction]] = None):
        """
        Initialize classifier.

        Args:
            transactions: Optional list of all transactions for transfer pair detection
        """
        self.all_transactions = transactions or []
        self.excluded_patterns = self._compile_patterns(EXCLUDED_CATEGORIES)
        self.transfer_patterns = self._compile_patterns(INTERNAL_TRANSFER_CATEGORIES)

    def classify(self, transaction: Transaction) -> CategorizationResult:
        """
        Classify a transaction's flow type.

        CRITICAL LOGIC:
        1. Check EXCLUDED first (credit card payments, loans)
        2. Check INTERNAL_TRANSFER second (between accounts)
        3. Then classify as INCOME or EXPENSE based on amount

        Args:
            transaction: Transaction to classify

        Returns:
            CategorizationResult with flow type and confidence
        """
        # Step 1: Check for EXCLUDED transactions (highest priority)
        if self._is_excluded(transaction):
            return CategorizationResult(
                flow_type=FlowType.EXCLUDED,
                category=self._get_excluded_category(transaction),
                confidence=CONFIDENCE_HIGH,
                method="excluded_pattern"
            )

        # Step 2: Check for specific INCOME patterns (CRITICAL FIX)
        # This must come BEFORE transfer check to catch dividends correctly
        if transaction.amount > 0:
            income_result = self._check_income_patterns(transaction)
            if income_result:
                return income_result

        # Step 3: Check for INTERNAL_TRANSFER
        transfer_result = self._check_internal_transfer(transaction)
        if transfer_result:
            return transfer_result

        # Step 4: Classify as INCOME or EXPENSE based on amount
        if transaction.amount > 0:
            return CategorizationResult(
                flow_type=FlowType.INCOME,
                category="Uncategorized_Income",
                confidence=CONFIDENCE_HIGH,
                method="amount_positive"
            )
        else:
            return CategorizationResult(
                flow_type=FlowType.EXPENSE,
                category="Uncategorized_Expense",
                confidence=CONFIDENCE_HIGH,
                method="amount_negative"
            )

    def _is_excluded(self, transaction: Transaction) -> bool:
        """Check if transaction should be excluded from cash flow"""
        description = transaction.description.upper()

        # Check each excluded pattern
        for category, patterns in self.excluded_patterns.items():
            for pattern in patterns:
                if pattern.search(description):
                    logger.debug(f"Transaction '{description}' matched EXCLUDED pattern: {pattern.pattern}")
                    return True

        return False

    def _get_excluded_category(self, transaction: Transaction) -> str:
        """Get the specific excluded category"""
        description = transaction.description.upper()

        for category, patterns in self.excluded_patterns.items():
            for pattern in patterns:
                if pattern.search(description):
                    return category

        return "Excluded_Other"

    def _check_internal_transfer(self, transaction: Transaction) -> Optional[CategorizationResult]:
        """
        Check if transaction is an internal transfer.

        Uses two methods:
        1. Pattern matching for known transfer descriptions
        2. Finding matching opposite transactions (transfer pairs)
        """
        description = transaction.description.upper()

        # Method 1: Check transfer patterns
        for category, patterns in self.transfer_patterns.items():
            for pattern in patterns:
                if pattern.search(description):
                    logger.debug(f"Transaction '{description}' matched TRANSFER pattern: {pattern.pattern}")

                    # Try to find matching pair for higher confidence
                    has_pair = self._find_transfer_pair(transaction) is not None

                    return CategorizationResult(
                        flow_type=FlowType.INTERNAL_TRANSFER,
                        category=category,
                        confidence=CONFIDENCE_HIGH if has_pair else CONFIDENCE_MEDIUM,
                        method="transfer_pattern_with_pair" if has_pair else "transfer_pattern"
                    )

        # Method 2: Look for transfer pair even without pattern match
        # This catches transfers that don't match our patterns
        pair_transaction = self._find_transfer_pair(transaction)
        if pair_transaction:
            # Found a matching opposite transaction
            logger.debug(f"Found transfer pair for '{description}'")

            # Determine transfer direction
            if transaction.amount < 0:
                category = "To_Unknown_Account"
            else:
                category = "From_Unknown_Account"

            return CategorizationResult(
                flow_type=FlowType.INTERNAL_TRANSFER,
                category=category,
                confidence=CONFIDENCE_MEDIUM,
                method="transfer_pair_only"
            )

        return None

    def _find_transfer_pair(self, transaction: Transaction) -> Optional[Transaction]:
        """
        Find matching transfer pair (opposite amount within time window).

        A transfer pair is:
        - Opposite amount (within tolerance)
        - Within TRANSFER_MATCH_DAYS days
        - Not already paired
        """
        if not self.all_transactions:
            return None

        target_amount = -transaction.amount  # Looking for opposite
        target_date = transaction.date

        for other in self.all_transactions:
            # Skip self
            if other is transaction:
                continue

            # Skip if already paired
            if other.has_pair:
                continue

            # Check date window
            date_diff = abs((other.date - target_date).days)
            if date_diff > TRANSFER_MATCH_DAYS:
                continue

            # Check amount match (opposite with tolerance)
            amount_diff = abs(float(other.amount - target_amount))
            if amount_diff <= TRANSFER_AMOUNT_TOLERANCE:
                # Found a match!
                transaction.has_pair = True
                transaction.pair_id = f"{other.date}_{other.amount}"
                other.has_pair = True
                other.pair_id = f"{transaction.date}_{transaction.amount}"
                return other

        return None

    def _check_income_patterns(self, transaction: Transaction) -> Optional[CategorizationResult]:
        """
        Check for specific income patterns that should take priority over transfer detection.
        CRITICAL: This prevents dividends from being misclassified as transfers.
        """
        description = transaction.description.upper()

        # Import income patterns from constants
        from ..core.constants import INCOME_CATEGORIES

        # Compile income patterns
        income_patterns = self._compile_patterns(INCOME_CATEGORIES)

        # Check each income pattern
        for category, patterns in income_patterns.items():
            for pattern in patterns:
                if pattern.search(description):
                    logger.debug(f"Transaction '{description}' matched INCOME pattern: {pattern.pattern}")
                    return CategorizationResult(
                        flow_type=FlowType.INCOME,
                        category=category,
                        confidence=CONFIDENCE_HIGH,
                        method="income_pattern"
                    )

        return None

    def classify_all(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Classify all transactions in a list.

        Args:
            transactions: List of transactions to classify

        Returns:
            List of transactions with flow_type set
        """
        # Store all transactions for transfer pair detection
        self.all_transactions = transactions

        classified_count = {
            FlowType.INCOME: 0,
            FlowType.EXPENSE: 0,
            FlowType.INTERNAL_TRANSFER: 0,
            FlowType.EXCLUDED: 0
        }

        for transaction in transactions:
            result = self.classify(transaction)
            transaction.flow_type = result.flow_type
            transaction.category = result.category
            transaction.confidence = result.confidence

            classified_count[result.flow_type] += 1

        # Log classification summary
        logger.info("Flow type classification complete:")
        for flow_type, count in classified_count.items():
            logger.info(f"  {flow_type.value}: {count} transactions")

        # Validate classification
        self._validate_classification(transactions)

        return transactions

    def _validate_classification(self, transactions: List[Transaction]):
        """Validate that classification makes sense"""
        # Check that we have at least some income and expenses
        has_income = any(t.flow_type == FlowType.INCOME for t in transactions)
        has_expense = any(t.flow_type == FlowType.EXPENSE for t in transactions)

        if not has_income:
            logger.warning("No INCOME transactions found - this seems unusual")

        if not has_expense:
            logger.warning("No EXPENSE transactions found - this seems unusual")

        # Check for unclassified transactions
        unclassified = [t for t in transactions if t.flow_type is None]
        if unclassified:
            logger.error(f"Found {len(unclassified)} unclassified transactions")

    def _compile_patterns(self, category_dict: dict) -> dict:
        """Compile regex patterns for efficiency"""
        compiled = {}
        for category, patterns in category_dict.items():
            compiled[category] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]
        return compiled

    def reclassify_transaction(self, transaction: Transaction,
                             new_flow_type: FlowType,
                             reason: str = "user_override"):
        """
        Manually reclassify a transaction.

        Args:
            transaction: Transaction to reclassify
            new_flow_type: New flow type
            reason: Reason for reclassification
        """
        old_type = transaction.flow_type
        transaction.flow_type = new_flow_type
        transaction.user_verified = True
        transaction.confidence = 1.0  # User override has perfect confidence

        logger.info(f"Reclassified transaction from {old_type} to {new_flow_type}: "
                   f"{transaction.description[:50]} (${transaction.amount:.2f}) - {reason}")