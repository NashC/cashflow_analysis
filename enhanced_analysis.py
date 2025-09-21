#!/usr/bin/env python3
"""Enhanced cash flow analysis with mortgage interest integration"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.data.loader import ChaseCSVLoader as BankCSVLoader
from src.categorization.flow_classifier import FlowTypeClassifier
from src.categorization.categorizer import TransactionCategorizer
from src.analysis.enhanced_cashflow import EnhancedCashFlowCalculator

print("🏦 ENHANCED CASH FLOW ANALYSIS WITH MORTGAGE INTEREST")
print("="*70)

# Load and process bank transactions
print("\n1. Loading bank transaction data...")
loader = BankCSVLoader('data/sample_bank_data.csv')
transactions = loader.load()

classifier = FlowTypeClassifier(transactions)
transactions = classifier.classify_all(transactions)

categorizer = TransactionCategorizer()
transactions = categorizer.categorize_all(transactions)

print(f"   ✓ Loaded {len(transactions)} bank transactions")

# Create enhanced calculator with mortgage data
print("\n2. Integrating mortgage interest data...")
enhanced_calc = EnhancedCashFlowCalculator(
    transactions=transactions,
    mortgage_data_path='data/mortgage_transactions.csv'
)

print(f"   ✓ Loaded mortgage data with {len(enhanced_calc.mortgage_transactions)} transactions")
print(f"   ✓ Found interest data for {len(enhanced_calc.monthly_mortgage_interest)} months")

# Get enhanced metrics
enhanced_summary = enhanced_calc.get_enhanced_summary_metrics()
mortgage_analysis = enhanced_calc.get_mortgage_analysis()
comparison = enhanced_summary.get('comparison_with_base', {})

print("\n" + "="*70)
print("📊 ENHANCED CASH FLOW SUMMARY")
print("="*70)

print(f"\n💰 KEY METRICS (With Mortgage Interest):")
print(f"  Average Monthly Income:     ${enhanced_summary['avg_monthly_income']:>12,.2f}")
print(f"  Average Monthly Expenses:   ${enhanced_summary['avg_monthly_expenses']:>12,.2f}")
print(f"    ↳ Mortgage Interest:      ${enhanced_summary['avg_monthly_mortgage_interest']:>12,.2f} ({enhanced_summary['mortgage_percentage_of_expenses']:.1f}% of expenses)")
print(f"  Average Monthly Net Flow:   ${enhanced_summary['avg_monthly_net_cash_flow']:>12,.2f}")
print(f"  Enhanced Savings Rate:      {enhanced_summary['overall_savings_rate']:>12.1f}%")
print(f"  Enhanced Expense Ratio:     {enhanced_summary['overall_expense_ratio']:>12.1f}%")

if comparison:
    print(f"\n📈 IMPACT OF INCLUDING MORTGAGE INTEREST:")
    print(f"  Base Monthly Expenses:      ${comparison['base_avg_monthly_expenses']:>12,.2f}")
    print(f"  Enhanced Monthly Expenses:  ${comparison['enhanced_avg_monthly_expenses']:>12,.2f}")
    print(f"  Expense Increase:           ${comparison['expense_increase_dollars']:>12,.2f} (+{comparison['expense_increase_percentage']:.1f}%)")
    print(f"  Savings Rate Change:        {comparison['savings_rate_change']:>12.1f} percentage points")

print(f"\n🏠 MORTGAGE ANALYSIS:")
print(f"  Total Interest Paid:        ${mortgage_analysis['total_interest_paid']:>12,.2f}")
print(f"  Total Principal Paid:       ${mortgage_analysis['total_principal_paid']:>12,.2f}")
print(f"  Extra Principal Payments:   ${mortgage_analysis['total_extra_principal']:>12,.2f}")
print(f"  Average Monthly Payment:    ${mortgage_analysis['avg_monthly_payment']:>12,.2f}")
print(f"  Average Monthly Interest:   ${mortgage_analysis['avg_monthly_interest']:>12,.2f}")
print(f"  Principal/Interest Ratio:   {mortgage_analysis['principal_to_interest_ratio']:>12.2f}:1")

# Show recent monthly breakdown
print(f"\n📅 RECENT MONTHLY BREAKDOWN:")
enhanced_monthly = enhanced_calc.calculate_enhanced_monthly_metrics()
for metrics in enhanced_monthly[-6:]:  # Last 6 months
    mortgage_interest = enhanced_calc.monthly_mortgage_interest.get(metrics.month, 0)
    print(f"  {metrics.month}: Income ${float(metrics.gross_income):>8,.0f} | "
          f"Expenses ${float(metrics.true_expenses):>8,.0f} | "
          f"Mortgage Int. ${float(mortgage_interest):>7,.0f} | "
          f"Net ${float(metrics.net_cash_flow):>8,.0f} | "
          f"Rate {float(metrics.savings_rate):>5.1f}%")

print(f"\n🎯 KEY INSIGHTS:")
print(f"• Mortgage interest of ~${enhanced_summary['avg_monthly_mortgage_interest']:,.0f}/month is a TRUE operating expense")
print(f"• Including mortgage interest gives more realistic expense ratio: {enhanced_summary['overall_expense_ratio']:.1f}%")
print(f"• Savings rate is still strong at {enhanced_summary['overall_savings_rate']:.1f}%, showing excellent financial health")
print(f"• Extra principal payments (${mortgage_analysis['total_extra_principal']:,.0f}) are wealth-building, not expenses")

print(f"\n✅ ANALYSIS COMPLETE: Professional-grade cash flow analysis with mortgage detail!")