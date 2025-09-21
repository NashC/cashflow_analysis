"""Data models for cash flow analysis"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from .constants import FlowType

@dataclass
class Transaction:
    """
    Represents a single bank transaction with all metadata.
    Uses Decimal for financial precision.
    """
    # Raw data from CSV
    date: datetime
    description: str
    amount: Decimal
    balance: Decimal
    type: str  # Chase transaction type

    # Classified data
    flow_type: Optional[FlowType] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    confidence: float = 0.0

    # Metadata flags
    is_duplicate: bool = False
    is_recurring: bool = False
    is_anomaly: bool = False
    has_pair: bool = False  # For internal transfers
    pair_id: Optional[str] = None  # Link to matching transfer

    # User corrections
    user_verified: bool = False
    user_category: Optional[str] = None

    # Derived fields
    year_month: Optional[str] = field(init=False, default=None)
    day_of_week: Optional[str] = field(init=False, default=None)
    quarter: Optional[str] = field(init=False, default=None)

    def __post_init__(self):
        """Calculate derived fields after initialization"""
        if self.date:
            self.year_month = self.date.strftime("%Y-%m")
            self.day_of_week = self.date.strftime("%A")
            self.quarter = f"{self.date.year}-Q{(self.date.month-1)//3 + 1}"

    @property
    def is_income(self) -> bool:
        """Check if transaction is income"""
        return self.flow_type == FlowType.INCOME

    @property
    def is_expense(self) -> bool:
        """Check if transaction is a true expense"""
        return self.flow_type == FlowType.EXPENSE

    @property
    def is_transfer(self) -> bool:
        """Check if transaction is an internal transfer"""
        return self.flow_type == FlowType.INTERNAL_TRANSFER

    @property
    def is_excluded(self) -> bool:
        """Check if transaction should be excluded from cash flow"""
        return self.flow_type == FlowType.EXCLUDED

    @property
    def abs_amount(self) -> Decimal:
        """Get absolute value of amount"""
        return abs(self.amount)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame"""
        return {
            'date': self.date,
            'description': self.description,
            'amount': float(self.amount),
            'balance': float(self.balance),
            'type': self.type,
            'flow_type': self.flow_type.value if self.flow_type else None,
            'category': self.category,
            'subcategory': self.subcategory,
            'confidence': self.confidence,
            'is_duplicate': self.is_duplicate,
            'is_recurring': self.is_recurring,
            'is_anomaly': self.is_anomaly,
            'has_pair': self.has_pair,
            'pair_id': self.pair_id,
            'user_verified': self.user_verified,
            'user_category': self.user_category,
            'year_month': self.year_month,
            'day_of_week': self.day_of_week,
            'quarter': self.quarter
        }

@dataclass
class MonthlyMetrics:
    """Monthly cash flow metrics"""
    month: str

    # Core metrics (CRITICAL)
    gross_income: Decimal
    true_expenses: Decimal  # Excludes transfers and debt payments
    net_cash_flow: Decimal  # Income - True Expenses

    # Additional tracking
    internal_transfers_out: Decimal
    internal_transfers_in: Decimal
    excluded_payments: Decimal

    # Calculated ratios
    savings_rate: float  # (transfers_out / income) * 100
    expense_ratio: float  # (expenses / income) * 100

    # Category breakdowns
    income_by_category: Dict[str, Decimal]
    expense_by_category: Dict[str, Decimal]

    # Statistics
    transaction_count: int
    largest_expense: Decimal
    largest_income: Decimal
    daily_burn_rate: Decimal

    # Balance tracking
    starting_balance: Decimal
    ending_balance: Decimal
    calculated_change: Decimal
    actual_change: Decimal
    reconciliation_diff: Decimal

@dataclass
class ValidationResult:
    """Results from data validation"""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Specific issues
    missing_columns: list[str] = field(default_factory=list)
    date_gaps: list[tuple[datetime, datetime]] = field(default_factory=list)
    balance_discrepancies: list[tuple[int, Decimal, Decimal]] = field(default_factory=list)
    duplicate_transactions: list[int] = field(default_factory=list)

    # Statistics
    total_rows: int = 0
    valid_rows: int = 0
    error_rows: int = 0

@dataclass
class CategorizationResult:
    """Result of categorizing a transaction"""
    flow_type: FlowType
    category: str
    subcategory: Optional[str] = None
    confidence: float = 0.0
    method: str = "unknown"  # regex, fuzzy, ml, user_rule
    matched_pattern: Optional[str] = None

@dataclass
class RecurringTransaction:
    """Represents a detected recurring transaction"""
    description_pattern: str
    category: str

    # Timing
    frequency_days: int
    last_date: datetime
    next_expected_date: datetime

    # Amount
    average_amount: Decimal
    amount_variance: Decimal

    # History
    transaction_count: int
    transaction_ids: list[str]

    # Status
    is_active: bool
    missed_count: int  # Number of times expected but not found

@dataclass
class Anomaly:
    """Represents a detected anomaly"""
    transaction_id: str
    anomaly_type: str  # amount, timing, pattern, merchant
    severity: str  # low, medium, high

    # Details
    expected_value: Any
    actual_value: Any
    deviation: float

    # Context
    description: str
    recommendation: str