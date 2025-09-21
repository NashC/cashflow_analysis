"""Enhanced cash flow analysis with mortgage interest integration"""

from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime
import logging
from collections import defaultdict

from ..core.models import Transaction, MonthlyMetrics
from ..core.constants import FlowType
from ..data.mortgage_loader import MortgageDataLoader, MortgageTransaction
from .cashflow import CashFlowCalculator

logger = logging.getLogger(__name__)

class EnhancedCashFlowCalculator(CashFlowCalculator):
    """Enhanced cash flow calculator that includes mortgage interest as operating expense"""

    def __init__(self, transactions: List[Transaction], mortgage_data_path: Optional[str] = None):
        super().__init__(transactions)
        self.mortgage_data_path = mortgage_data_path
        self.mortgage_transactions: List[MortgageTransaction] = []
        self.monthly_mortgage_interest: Dict[str, Decimal] = {}

        if mortgage_data_path:
            self._load_mortgage_data()

    def _load_mortgage_data(self):
        """Load and process mortgage data"""
        try:
            loader = MortgageDataLoader(self.mortgage_data_path)
            self.mortgage_transactions = loader.load()
            self.monthly_mortgage_interest = loader.get_monthly_interest_payments()
            logger.info(f"Loaded {len(self.mortgage_transactions)} mortgage transactions")
            logger.info(f"Found mortgage interest data for {len(self.monthly_mortgage_interest)} months")
        except Exception as e:
            logger.error(f"Failed to load mortgage data: {e}")
            self.mortgage_transactions = []
            self.monthly_mortgage_interest = {}

    def calculate_enhanced_monthly_metrics(self) -> List[MonthlyMetrics]:
        """Calculate monthly metrics with mortgage interest included as expense"""

        # Get base metrics from parent class
        base_metrics = super().calculate_monthly_metrics()

        # Enhance with mortgage interest data
        enhanced_metrics = []
        for metrics in base_metrics:
            # Add mortgage interest to true expenses
            mortgage_interest = self.monthly_mortgage_interest.get(metrics.month, Decimal('0'))

            # Create enhanced metrics
            enhanced_true_expenses = metrics.true_expenses + mortgage_interest
            enhanced_net_cash_flow = metrics.gross_income - enhanced_true_expenses

            # Recalculate ratios
            enhanced_savings_rate = (enhanced_net_cash_flow / metrics.gross_income * 100) if metrics.gross_income > 0 else Decimal('0')
            enhanced_expense_ratio = (enhanced_true_expenses / metrics.gross_income * 100) if metrics.gross_income > 0 else Decimal('0')

            # Create new metrics object with mortgage interest included
            enhanced_metrics_obj = MonthlyMetrics(
                month=metrics.month,
                gross_income=metrics.gross_income,
                true_expenses=enhanced_true_expenses,  # Now includes mortgage interest
                net_cash_flow=enhanced_net_cash_flow,  # Adjusted for mortgage interest
                internal_transfers_out=metrics.internal_transfers_out,
                internal_transfers_in=metrics.internal_transfers_in,
                excluded_payments=metrics.excluded_payments,
                savings_rate=enhanced_savings_rate,
                expense_ratio=enhanced_expense_ratio,
                income_by_category=metrics.income_by_category,
                expense_by_category=self._add_mortgage_to_expenses(metrics.expense_by_category, mortgage_interest),
                transaction_count=metrics.transaction_count,
                largest_expense=max(metrics.largest_expense, mortgage_interest) if mortgage_interest > 0 else metrics.largest_expense,
                largest_income=metrics.largest_income,
                daily_burn_rate=enhanced_true_expenses / Decimal('30'),  # Approximate daily burn rate
                starting_balance=metrics.starting_balance,
                ending_balance=metrics.ending_balance,
                calculated_change=metrics.calculated_change,
                actual_change=metrics.actual_change,
                reconciliation_diff=metrics.reconciliation_diff
            )

            enhanced_metrics.append(enhanced_metrics_obj)

        return enhanced_metrics

    def _add_mortgage_to_expenses(self, expense_categories: Dict[str, Decimal], mortgage_interest: Decimal) -> Dict[str, Decimal]:
        """Add mortgage interest to expense categories"""
        if mortgage_interest <= 0:
            return expense_categories

        enhanced_categories = expense_categories.copy()
        enhanced_categories['Housing_Interest'] = enhanced_categories.get('Housing_Interest', Decimal('0')) + mortgage_interest
        return enhanced_categories

    def get_enhanced_summary_metrics(self) -> Dict:
        """Get summary metrics including mortgage interest"""
        enhanced_monthly = self.calculate_enhanced_monthly_metrics()

        if not enhanced_monthly:
            return {}

        # Calculate totals and averages
        total_months = len(enhanced_monthly)
        total_income = sum(m.gross_income for m in enhanced_monthly)
        total_expenses = sum(m.true_expenses for m in enhanced_monthly)
        total_net_flow = sum(m.net_cash_flow for m in enhanced_monthly)

        avg_monthly_income = total_income / total_months if total_months > 0 else Decimal('0')
        avg_monthly_expenses = total_expenses / total_months if total_months > 0 else Decimal('0')
        avg_monthly_net_flow = total_net_flow / total_months if total_months > 0 else Decimal('0')

        # Calculate savings rate and expense ratio
        overall_savings_rate = (total_net_flow / total_income * 100) if total_income > 0 else Decimal('0')
        overall_expense_ratio = (total_expenses / total_income * 100) if total_income > 0 else Decimal('0')

        # Mortgage-specific metrics
        total_mortgage_interest = sum(self.monthly_mortgage_interest.values())
        avg_monthly_mortgage_interest = total_mortgage_interest / total_months if total_months > 0 else Decimal('0')
        mortgage_percentage_of_expenses = (total_mortgage_interest / total_expenses * 100) if total_expenses > 0 else Decimal('0')

        return {
            'period': f"{enhanced_monthly[0].month} to {enhanced_monthly[-1].month}",
            'total_months': total_months,
            'avg_monthly_income': float(avg_monthly_income),
            'avg_monthly_expenses': float(avg_monthly_expenses),
            'avg_monthly_net_cash_flow': float(avg_monthly_net_flow),
            'avg_monthly_mortgage_interest': float(avg_monthly_mortgage_interest),
            'overall_savings_rate': float(overall_savings_rate),
            'overall_expense_ratio': float(overall_expense_ratio),
            'mortgage_percentage_of_expenses': float(mortgage_percentage_of_expenses),
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'total_mortgage_interest': float(total_mortgage_interest),
            'comparison_with_base': self._get_comparison_metrics()
        }

    def _get_comparison_metrics(self) -> Dict:
        """Compare enhanced metrics with base metrics (without mortgage interest)"""
        base_summary = super().get_summary_metrics()

        # Calculate enhanced metrics directly without calling get_enhanced_summary_metrics
        enhanced_monthly = self.calculate_enhanced_monthly_metrics()
        if not enhanced_monthly:
            return {}

        total_months = len(enhanced_monthly)
        total_income = sum(m.gross_income for m in enhanced_monthly)
        total_expenses = sum(m.true_expenses for m in enhanced_monthly)
        avg_monthly_expenses = total_expenses / total_months if total_months > 0 else Decimal('0')
        overall_savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else Decimal('0')

        if not base_summary:
            return {}

        return {
            'base_avg_monthly_expenses': base_summary.get('avg_monthly_expenses', 0),
            'enhanced_avg_monthly_expenses': float(avg_monthly_expenses),
            'expense_increase_dollars': float(avg_monthly_expenses) - base_summary.get('avg_monthly_expenses', 0),
            'expense_increase_percentage': ((float(avg_monthly_expenses) / base_summary.get('avg_monthly_expenses', 1)) - 1) * 100,
            'base_savings_rate': base_summary.get('overall_savings_rate', 0),
            'enhanced_savings_rate': float(overall_savings_rate),
            'savings_rate_change': float(overall_savings_rate) - base_summary.get('overall_savings_rate', 0)
        }

    def get_mortgage_analysis(self) -> Dict:
        """Get detailed mortgage analysis"""
        if not self.mortgage_transactions:
            return {'error': 'No mortgage data available'}

        monthly_payments = [t for t in self.mortgage_transactions if t.transaction_type == "MONTHLY PAYMENT"]
        principal_payments = [t for t in self.mortgage_transactions if t.transaction_type == "PRINCIPAL PAYMENT"]

        total_principal = sum(t.principal for t in self.mortgage_transactions)
        total_interest = sum(t.interest for t in self.mortgage_transactions)
        total_extra_principal = sum(t.principal for t in principal_payments)

        return {
            'total_transactions': len(self.mortgage_transactions),
            'monthly_payments': len(monthly_payments),
            'extra_principal_payments': len(principal_payments),
            'total_principal_paid': float(total_principal),
            'total_interest_paid': float(total_interest),
            'total_extra_principal': float(total_extra_principal),
            'avg_monthly_payment': float(sum(t.total_amount for t in monthly_payments) / len(monthly_payments)) if monthly_payments else 0,
            'avg_monthly_interest': float(sum(t.interest for t in monthly_payments) / len(monthly_payments)) if monthly_payments else 0,
            'principal_to_interest_ratio': float(total_principal / total_interest) if total_interest > 0 else 0,
            'date_range': (
                min(t.date for t in self.mortgage_transactions).strftime('%Y-%m-%d'),
                max(t.date for t in self.mortgage_transactions).strftime('%Y-%m-%d')
            ) if self.mortgage_transactions else None
        }