"""
Test flow type classification - CRITICAL for accurate cash flow calculation.
These tests ensure that transactions are correctly classified as:
- INCOME (money entering)
- EXPENSE (money leaving)
- INTERNAL_TRANSFER (between own accounts)
- EXCLUDED (debt payments already counted elsewhere)
"""

import pytest
from decimal import Decimal
from datetime import datetime

from src.core.models import Transaction
from src.core.constants import FlowType
from src.categorization.flow_classifier import FlowTypeClassifier

class TestFlowTypeClassifier:
    """Test the critical flow type classification"""

    def setup_method(self):
        """Set up test fixtures"""
        self.classifier = FlowTypeClassifier()

    def test_excluded_classification(self):
        """Test that debt payments are correctly excluded"""
        # Credit card payment - should be EXCLUDED
        cc_payment = Transaction(
            date=datetime.now(),
            description="CHASE CARD AUTOPAY",
            amount=Decimal('-1500.00'),
            balance=Decimal('2000.00'),
            type="ACH_DEBIT"
        )

        result = self.classifier.classify(cc_payment)
        assert result.flow_type == FlowType.EXCLUDED
        assert "Credit_Card_Payment" in result.category
        assert result.confidence > 0.8

        # Auto loan payment - should be EXCLUDED
        loan_payment = Transaction(
            date=datetime.now(),
            description="AUTO LOAN PAYMENT",
            amount=Decimal('-425.00'),
            balance=Decimal('1575.00'),
            type="ACH_DEBIT"
        )

        result = self.classifier.classify(loan_payment)
        assert result.flow_type == FlowType.EXCLUDED
        assert "Loan_Payment" in result.category

    def test_internal_transfer_classification(self):
        """Test that internal transfers are correctly identified"""
        # Transfer to savings - should be INTERNAL_TRANSFER
        savings_transfer = Transaction(
            date=datetime.now(),
            description="TRANSFER TO SAVINGS",
            amount=Decimal('-1000.00'),
            balance=Decimal('1000.00'),
            type="TRANSFER"
        )

        result = self.classifier.classify(savings_transfer)
        assert result.flow_type == FlowType.INTERNAL_TRANSFER
        assert "To_Savings" in result.category

        # Investment transfer - should be INTERNAL_TRANSFER
        investment_transfer = Transaction(
            date=datetime.now(),
            description="CHARLES SCHWAB TRANSFER",
            amount=Decimal('-2000.00'),
            balance=Decimal('3000.00'),
            type="ACH_DEBIT"
        )

        result = self.classifier.classify(investment_transfer)
        assert result.flow_type == FlowType.INTERNAL_TRANSFER
        assert "To_Investment" in result.category

    def test_income_classification(self):
        """Test that income is correctly identified"""
        # Payroll - should be INCOME
        payroll = Transaction(
            date=datetime.now(),
            description="DIRECT DEP PAYROLL COMPANY",
            amount=Decimal('5000.00'),
            balance=Decimal('8000.00'),
            type="ACH_CREDIT"
        )

        result = self.classifier.classify(payroll)
        assert result.flow_type == FlowType.INCOME
        assert result.confidence > 0.8

        # Any positive amount should default to INCOME
        positive_transaction = Transaction(
            date=datetime.now(),
            description="UNKNOWN CREDIT",
            amount=Decimal('100.00'),
            balance=Decimal('3100.00'),
            type="CREDIT"
        )

        result = self.classifier.classify(positive_transaction)
        assert result.flow_type == FlowType.INCOME

    def test_expense_classification(self):
        """Test that expenses are correctly identified"""
        # Negative amount that's not transfer or excluded should be EXPENSE
        grocery = Transaction(
            date=datetime.now(),
            description="WHOLE FOODS MARKET",
            amount=Decimal('-85.50'),
            balance=Decimal('2914.50'),
            type="DEBIT_CARD"
        )

        result = self.classifier.classify(grocery)
        assert result.flow_type == FlowType.EXPENSE

        # Restaurant - should be EXPENSE
        restaurant = Transaction(
            date=datetime.now(),
            description="CHIPOTLE MEXICAN GRILL",
            amount=Decimal('-12.50'),
            balance=Decimal('2902.00'),
            type="DEBIT_CARD"
        )

        result = self.classifier.classify(restaurant)
        assert result.flow_type == FlowType.EXPENSE

    def test_classification_priority(self):
        """Test that classification follows correct priority order"""
        # A transaction that could match multiple patterns
        # Should be classified as EXCLUDED (highest priority)
        ambiguous = Transaction(
            date=datetime.now(),
            description="CHASE CARD PAYMENT TRANSFER",  # Contains both patterns
            amount=Decimal('-1000.00'),
            balance=Decimal('2000.00'),
            type="ACH_DEBIT"
        )

        result = self.classifier.classify(ambiguous)
        # Should be EXCLUDED because it's checked first
        assert result.flow_type == FlowType.EXCLUDED

    def test_transfer_pair_detection(self):
        """Test that transfer pairs are correctly identified"""
        transactions = [
            Transaction(
                date=datetime(2024, 1, 15),
                description="TRANSFER OUT UNKNOWN",
                amount=Decimal('-500.00'),
                balance=Decimal('2000.00'),
                type="TRANSFER"
            ),
            Transaction(
                date=datetime(2024, 1, 16),  # Next day
                description="TRANSFER IN UNKNOWN",
                amount=Decimal('500.00'),
                balance=Decimal('2500.00'),
                type="TRANSFER"
            )
        ]

        classifier = FlowTypeClassifier(transactions)

        result1 = classifier.classify(transactions[0])
        result2 = classifier.classify(transactions[1])

        # Both should be classified as transfers
        assert result1.flow_type == FlowType.INTERNAL_TRANSFER
        assert result2.flow_type == FlowType.INTERNAL_TRANSFER

        # They should be marked as having pairs
        assert transactions[0].has_pair
        assert transactions[1].has_pair

    def test_classification_validation(self):
        """Test overall classification validation"""
        # Create a realistic set of transactions
        transactions = [
            # Income
            Transaction(datetime.now(), "PAYROLL", Decimal('5000'), Decimal('5000'), "CREDIT"),
            # Expenses
            Transaction(datetime.now(), "RENT", Decimal('-1800'), Decimal('3200'), "DEBIT"),
            Transaction(datetime.now(), "GROCERIES", Decimal('-100'), Decimal('3100'), "DEBIT"),
            # Transfer
            Transaction(datetime.now(), "SAVINGS TRANSFER", Decimal('-1000'), Decimal('2100'), "TRANSFER"),
            # Excluded
            Transaction(datetime.now(), "CREDIT CARD PAYMENT", Decimal('-300'), Decimal('1800'), "DEBIT"),
        ]

        classifier = FlowTypeClassifier()
        classified = classifier.classify_all(transactions)

        # All should be classified
        assert all(t.flow_type is not None for t in classified)

        # Should have all flow types represented
        flow_types = {t.flow_type for t in classified}
        assert FlowType.INCOME in flow_types
        assert FlowType.EXPENSE in flow_types
        assert FlowType.INTERNAL_TRANSFER in flow_types
        assert FlowType.EXCLUDED in flow_types

    def test_critical_cash_flow_formula(self):
        """Test that the classification supports correct cash flow calculation"""
        transactions = [
            # Income: $5000
            Transaction(datetime.now(), "SALARY", Decimal('5000'), Decimal('5000'), "CREDIT"),

            # True expenses: $1900 total
            Transaction(datetime.now(), "RENT", Decimal('-1800'), Decimal('3200'), "DEBIT"),
            Transaction(datetime.now(), "FOOD", Decimal('-100'), Decimal('3100'), "DEBIT"),

            # Internal transfer: $1000 (NOT expense)
            Transaction(datetime.now(), "SAVINGS TRANSFER", Decimal('-1000'), Decimal('2100'), "TRANSFER"),

            # Excluded: $500 (NOT expense)
            Transaction(datetime.now(), "CREDIT CARD PAYMENT", Decimal('-500'), Decimal('1600'), "DEBIT"),
        ]

        classifier = FlowTypeClassifier()
        classified = classifier.classify_all(transactions)

        # Calculate what the net cash flow should be
        income = sum(t.amount for t in classified if t.flow_type == FlowType.INCOME)
        expenses = sum(abs(t.amount) for t in classified if t.flow_type == FlowType.EXPENSE)

        # Net cash flow = Income - True Expenses = $5000 - $1900 = $3100
        net_cash_flow = income - expenses

        assert income == Decimal('5000')
        assert expenses == Decimal('1900')  # Only rent + food
        assert net_cash_flow == Decimal('3100')  # The correct answer

        # Verify transfers and excluded are NOT counted in expenses
        transfers = sum(abs(t.amount) for t in classified if t.flow_type == FlowType.INTERNAL_TRANSFER)
        excluded = sum(abs(t.amount) for t in classified if t.flow_type == FlowType.EXCLUDED)

        assert transfers == Decimal('1000')
        assert excluded == Decimal('500')

        # These should NOT be part of the expense calculation
        assert expenses != Decimal('3400')  # Wrong if including transfers/excluded