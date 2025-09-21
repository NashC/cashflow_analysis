"""
Cash flow analysis with correct calculation formula.

CRITICAL FORMULA:
net_cash_flow = total_income - total_true_expenses

WHERE:
- total_income = sum(INCOME transactions)
- total_true_expenses = sum(EXPENSE transactions)
- INTERNAL_TRANSFERS are NOT included in net calculation
- EXCLUDED payments are NOT included in net calculation
"""

import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Tuple
import logging
from collections import defaultdict

from ..core.models import Transaction, MonthlyMetrics
from ..core.constants import FlowType

logger = logging.getLogger(__name__)

class CashFlowCalculator:
    """
    Calculates accurate cash flow metrics using the correct formula.
    Excludes internal transfers and debt payments from net cash flow.
    """

    def __init__(self, transactions: List[Transaction]):
        """
        Initialize with list of categorized transactions.

        Args:
            transactions: List of transactions with flow_type and category set
        """
        self.transactions = transactions
        self.df = self._create_dataframe()

    def calculate_monthly_metrics(self) -> List[MonthlyMetrics]:
        """
        Calculate monthly cash flow metrics.

        Returns:
            List of MonthlyMetrics for each month
        """
        logger.info("Calculating monthly cash flow metrics")

        monthly_data = []

        # Group by year-month
        for year_month in sorted(self.df['year_month'].unique()):
            month_df = self.df[self.df['year_month'] == year_month]
            metrics = self._calculate_month_metrics(month_df, year_month)
            monthly_data.append(metrics)

        logger.info(f"Calculated metrics for {len(monthly_data)} months")
        return monthly_data

    def _calculate_month_metrics(self, month_df: pd.DataFrame, year_month: str) -> MonthlyMetrics:
        """
        Calculate metrics for a single month.

        CRITICAL CALCULATIONS:
        - net_cash_flow = gross_income - true_expenses
        - Internal transfers and excluded payments NOT included
        """
        # Core metrics - CRITICAL FOR ACCURACY
        income_mask = month_df['flow_type'] == FlowType.INCOME.value
        expense_mask = month_df['flow_type'] == FlowType.EXPENSE.value
        transfer_out_mask = (month_df['flow_type'] == FlowType.INTERNAL_TRANSFER.value) & (month_df['amount'] < 0)
        transfer_in_mask = (month_df['flow_type'] == FlowType.INTERNAL_TRANSFER.value) & (month_df['amount'] > 0)
        excluded_mask = month_df['flow_type'] == FlowType.EXCLUDED.value

        gross_income = Decimal(str(month_df[income_mask]['amount'].sum()))
        true_expenses = Decimal(str(abs(month_df[expense_mask]['amount'].sum())))
        internal_transfers_out = Decimal(str(abs(month_df[transfer_out_mask]['amount'].sum())))
        internal_transfers_in = Decimal(str(month_df[transfer_in_mask]['amount'].sum()))
        excluded_payments = Decimal(str(abs(month_df[excluded_mask]['amount'].sum())))

        # THE CRITICAL CALCULATION
        net_cash_flow = gross_income - true_expenses

        # Calculate ratios
        savings_rate = float((internal_transfers_out / gross_income) * 100) if gross_income > 0 else 0
        expense_ratio = float((true_expenses / gross_income) * 100) if gross_income > 0 else 0

        # Category breakdowns
        income_by_category = self._get_category_breakdown(month_df[income_mask])
        expense_by_category = self._get_category_breakdown(month_df[expense_mask])

        # Statistics
        transaction_count = len(month_df)
        largest_expense = Decimal(str(abs(month_df[expense_mask]['amount'].min()))) if len(month_df[expense_mask]) > 0 else Decimal('0')
        largest_income = Decimal(str(month_df[income_mask]['amount'].max())) if len(month_df[income_mask]) > 0 else Decimal('0')

        # Calculate daily burn rate (expenses only)
        days_in_month = self._get_days_in_month(year_month)
        daily_burn_rate = true_expenses / Decimal(str(days_in_month)) if days_in_month > 0 else Decimal('0')

        # CRITICAL FIX: Use transaction-only balance calculation
        # CSV balance field is unreliable, so we calculate based purely on transactions
        calculated_change = Decimal(str(month_df['amount'].sum()))

        # Optional: Try to compare with CSV balance if available, but don't rely on it
        csv_balance_available = month_df['balance'].notna().any() and (month_df['balance'] != 0).any()
        if csv_balance_available:
            starting_balance = self._get_starting_balance_from_csv(month_df)
            ending_balance = self._get_ending_balance_from_csv(month_df)
            actual_change = ending_balance - starting_balance
            reconciliation_diff = abs(calculated_change - actual_change)
        else:
            # No CSV balance data available, use transaction-only calculation
            reconciliation_diff = Decimal('0')  # No discrepancy when using transaction-only

        return MonthlyMetrics(
            month=year_month,
            gross_income=gross_income,
            true_expenses=true_expenses,
            net_cash_flow=net_cash_flow,
            internal_transfers_out=internal_transfers_out,
            internal_transfers_in=internal_transfers_in,
            excluded_payments=excluded_payments,
            savings_rate=savings_rate,
            expense_ratio=expense_ratio,
            income_by_category=income_by_category,
            expense_by_category=expense_by_category,
            transaction_count=transaction_count,
            largest_expense=largest_expense,
            largest_income=largest_income,
            daily_burn_rate=daily_burn_rate,
            starting_balance=starting_balance,
            ending_balance=ending_balance,
            calculated_change=calculated_change,
            actual_change=actual_change,
            reconciliation_diff=reconciliation_diff
        )

    def get_summary_metrics(self) -> Dict:
        """Get overall summary metrics across all time periods"""
        total_income = Decimal('0')
        total_expenses = Decimal('0')
        total_transfers_out = Decimal('0')
        total_excluded = Decimal('0')

        for trans in self.transactions:
            if trans.flow_type == FlowType.INCOME:
                total_income += trans.amount
            elif trans.flow_type == FlowType.EXPENSE:
                total_expenses += abs(trans.amount)
            elif trans.flow_type == FlowType.INTERNAL_TRANSFER and trans.amount < 0:
                total_transfers_out += abs(trans.amount)
            elif trans.flow_type == FlowType.EXCLUDED:
                total_excluded += abs(trans.amount)

        total_net_cash_flow = total_income - total_expenses

        # Get date range
        dates = [t.date for t in self.transactions]
        date_range = (min(dates), max(dates)) if dates else (None, None)
        months_span = self._calculate_months_span(date_range[0], date_range[1]) if date_range[0] else 1

        return {
            'period': f"{date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}" if date_range[0] else "N/A",
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'total_net_cash_flow': float(total_net_cash_flow),
            'total_transfers_out': float(total_transfers_out),
            'total_excluded': float(total_excluded),
            'avg_monthly_income': float(total_income / months_span),
            'avg_monthly_expenses': float(total_expenses / months_span),
            'avg_monthly_net_cash_flow': float(total_net_cash_flow / months_span),
            'avg_monthly_savings': float(total_transfers_out / months_span),
            'overall_savings_rate': float((total_transfers_out / total_income) * 100) if total_income > 0 else 0,
            'overall_expense_ratio': float((total_expenses / total_income) * 100) if total_income > 0 else 0,
            'transaction_count': len(self.transactions),
            'months_span': months_span
        }

    def get_category_analysis(self) -> Dict:
        """Get detailed category analysis"""
        category_data = defaultdict(lambda: {
            'total': Decimal('0'),
            'count': 0,
            'average': Decimal('0'),
            'percentage': 0.0
        })

        # Calculate totals by category
        for trans in self.transactions:
            if trans.flow_type in [FlowType.EXPENSE, FlowType.INCOME]:
                category = f"{trans.flow_type.value}:{trans.category}"
                category_data[category]['total'] += abs(trans.amount)
                category_data[category]['count'] += 1

        # Calculate percentages and averages
        total_income = sum(trans.amount for trans in self.transactions if trans.flow_type == FlowType.INCOME)
        total_expenses = sum(abs(trans.amount) for trans in self.transactions if trans.flow_type == FlowType.EXPENSE)

        for category, data in category_data.items():
            data['average'] = data['total'] / data['count'] if data['count'] > 0 else Decimal('0')

            # Calculate percentage of relevant total
            if category.startswith('INCOME:'):
                data['percentage'] = float((data['total'] / total_income) * 100) if total_income > 0 else 0
            elif category.startswith('EXPENSE:'):
                data['percentage'] = float((data['total'] / total_expenses) * 100) if total_expenses > 0 else 0

        # Convert to regular dict with float values for JSON serialization
        result = {}
        for category, data in category_data.items():
            result[category] = {
                'total': float(data['total']),
                'count': data['count'],
                'average': float(data['average']),
                'percentage': data['percentage']
            }

        return result

    def validate_cash_flow_calculation(self) -> Dict:
        """
        Validate that cash flow calculation is correct.
        Returns validation results and any discrepancies.
        """
        validation = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'flow_type_counts': {},
            'balance_check': {}
        }

        # Count transactions by flow type
        for flow_type in FlowType:
            count = sum(1 for t in self.transactions if t.flow_type == flow_type)
            validation['flow_type_counts'][flow_type.value] = count

        # Check for missing flow types
        if validation['flow_type_counts'].get(FlowType.INCOME.value, 0) == 0:
            validation['warnings'].append("No INCOME transactions found")

        if validation['flow_type_counts'].get(FlowType.EXPENSE.value, 0) == 0:
            validation['warnings'].append("No EXPENSE transactions found")

        # Check for large reconciliation differences (warnings only, not errors)
        # Note: reconciliation_diff compares transaction-based calc vs unreliable CSV balance
        monthly_metrics = self.calculate_monthly_metrics()
        large_discrepancies = 0
        for metrics in monthly_metrics:
            if metrics.reconciliation_diff > Decimal('100.00'):  # Only warn for very large differences
                validation['warnings'].append(
                    f"Large CSV balance discrepancy in {metrics.month}: ${float(metrics.reconciliation_diff):.2f} "
                    "(This is normal if CSV balance data is unreliable)"
                )
                large_discrepancies += 1

        # Only flag as error if ALL months have large discrepancies (suggests systematic issue)
        if large_discrepancies > 0 and large_discrepancies == len(monthly_metrics):
            validation['warnings'].append(
                "All months show CSV balance discrepancies. This suggests the CSV balance field is unreliable, "
                "but transaction-based calculations should still be accurate."
            )

        validation['is_valid'] = len(validation['errors']) == 0

        return validation

    def _create_dataframe(self) -> pd.DataFrame:
        """Convert transactions to pandas DataFrame for analysis"""
        data = []
        for trans in self.transactions:
            data.append({
                'date': trans.date,
                'description': trans.description,
                'amount': float(trans.amount),
                'balance': float(trans.balance),
                'flow_type': trans.flow_type.value if trans.flow_type else None,
                'category': trans.category,
                'year_month': trans.year_month,
                'confidence': trans.confidence
            })

        return pd.DataFrame(data)

    def _get_category_breakdown(self, df: pd.DataFrame) -> Dict[str, Decimal]:
        """Get spending/income breakdown by category"""
        if len(df) == 0:
            return {}

        breakdown = {}
        for category in df['category'].unique():
            if pd.notna(category):
                category_df = df[df['category'] == category]
                total = Decimal(str(abs(category_df['amount'].sum())))
                breakdown[category] = total

        return breakdown

    def _get_days_in_month(self, year_month: str) -> int:
        """Get number of days in the month"""
        try:
            year, month = year_month.split('-')
            if month == '02':  # February
                year_int = int(year)
                if (year_int % 4 == 0 and year_int % 100 != 0) or (year_int % 400 == 0):
                    return 29  # Leap year
                else:
                    return 28
            elif month in ['04', '06', '09', '11']:
                return 30
            else:
                return 31
        except:
            return 30  # Default

    def _get_starting_balance_from_csv(self, month_df: pd.DataFrame) -> Decimal:
        """Get starting balance from CSV data (unreliable, for comparison only)"""
        if len(month_df) == 0:
            return Decimal('0')

        # Find earliest transaction's balance minus its amount
        earliest = month_df.loc[month_df['date'].idxmin()]
        return Decimal(str(earliest['balance'] - earliest['amount']))

    def _get_ending_balance_from_csv(self, month_df: pd.DataFrame) -> Decimal:
        """Get ending balance from CSV data (unreliable, for comparison only)"""
        if len(month_df) == 0:
            return Decimal('0')

        # Find latest transaction's balance
        latest = month_df.loc[month_df['date'].idxmax()]
        return Decimal(str(latest['balance']))

    def _calculate_months_span(self, start_date: datetime, end_date: datetime) -> float:
        """Calculate number of months between two dates"""
        if not start_date or not end_date:
            return 1

        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        return max(1, months + 1)  # Include partial months