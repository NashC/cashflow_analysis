"""
Test cash flow calculation - CRITICAL for accurate analysis.
These tests verify that the formula is correct:
net_cash_flow = total_income - total_true_expenses

Where internal transfers and excluded payments are NOT counted as expenses.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from src.core.models import Transaction
from src.core.constants import FlowType
from src.analysis.cashflow import CashFlowCalculator

class TestCashFlowCalculation:
    """Test the critical cash flow calculation logic"""

    def test_basic_cash_flow_formula(self):
        """Test the fundamental cash flow formula"""
        transactions = [
            # Income: $5000
            Transaction(
                date=datetime(2024, 1, 15),
                description="SALARY",
                amount=Decimal('5000'),
                balance=Decimal('5000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
            # True expenses: $2000
            Transaction(
                date=datetime(2024, 1, 16),
                description="RENT",
                amount=Decimal('-1800'),
                balance=Decimal('3200'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Housing"
            ),
            Transaction(
                date=datetime(2024, 1, 17),
                description="GROCERIES",
                amount=Decimal('-200'),
                balance=Decimal('3000'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Groceries"
            ),
            # Internal transfer: $1000 (NOT an expense)
            Transaction(
                date=datetime(2024, 1, 18),
                description="SAVINGS TRANSFER",
                amount=Decimal('-1000'),
                balance=Decimal('2000'),
                type="TRANSFER",
                flow_type=FlowType.INTERNAL_TRANSFER,
                category="To_Savings"
            ),
            # Excluded payment: $500 (NOT an expense)
            Transaction(
                date=datetime(2024, 1, 19),
                description="CREDIT CARD PAYMENT",
                amount=Decimal('-500'),
                balance=Decimal('1500'),
                type="DEBIT",
                flow_type=FlowType.EXCLUDED,
                category="Credit_Card_Payment"
            )
        ]

        calculator = CashFlowCalculator(transactions)
        summary = calculator.get_summary_metrics()

        # Verify the critical calculation
        assert summary['total_income'] == 5000.0
        assert summary['total_expenses'] == 2000.0  # Only rent + groceries
        assert summary['total_net_cash_flow'] == 3000.0  # $5000 - $2000

        # Verify transfers and excluded are tracked separately
        assert summary['total_transfers_out'] == 1000.0
        assert summary['total_excluded'] == 500.0

    def test_monthly_metrics_calculation(self):
        """Test monthly metrics calculation"""
        # Create transactions spanning multiple months
        transactions = [
            # January - Income $4000, Expenses $1500, Net $2500
            Transaction(
                date=datetime(2024, 1, 1),
                description="SALARY JAN",
                amount=Decimal('4000'),
                balance=Decimal('4000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
            Transaction(
                date=datetime(2024, 1, 15),
                description="RENT JAN",
                amount=Decimal('-1500'),
                balance=Decimal('2500'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Housing"
            ),
            Transaction(
                date=datetime(2024, 1, 20),
                description="SAVINGS JAN",
                amount=Decimal('-1000'),
                balance=Decimal('1500'),
                type="TRANSFER",
                flow_type=FlowType.INTERNAL_TRANSFER,
                category="To_Savings"
            ),

            # February - Income $4500, Expenses $1800, Net $2700
            Transaction(
                date=datetime(2024, 2, 1),
                description="SALARY FEB",
                amount=Decimal('4500'),
                balance=Decimal('6000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
            Transaction(
                date=datetime(2024, 2, 15),
                description="RENT FEB",
                amount=Decimal('-1500'),
                balance=Decimal('4500'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Housing"
            ),
            Transaction(
                date=datetime(2024, 2, 20),
                description="FOOD FEB",
                amount=Decimal('-300'),
                balance=Decimal('4200'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Groceries"
            ),
        ]

        calculator = CashFlowCalculator(transactions)
        monthly_metrics = calculator.calculate_monthly_metrics()

        # Should have 2 months
        assert len(monthly_metrics) == 2

        # January metrics
        jan_metrics = next(m for m in monthly_metrics if m.month == "2024-01")
        assert jan_metrics.gross_income == Decimal('4000')
        assert jan_metrics.true_expenses == Decimal('1500')
        assert jan_metrics.net_cash_flow == Decimal('2500')
        assert jan_metrics.internal_transfers_out == Decimal('1000')

        # February metrics
        feb_metrics = next(m for m in monthly_metrics if m.month == "2024-02")
        assert feb_metrics.gross_income == Decimal('4500')
        assert feb_metrics.true_expenses == Decimal('1800')
        assert feb_metrics.net_cash_flow == Decimal('2700')

    def test_category_breakdown(self):
        """Test category analysis"""
        transactions = [
            Transaction(
                date=datetime(2024, 1, 1),
                description="SALARY",
                amount=Decimal('5000'),
                balance=Decimal('5000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
            Transaction(
                date=datetime(2024, 1, 5),
                description="RENT",
                amount=Decimal('-1800'),
                balance=Decimal('3200'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Housing"
            ),
            Transaction(
                date=datetime(2024, 1, 10),
                description="GROCERIES",
                amount=Decimal('-300'),
                balance=Decimal('2900'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Groceries"
            ),
            Transaction(
                date=datetime(2024, 1, 15),
                description="RESTAURANT",
                amount=Decimal('-100'),
                balance=Decimal('2800'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Dining"
            ),
        ]

        calculator = CashFlowCalculator(transactions)
        category_analysis = calculator.get_category_analysis()

        # Check expense categories
        assert category_analysis['EXPENSE:Housing']['total'] == 1800.0
        assert category_analysis['EXPENSE:Groceries']['total'] == 300.0
        assert category_analysis['EXPENSE:Dining']['total'] == 100.0

        # Check percentages (of total expenses)
        total_expenses = 1800 + 300 + 100  # $2200
        assert abs(category_analysis['EXPENSE:Housing']['percentage'] - (1800/2200)*100) < 0.1

    def test_validation_catches_errors(self):
        """Test that validation catches calculation errors"""
        transactions = [
            Transaction(
                date=datetime(2024, 1, 1),
                description="SALARY",
                amount=Decimal('5000'),
                balance=Decimal('5000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
            # No expenses - should trigger warning
        ]

        calculator = CashFlowCalculator(transactions)
        validation = calculator.validate_cash_flow_calculation()

        # Should warn about no expenses
        assert any("EXPENSE" in warning for warning in validation['warnings'])

    def test_zero_amounts_handled(self):
        """Test that zero amounts are handled correctly"""
        transactions = [
            Transaction(
                date=datetime(2024, 1, 1),
                description="ADJUSTMENT",
                amount=Decimal('0'),
                balance=Decimal('1000'),
                type="ADJUSTMENT",
                flow_type=FlowType.EXPENSE,  # Even if classified as expense
                category="Other"
            ),
            Transaction(
                date=datetime(2024, 1, 2),
                description="SALARY",
                amount=Decimal('1000'),
                balance=Decimal('2000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
        ]

        calculator = CashFlowCalculator(transactions)
        summary = calculator.get_summary_metrics()

        # Zero amount shouldn't affect calculations
        assert summary['total_income'] == 1000.0
        assert summary['total_expenses'] == 0.0  # Zero amount doesn't count
        assert summary['total_net_cash_flow'] == 1000.0

    def test_large_numbers_precision(self):
        """Test that large numbers maintain precision"""
        transactions = [
            Transaction(
                date=datetime(2024, 1, 1),
                description="LARGE INCOME",
                amount=Decimal('999999.99'),
                balance=Decimal('999999.99'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Other_Income"
            ),
            Transaction(
                date=datetime(2024, 1, 2),
                description="LARGE EXPENSE",
                amount=Decimal('-999999.98'),
                balance=Decimal('0.01'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Other_Expense"
            ),
        ]

        calculator = CashFlowCalculator(transactions)
        summary = calculator.get_summary_metrics()

        # Should maintain precision
        assert summary['total_net_cash_flow'] == 0.01

    def test_savings_rate_calculation(self):
        """Test that savings rate is calculated correctly"""
        transactions = [
            Transaction(
                date=datetime(2024, 1, 1),
                description="SALARY",
                amount=Decimal('5000'),
                balance=Decimal('5000'),
                type="CREDIT",
                flow_type=FlowType.INCOME,
                category="Salary"
            ),
            Transaction(
                date=datetime(2024, 1, 15),
                description="EXPENSES",
                amount=Decimal('-3000'),
                balance=Decimal('2000'),
                type="DEBIT",
                flow_type=FlowType.EXPENSE,
                category="Various"
            ),
            Transaction(
                date=datetime(2024, 1, 20),
                description="SAVINGS",
                amount=Decimal('-1000'),
                balance=Decimal('1000'),
                type="TRANSFER",
                flow_type=FlowType.INTERNAL_TRANSFER,
                category="To_Savings"
            ),
        ]

        calculator = CashFlowCalculator(transactions)
        summary = calculator.get_summary_metrics()

        # Savings rate = (transfers_out / income) * 100 = (1000 / 5000) * 100 = 20%
        assert abs(summary['overall_savings_rate'] - 20.0) < 0.1

        # Expense ratio = (expenses / income) * 100 = (3000 / 5000) * 100 = 60%
        assert abs(summary['overall_expense_ratio'] - 60.0) < 0.1