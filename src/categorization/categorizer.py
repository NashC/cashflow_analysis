"""Transaction categorizer with regex patterns and fuzzy matching"""

import re
from typing import List, Optional, Dict, Tuple
import logging
from fuzzywuzzy import fuzz, process

from ..core.models import Transaction, CategorizationResult
from ..core.constants import (
    FlowType,
    INCOME_CATEGORIES,
    EXPENSE_CATEGORIES,
    INTERNAL_TRANSFER_CATEGORIES,
    EXCLUDED_CATEGORIES,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW
)

logger = logging.getLogger(__name__)

class TransactionCategorizer:
    """
    Categorizes transactions into detailed categories based on flow type.
    Uses regex patterns and fuzzy matching for merchant names.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize categorizer with optional configuration.

        Args:
            config: Optional configuration dict with custom rules
        """
        self.config = config or {}

        # Compile regex patterns for each flow type
        self.patterns = {
            FlowType.INCOME: self._compile_patterns(INCOME_CATEGORIES),
            FlowType.EXPENSE: self._compile_patterns(EXPENSE_CATEGORIES),
            FlowType.INTERNAL_TRANSFER: self._compile_patterns(INTERNAL_TRANSFER_CATEGORIES),
            FlowType.EXCLUDED: self._compile_patterns(EXCLUDED_CATEGORIES)
        }

        # Build merchant database for fuzzy matching
        self.merchant_database = self._build_merchant_database()

        # Load custom rules from config
        self.custom_rules = self._load_custom_rules()

        # Track categorization stats
        self.stats = {
            'total': 0,
            'categorized': 0,
            'uncategorized': 0,
            'by_method': {}
        }

    def categorize(self, transaction: Transaction) -> CategorizationResult:
        """
        Categorize a single transaction.

        Priority:
        1. User override (if set)
        2. Custom rules from config
        3. Regex pattern matching
        4. Fuzzy merchant matching
        5. Default to uncategorized

        Args:
            transaction: Transaction to categorize

        Returns:
            CategorizationResult with category and confidence
        """
        self.stats['total'] += 1

        # Check if user has already categorized
        if transaction.user_verified and transaction.user_category:
            return CategorizationResult(
                flow_type=transaction.flow_type,
                category=transaction.user_category,
                confidence=1.0,
                method="user_override"
            )

        # Check custom rules
        custom_result = self._check_custom_rules(transaction)
        if custom_result:
            self.stats['categorized'] += 1
            self._track_method('custom_rule')
            return custom_result

        # Check regex patterns based on flow type
        pattern_result = self._check_patterns(transaction)
        if pattern_result:
            self.stats['categorized'] += 1
            self._track_method('regex_pattern')
            return pattern_result

        # Try fuzzy matching for merchants
        fuzzy_result = self._fuzzy_match_merchant(transaction)
        if fuzzy_result:
            self.stats['categorized'] += 1
            self._track_method('fuzzy_match')
            return fuzzy_result

        # Default to uncategorized
        self.stats['uncategorized'] += 1
        self._track_method('uncategorized')

        default_category = self._get_default_category(transaction.flow_type)
        return CategorizationResult(
            flow_type=transaction.flow_type,
            category=default_category,
            confidence=CONFIDENCE_LOW,
            method="default"
        )

    def categorize_all(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Categorize all transactions in a list.

        Args:
            transactions: List of transactions to categorize

        Returns:
            List of transactions with categories set
        """
        logger.info(f"Starting categorization of {len(transactions)} transactions")

        # Reset stats
        self.stats = {
            'total': 0,
            'categorized': 0,
            'uncategorized': 0,
            'by_method': {}
        }

        category_counts = {}

        for transaction in transactions:
            # Skip if no flow type (should not happen)
            if not transaction.flow_type:
                logger.warning(f"Transaction has no flow type: {transaction.description[:50]}")
                continue

            result = self.categorize(transaction)
            transaction.category = result.category
            transaction.subcategory = result.subcategory
            transaction.confidence = result.confidence

            # Track category counts
            category_key = f"{transaction.flow_type.value}:{transaction.category}"
            category_counts[category_key] = category_counts.get(category_key, 0) + 1

        # Log categorization summary
        self._log_categorization_summary(category_counts)

        return transactions

    def _check_custom_rules(self, transaction: Transaction) -> Optional[CategorizationResult]:
        """Check custom rules from configuration"""
        if not self.custom_rules:
            return None

        description = transaction.description.upper()

        for rule in self.custom_rules:
            # Check if description contains the pattern
            if 'description_contains' in rule:
                if rule['description_contains'].upper() in description:
                    return CategorizationResult(
                        flow_type=transaction.flow_type,
                        category=rule.get('category', 'Custom'),
                        subcategory=rule.get('subcategory'),
                        confidence=rule.get('confidence', CONFIDENCE_HIGH),
                        method="custom_rule",
                        matched_pattern=rule['description_contains']
                    )

            # Check regex pattern
            if 'pattern' in rule:
                if re.search(rule['pattern'], description, re.IGNORECASE):
                    return CategorizationResult(
                        flow_type=transaction.flow_type,
                        category=rule.get('category', 'Custom'),
                        subcategory=rule.get('subcategory'),
                        confidence=rule.get('confidence', CONFIDENCE_HIGH),
                        method="custom_rule",
                        matched_pattern=rule['pattern']
                    )

        return None

    def _check_patterns(self, transaction: Transaction) -> Optional[CategorizationResult]:
        """Check regex patterns for the transaction's flow type"""
        if transaction.flow_type not in self.patterns:
            return None

        description = transaction.description.upper()
        flow_patterns = self.patterns[transaction.flow_type]

        # Check each category's patterns
        for category, patterns in flow_patterns.items():
            for pattern in patterns:
                if pattern.search(description):
                    logger.debug(f"Matched pattern '{pattern.pattern}' for category '{category}'")
                    return CategorizationResult(
                        flow_type=transaction.flow_type,
                        category=category,
                        confidence=CONFIDENCE_HIGH,
                        method="regex_pattern",
                        matched_pattern=pattern.pattern
                    )

        return None

    def _fuzzy_match_merchant(self, transaction: Transaction) -> Optional[CategorizationResult]:
        """Use fuzzy matching to find similar merchant names"""
        if not self.merchant_database:
            return None

        # Get fuzzy match threshold from config
        threshold = self.config.get('categorization', {}).get('fuzzy_match_threshold', 85)

        description = transaction.description.upper()

        # Try to find best match
        best_match = process.extractOne(
            description,
            self.merchant_database.keys(),
            scorer=fuzz.token_sort_ratio
        )

        if best_match and best_match[1] >= threshold:
            matched_merchant = best_match[0]
            category_info = self.merchant_database[matched_merchant]

            confidence = CONFIDENCE_HIGH if best_match[1] >= 95 else CONFIDENCE_MEDIUM

            return CategorizationResult(
                flow_type=transaction.flow_type,
                category=category_info['category'],
                subcategory=category_info.get('subcategory'),
                confidence=confidence,
                method="fuzzy_match",
                matched_pattern=matched_merchant
            )

        return None

    def _build_merchant_database(self) -> Dict[str, dict]:
        """Build a database of known merchants for fuzzy matching"""
        database = {}

        # Common merchant mappings
        merchant_mappings = {
            # Groceries
            'WHOLE FOODS': {'category': 'Groceries', 'flow_type': FlowType.EXPENSE},
            'TRADER JOES': {'category': 'Groceries', 'flow_type': FlowType.EXPENSE},
            'SAFEWAY': {'category': 'Groceries', 'flow_type': FlowType.EXPENSE},
            'KROGER': {'category': 'Groceries', 'flow_type': FlowType.EXPENSE},

            # Dining
            'STARBUCKS': {'category': 'Dining', 'subcategory': 'Coffee', 'flow_type': FlowType.EXPENSE},
            'CHIPOTLE': {'category': 'Dining', 'subcategory': 'Fast Food', 'flow_type': FlowType.EXPENSE},
            'MCDONALDS': {'category': 'Dining', 'subcategory': 'Fast Food', 'flow_type': FlowType.EXPENSE},
            'UBER EATS': {'category': 'Dining', 'subcategory': 'Delivery', 'flow_type': FlowType.EXPENSE},
            'DOORDASH': {'category': 'Dining', 'subcategory': 'Delivery', 'flow_type': FlowType.EXPENSE},

            # Shopping
            'AMAZON': {'category': 'Shopping', 'subcategory': 'Online', 'flow_type': FlowType.EXPENSE},
            'TARGET': {'category': 'Shopping', 'subcategory': 'General', 'flow_type': FlowType.EXPENSE},
            'WALMART': {'category': 'Shopping', 'subcategory': 'General', 'flow_type': FlowType.EXPENSE},
            'BEST BUY': {'category': 'Shopping', 'subcategory': 'Electronics', 'flow_type': FlowType.EXPENSE},

            # Transportation
            'SHELL': {'category': 'Transportation', 'subcategory': 'Gas', 'flow_type': FlowType.EXPENSE},
            'CHEVRON': {'category': 'Transportation', 'subcategory': 'Gas', 'flow_type': FlowType.EXPENSE},
            'UBER': {'category': 'Transportation', 'subcategory': 'Rideshare', 'flow_type': FlowType.EXPENSE},
            'LYFT': {'category': 'Transportation', 'subcategory': 'Rideshare', 'flow_type': FlowType.EXPENSE},

            # Subscriptions
            'NETFLIX': {'category': 'Subscriptions', 'subcategory': 'Entertainment', 'flow_type': FlowType.EXPENSE},
            'SPOTIFY': {'category': 'Subscriptions', 'subcategory': 'Music', 'flow_type': FlowType.EXPENSE},
            'AMAZON PRIME': {'category': 'Subscriptions', 'subcategory': 'Shopping', 'flow_type': FlowType.EXPENSE},
        }

        # Add merchant aliases from config
        if 'merchant_aliases' in self.config.get('categorization', {}):
            aliases = self.config['categorization']['merchant_aliases']
            for alias, standard in aliases.items():
                if standard in merchant_mappings:
                    database[alias] = merchant_mappings[standard]

        # Add all standard merchants
        database.update(merchant_mappings)

        return database

    def _load_custom_rules(self) -> List[dict]:
        """Load custom categorization rules from config"""
        if not self.config:
            return []

        return self.config.get('categorization', {}).get('custom_rules', [])

    def _compile_patterns(self, category_dict: dict) -> dict:
        """Compile regex patterns for efficiency"""
        compiled = {}
        for category, patterns in category_dict.items():
            compiled[category] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]
        return compiled

    def _get_default_category(self, flow_type: FlowType) -> str:
        """Get default category name for uncategorized transactions"""
        if flow_type == FlowType.INCOME:
            return "Other_Income"
        elif flow_type == FlowType.EXPENSE:
            return "Other_Expense"
        elif flow_type == FlowType.INTERNAL_TRANSFER:
            return "Other_Transfer"
        elif flow_type == FlowType.EXCLUDED:
            return "Other_Excluded"
        else:
            return "Unknown"

    def _track_method(self, method: str):
        """Track categorization method for statistics"""
        if method not in self.stats['by_method']:
            self.stats['by_method'][method] = 0
        self.stats['by_method'][method] += 1

    def _log_categorization_summary(self, category_counts: dict):
        """Log summary of categorization results"""
        logger.info("Categorization complete:")
        logger.info(f"  Total: {self.stats['total']}")
        logger.info(f"  Categorized: {self.stats['categorized']} "
                   f"({self.stats['categorized']/max(self.stats['total'], 1)*100:.1f}%)")
        logger.info(f"  Uncategorized: {self.stats['uncategorized']} "
                   f"({self.stats['uncategorized']/max(self.stats['total'], 1)*100:.1f}%)")

        if self.stats['by_method']:
            logger.info("Categorization methods:")
            for method, count in self.stats['by_method'].items():
                logger.info(f"  {method}: {count}")

        # Log top categories
        if category_counts:
            sorted_categories = sorted(category_counts.items(),
                                     key=lambda x: x[1],
                                     reverse=True)
            logger.info("Top 10 categories:")
            for category, count in sorted_categories[:10]:
                logger.info(f"  {category}: {count}")

    def get_low_confidence_transactions(self, transactions: List[Transaction],
                                       threshold: float = CONFIDENCE_MEDIUM) -> List[Transaction]:
        """
        Get transactions with low confidence categorization.

        Args:
            transactions: List of categorized transactions
            threshold: Confidence threshold

        Returns:
            List of transactions below confidence threshold
        """
        return [t for t in transactions if t.confidence < threshold]