"""Mortgage data loader for principal/interest breakdown analysis"""

import pandas as pd
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MortgageTransaction:
    """Represents a mortgage transaction with principal/interest breakdown"""
    date: datetime
    transaction_type: str  # "PAYMENT", "PRINCIPAL PAYMENT", "NEW LOAN SET UP"
    total_amount: Decimal
    principal: Decimal
    interest: Decimal
    escrow: Decimal
    fees: Decimal
    balance: Decimal
    raw_details: str

    @property
    def year_month(self) -> str:
        """Get YYYY-MM format for grouping"""
        return self.date.strftime('%Y-%m')

class MortgageDataLoader:
    """Loads and processes mortgage transaction data with principal/interest breakdown"""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"Mortgage file not found: {filepath}")

        self.transactions: List[MortgageTransaction] = []

    def load(self) -> List[MortgageTransaction]:
        """Load mortgage CSV and extract principal/interest details"""
        logger.info(f"Loading mortgage data from {self.filepath}")

        # Read CSV with proper handling
        df = pd.read_csv(self.filepath)
        logger.debug(f"Found {len(df)} mortgage records")

        # Process each row
        for idx, row in df.iterrows():
            try:
                transaction = self._parse_transaction(row)
                if transaction:
                    self.transactions.append(transaction)
            except Exception as e:
                logger.warning(f"Failed to parse mortgage row {idx}: {e}")
                continue

        # Sort by date
        self.transactions.sort(key=lambda t: t.date)

        logger.info(f"Successfully loaded {len(self.transactions)} mortgage transactions")
        return self.transactions

    def _parse_transaction(self, row) -> Optional[MortgageTransaction]:
        """Parse a single mortgage transaction row"""

        # Parse date - handle multiple formats
        date_str = str(row['Date']).strip('"')
        date = self._parse_date(date_str)
        if not date:
            logger.warning(f"Could not parse date: {date_str}")
            return None

        # Parse total amount
        amount_str = str(row['Amount']).replace('$', '').replace(',', '').replace('"', '')
        try:
            total_amount = Decimal(amount_str)
        except:
            logger.warning(f"Could not parse amount: {row['Amount']}")
            return None

        # Parse balance
        balance_str = str(row['Balance']).replace('$', '').replace(',', '').replace('"', '')
        try:
            balance = Decimal(balance_str)
        except:
            balance = Decimal('0')

        # Parse details for principal/interest breakdown
        details = str(row['Details'])
        principal, interest, escrow, fees, transaction_type = self._parse_details(details)

        return MortgageTransaction(
            date=date,
            transaction_type=transaction_type,
            total_amount=total_amount,
            principal=principal,
            interest=interest,
            escrow=escrow,
            fees=fees,
            balance=balance,
            raw_details=details
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats"""
        date_formats = [
            "%b %d, %Y",     # "Sep 17, 2025"
            "%m/%d/%Y",      # "06/28/2025"
            "%Y-%m-%d",      # "2025-09-17"
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _parse_details(self, details: str) -> Tuple[Decimal, Decimal, Decimal, Decimal, str]:
        """Parse the details field to extract principal, interest, escrow, fees"""

        # Initialize defaults
        principal = Decimal('0')
        interest = Decimal('0')
        escrow = Decimal('0')
        fees = Decimal('0')
        transaction_type = "UNKNOWN"

        # Determine transaction type
        if "PRINCIPAL PAYMENT" in details:
            transaction_type = "PRINCIPAL PAYMENT"
        elif "PAYMENT" in details and "Principal" in details:
            transaction_type = "MONTHLY PAYMENT"
        elif "NEW LOAN" in details:
            transaction_type = "NEW LOAN SET UP"
        else:
            transaction_type = "OTHER"

        # Extract dollar amounts using regex
        patterns = {
            'principal': r'Principal\$?([\d,]+\.?\d*)',
            'interest': r'Interest\$?([\d,]+\.?\d*)',
            'escrow': r'Escrow\$?([\d,]+\.?\d*)',
            'fees': r'Fees\$?([\d,]+\.?\d*)'
        }

        for field, pattern in patterns.items():
            matches = re.findall(pattern, details)
            if matches:
                try:
                    value = Decimal(matches[0].replace(',', ''))
                    if field == 'principal':
                        principal = value
                    elif field == 'interest':
                        interest = value
                    elif field == 'escrow':
                        escrow = value
                    elif field == 'fees':
                        fees = value
                except:
                    logger.debug(f"Could not parse {field} from: {matches[0]}")

        return principal, interest, escrow, fees, transaction_type

    def get_monthly_interest_payments(self) -> Dict[str, Decimal]:
        """Extract monthly interest payments for expense tracking"""
        monthly_interest = {}

        for transaction in self.transactions:
            if transaction.transaction_type == "MONTHLY PAYMENT" and transaction.interest > 0:
                month = transaction.year_month
                if month not in monthly_interest:
                    monthly_interest[month] = Decimal('0')
                monthly_interest[month] += transaction.interest

        return monthly_interest

    def get_summary_stats(self) -> Dict:
        """Get summary statistics for mortgage data"""
        if not self.transactions:
            return {}

        total_principal = sum(t.principal for t in self.transactions)
        total_interest = sum(t.interest for t in self.transactions)
        total_payments = sum(t.total_amount for t in self.transactions if t.total_amount > 0)

        monthly_payments = [t for t in self.transactions if t.transaction_type == "MONTHLY PAYMENT"]
        principal_payments = [t for t in self.transactions if t.transaction_type == "PRINCIPAL PAYMENT"]

        return {
            'total_transactions': len(self.transactions),
            'date_range': (min(t.date for t in self.transactions), max(t.date for t in self.transactions)),
            'total_principal_paid': float(total_principal),
            'total_interest_paid': float(total_interest),
            'total_payments': float(total_payments),
            'monthly_payment_count': len(monthly_payments),
            'extra_principal_count': len(principal_payments),
            'avg_monthly_interest': float(sum(t.interest for t in monthly_payments) / len(monthly_payments)) if monthly_payments else 0,
            'starting_balance': float(self.transactions[0].balance) if self.transactions else 0,
            'ending_balance': float(self.transactions[-1].balance) if self.transactions else 0
        }