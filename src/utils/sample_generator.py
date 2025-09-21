"""Sample data generator for testing and demonstration"""

import csv
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
import numpy as np

class SampleDataGenerator:
    """
    Generates realistic Chase CSV data for testing the cash flow analysis.
    Creates various transaction types to test all flow classifications.
    """

    def __init__(self, start_date: datetime = None, months: int = 6):
        """
        Initialize generator.

        Args:
            start_date: Start date for transactions (defaults to 6 months ago)
            months: Number of months of data to generate
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=months * 30)

        self.start_date = start_date
        self.end_date = start_date + timedelta(days=months * 30)
        self.current_balance = Decimal('2500.00')  # Starting balance

        # Transaction templates for realistic data
        self.income_templates = [
            {"description": "DIRECT DEP PAYROLL COMPANY", "amount_range": (4500, 5500), "frequency": 14},
            {"description": "FREELANCE PAYMENT ZELLE FROM", "amount_range": (800, 1500), "frequency": 30},
            {"description": "DIVIDEND SCHWAB", "amount_range": (50, 200), "frequency": 90},
            {"description": "TAX REFUND IRS TREAS", "amount_range": (1200, 2500), "frequency": 365},
        ]

        self.expense_templates = [
            # Housing
            {"description": "RENT PAYMENT CHECK", "amount_range": (-1800, -1800), "frequency": 30},
            {"description": "ELECTRIC COMPANY UTIL", "amount_range": (-80, -150), "frequency": 30},
            {"description": "INTERNET COMCAST", "amount_range": (-89, -89), "frequency": 30},

            # Food
            {"description": "WHOLE FOODS", "amount_range": (-50, -150), "frequency": 7},
            {"description": "STARBUCKS", "amount_range": (-5, -12), "frequency": 3},
            {"description": "CHIPOTLE", "amount_range": (-12, -18), "frequency": 10},
            {"description": "UBER EATS DELIVERY", "amount_range": (-25, -45), "frequency": 7},

            # Transportation
            {"description": "SHELL GAS STATION", "amount_range": (-35, -65), "frequency": 10},
            {"description": "UBER RIDE", "amount_range": (-12, -25), "frequency": 14},

            # Shopping
            {"description": "AMAZON MARKETPLACE", "amount_range": (-25, -200), "frequency": 8},
            {"description": "TARGET STORE", "amount_range": (-40, -120), "frequency": 20},

            # Subscriptions
            {"description": "NETFLIX", "amount_range": (-15.99, -15.99), "frequency": 30},
            {"description": "SPOTIFY", "amount_range": (-9.99, -9.99), "frequency": 30},
            {"description": "AMAZON PRIME", "amount_range": (-14.99, -14.99), "frequency": 30},

            # Healthcare
            {"description": "CVS PHARMACY", "amount_range": (-15, -80), "frequency": 45},

            # Fitness
            {"description": "PLANET FITNESS", "amount_range": (-10, -10), "frequency": 30},
        ]

        self.transfer_templates = [
            {"description": "TRANSFER TO SAVINGS", "amount_range": (-1000, -2000), "frequency": 30},
            {"description": "CHARLES SCHWAB INVESTMENT", "amount_range": (-500, -1500), "frequency": 30},
            {"description": "TREASURYDIRECT PURCHASE", "amount_range": (-1000, -1000), "frequency": 90},
        ]

        self.excluded_templates = [
            {"description": "CHASE CARD AUTOPAY", "amount_range": (-800, -2500), "frequency": 30},
            {"description": "AUTO LOAN PAYMENT", "amount_range": (-425, -425), "frequency": 30},
        ]

    def generate_csv(self, filepath: str, target_transactions: int = 200):
        """
        Generate a CSV file with sample transaction data.

        Args:
            filepath: Path to output CSV file
            target_transactions: Approximate number of transactions to generate
        """
        transactions = self._generate_transactions(target_transactions)

        # Write to CSV in Chase format
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Posting Date', 'Description', 'Amount', 'Type', 'Balance']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for trans in transactions:
                writer.writerow(trans)

        print(f"Generated {len(transactions)} transactions in {filepath}")

    def _generate_transactions(self, target_count: int) -> List[Dict[str, Any]]:
        """Generate list of transaction dictionaries"""
        transactions = []

        # Calculate how many transactions per template
        total_templates = (len(self.income_templates) + len(self.expense_templates) +
                          len(self.transfer_templates) + len(self.excluded_templates))

        # Generate transactions for each template
        for template in self.income_templates:
            count = self._calculate_transaction_count(template, target_count, total_templates)
            transactions.extend(self._generate_from_template(template, count, "ACH_CREDIT"))

        for template in self.expense_templates:
            count = self._calculate_transaction_count(template, target_count, total_templates)
            transactions.extend(self._generate_from_template(template, count, "DEBIT_CARD"))

        for template in self.transfer_templates:
            count = self._calculate_transaction_count(template, target_count, total_templates)
            transactions.extend(self._generate_from_template(template, count, "ACH_DEBIT"))

        for template in self.excluded_templates:
            count = self._calculate_transaction_count(template, target_count, total_templates)
            transactions.extend(self._generate_from_template(template, count, "ACH_DEBIT"))

        # Sort by date
        transactions.sort(key=lambda x: datetime.strptime(x['Posting Date'], '%m/%d/%Y'))

        # Update running balance
        self._update_balances(transactions)

        return transactions

    def _calculate_transaction_count(self, template: Dict, target_total: int, total_templates: int) -> int:
        """Calculate how many transactions to generate for this template"""
        days_span = (self.end_date - self.start_date).days
        frequency_days = template['frequency']

        # Calculate based on frequency
        frequency_count = days_span // frequency_days

        # Add some randomness
        variance = max(1, frequency_count // 4)
        return random.randint(
            max(1, frequency_count - variance),
            frequency_count + variance
        )

    def _generate_from_template(self, template: Dict, count: int, trans_type: str) -> List[Dict]:
        """Generate transactions from a template"""
        transactions = []
        base_description = template['description']
        amount_range = template['amount_range']
        frequency = template['frequency']

        for i in range(count):
            # Generate random date
            days_offset = random.randint(0, (self.end_date - self.start_date).days)
            trans_date = self.start_date + timedelta(days=days_offset)

            # Generate amount within range
            if amount_range[0] == amount_range[1]:
                amount = amount_range[0]
            else:
                amount = random.uniform(amount_range[0], amount_range[1])

            # Add some variation to description
            description = self._vary_description(base_description)

            transactions.append({
                'Posting Date': trans_date.strftime('%m/%d/%Y'),
                'Description': description,
                'Amount': f"{amount:.2f}",
                'Type': trans_type,
                'Balance': '0.00'  # Will be calculated later
            })

        return transactions

    def _vary_description(self, base_description: str) -> str:
        """Add variations to make descriptions more realistic"""
        variations = {
            'WHOLE FOODS': ['WHOLE FOODS MKT', 'WHOLEFDS', 'WHOLE FOODS MARKET'],
            'STARBUCKS': ['STARBUCKS STORE', 'STARBUCKS #1234', 'STARBUCKS COFFEE'],
            'AMAZON': ['AMZN MKTP', 'AMAZON.COM', 'AMAZON MARKETPLACE'],
            'SHELL': ['SHELL OIL', 'SHELL #1234', 'SHELL GAS'],
            'TARGET': ['TARGET STORE', 'TARGET #1234', 'TARGET T-1234'],
        }

        for key, variants in variations.items():
            if key in base_description:
                return random.choice(variants)

        # Add random numbers to some descriptions
        if any(word in base_description for word in ['STORE', 'STATION', 'MARKET']):
            return base_description + f" #{random.randint(1000, 9999)}"

        return base_description

    def _update_balances(self, transactions: List[Dict]):
        """Update running balance for all transactions"""
        running_balance = self.current_balance

        for trans in transactions:
            amount = Decimal(trans['Amount'])
            running_balance += amount
            trans['Balance'] = f"{running_balance:.2f}"

    def generate_test_scenarios(self) -> Dict[str, str]:
        """
        Generate multiple CSV files for different test scenarios.

        Returns:
            Dictionary mapping scenario names to file paths
        """
        scenarios = {}

        # Normal scenario
        scenarios['normal'] = 'data/input/sample_normal.csv'
        self.generate_csv(scenarios['normal'], 300)

        # High transfer scenario (lots of savings)
        original_transfers = self.transfer_templates.copy()
        for template in self.transfer_templates:
            template['frequency'] = 15  # More frequent transfers
            template['amount_range'] = (template['amount_range'][0] * 2, template['amount_range'][1] * 2)
        scenarios['high_savings'] = 'data/input/sample_high_savings.csv'
        self.generate_csv(scenarios['high_savings'], 250)
        self.transfer_templates = original_transfers  # Restore

        # Low income scenario
        original_income = self.income_templates.copy()
        for template in self.income_templates:
            template['amount_range'] = (template['amount_range'][0] * 0.6, template['amount_range'][1] * 0.6)
        scenarios['low_income'] = 'data/input/sample_low_income.csv'
        self.generate_csv(scenarios['low_income'], 200)
        self.income_templates = original_income  # Restore

        # High spending scenario
        original_expenses = self.expense_templates.copy()
        for template in self.expense_templates:
            if template['description'] not in ['RENT PAYMENT', 'NETFLIX', 'SPOTIFY']:  # Don't change fixed expenses
                template['amount_range'] = (template['amount_range'][0] * 1.5, template['amount_range'][1] * 1.5)
        scenarios['high_spending'] = 'data/input/sample_high_spending.csv'
        self.generate_csv(scenarios['high_spending'], 350)
        self.expense_templates = original_expenses  # Restore

        return scenarios