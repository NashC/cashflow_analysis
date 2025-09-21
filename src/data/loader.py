"""Bank CSV data loader with robust error handling for multiple institutions"""

import pandas as pd
import numpy as np
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Optional, List, Tuple
import logging
import re

from ..core.models import Transaction, ValidationResult
from ..core.exceptions import DataLoadError
from ..core.constants import DATE_FORMATS

logger = logging.getLogger(__name__)

class ChaseCSVLoader:
    """
    Loads and preprocesses bank CSV exports from multiple institutions.
    Handles various encoding issues and data formats.
    Currently optimized for Chase CSV format but extensible to other banks.
    """

    # Expected column mappings for different bank CSV formats
    COLUMN_MAPPINGS = {
        # Chase bank standard format
        'chase_standard': {
            'Posting Date': 'date',
            'Description': 'description',
            'Amount': 'amount',
            'Type': 'type',
            'Balance': 'balance'
        },
        # Generic bank formats with common column names
        'generic': {
            'Date': 'date',
            'Transaction Date': 'date',
            'Post Date': 'date',
            'Description': 'description',
            'Merchant': 'description',
            'Details': 'description',
            'Amount': 'amount',
            'Debit': 'amount_debit',
            'Credit': 'amount_credit',
            'Balance': 'balance',
            'Type': 'type',
            'Category': 'type'
        },
        # Wells Fargo common format
        'wells_fargo': {
            'Date': 'date',
            'Amount': 'amount',
            'Description': 'description'
        },
        # Bank of America format
        'boa': {
            'Posted Date': 'date',
            'Reference Number': 'reference',
            'Payee': 'description',
            'Address': 'address',
            'Amount': 'amount'
        }
    }

    def __init__(self, filepath: str):
        """Initialize with file path"""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise DataLoadError(f"File not found: {filepath}")

        self.raw_df: Optional[pd.DataFrame] = None
        self.transactions: List[Transaction] = []

    def load(self) -> List[Transaction]:
        """
        Load CSV file and convert to Transaction objects.

        Returns:
            List of Transaction objects
        """
        # Step 1: Read CSV with encoding detection
        self.raw_df = self._read_csv_with_encoding()

        # Step 2: Standardize column names
        self._standardize_columns()

        # Step 3: Parse and clean data
        self._parse_dates()
        self._clean_amounts()
        self._clean_descriptions()
        self._validate_required_fields()

        # Step 4: Convert to Transaction objects
        self._create_transactions()

        # Step 5: Sort by date (oldest first)
        self.transactions.sort(key=lambda t: t.date)

        logger.info(f"Loaded {len(self.transactions)} transactions from {self.filepath}")
        return self.transactions

    def _read_csv_with_encoding(self) -> pd.DataFrame:
        """Try multiple encodings to read CSV"""
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                # CRITICAL FIX: Explicitly set index_col=False to prevent pandas
                # from automatically using first column as index
                df = pd.read_csv(self.filepath, encoding=encoding, index_col=False)
                logger.info(f"Successfully read CSV with {encoding} encoding")
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Failed to read with {encoding}: {e}")

        raise DataLoadError(f"Could not read CSV file with any encoding: {encodings}")

    def _standardize_columns(self):
        """Standardize column names to expected format"""
        if self.raw_df is None:
            raise DataLoadError("No data loaded")

        columns = self.raw_df.columns.tolist()
        logger.debug(f"CSV columns found: {columns}")

        # Clean column names first
        self.raw_df.columns = [col.strip() for col in columns]
        columns = self.raw_df.columns.tolist()

        # Detect and handle different Chase CSV formats
        if self._is_chase_activity_format(columns):
            logger.info("Detected Chase Activity CSV format")
            self._handle_chase_activity_format()
        elif self._is_standard_format(columns):
            logger.info("Detected standard transaction CSV format")
            # Already in the right format, just proceed
        else:
            # Try to auto-detect column mapping
            logger.info("Attempting to auto-detect column mapping")
            self._auto_detect_columns()

        # Handle separate debit/credit columns if present
        if 'Debit' in self.raw_df.columns and 'Credit' in self.raw_df.columns:
            self._combine_debit_credit()

        # Final validation
        self._validate_column_mapping()

    def _is_chase_activity_format(self, columns: list) -> bool:
        """Check if this is a Chase Activity CSV format"""
        expected_chase_columns = ['Details', 'Posting Date', 'Description', 'Amount', 'Type', 'Balance']
        return all(col in columns for col in expected_chase_columns)

    def _is_standard_format(self, columns: list) -> bool:
        """Check if this is our standard format"""
        required_columns = ['Posting Date', 'Description', 'Amount']
        return all(col in columns for col in required_columns) and 'Details' not in columns

    def _handle_chase_activity_format(self):
        """Handle Chase Activity CSV format specifically"""
        # The Chase Activity format has columns:
        # Details, Posting Date, Description, Amount, Type, Balance, Check or Slip #

        # We can use the data as-is since the column names match our expectations
        # We just need to drop the extra columns we don't use
        columns_to_keep = ['Posting Date', 'Description', 'Amount', 'Type', 'Balance']

        # Check if all required columns exist
        missing_columns = [col for col in columns_to_keep if col not in self.raw_df.columns]
        if missing_columns:
            raise DataLoadError(f"Missing required columns in Chase Activity format: {missing_columns}")

        # Select only the columns we need and reorder them
        self.raw_df = self.raw_df[columns_to_keep]

        logger.info(f"Successfully mapped Chase Activity format, keeping columns: {columns_to_keep}")

    def _auto_detect_columns(self):
        """Attempt to auto-detect column mapping"""
        columns = self.raw_df.columns.tolist()

        # Try to find date column
        date_columns = ['Posting Date', 'Transaction Date', 'Post Date', 'Date']
        date_col = None
        for col in date_columns:
            if col in columns:
                date_col = col
                break

        if not date_col:
            raise DataLoadError(f"No date column found. Available columns: {columns}")

        # Rename date column if needed
        if date_col != 'Posting Date':
            self.raw_df = self.raw_df.rename(columns={date_col: 'Posting Date'})

    def _validate_column_mapping(self):
        """Validate that we have all required columns after mapping"""
        required_columns = ['Posting Date', 'Description', 'Amount']

        missing = [col for col in required_columns if col not in self.raw_df.columns]
        if missing:
            available = list(self.raw_df.columns)
            raise DataLoadError(f"Missing required columns after mapping: {missing}. Available: {available}")

    def _combine_debit_credit(self):
        """Combine separate debit/credit columns into single amount column"""
        if 'Debit' in self.raw_df.columns and 'Credit' in self.raw_df.columns:
            # Convert to numeric, replacing NaN with 0
            debit = pd.to_numeric(self.raw_df['Debit'], errors='coerce').fillna(0)
            credit = pd.to_numeric(self.raw_df['Credit'], errors='coerce').fillna(0)

            # Debits are negative, credits are positive
            self.raw_df['Amount'] = credit - debit

            # Drop original columns
            self.raw_df = self.raw_df.drop(columns=['Debit', 'Credit'])

    def _parse_dates(self):
        """Parse date column trying multiple formats"""
        date_col = 'Posting Date'

        if date_col not in self.raw_df.columns:
            raise DataLoadError(f"Date column '{date_col}' not found")

        parsed_dates = []
        for idx, date_str in enumerate(self.raw_df[date_col]):
            if pd.isna(date_str):
                parsed_dates.append(pd.NaT)
                continue

            date_str = str(date_str).strip()
            parsed_date = None

            # Try each date format
            for fmt in DATE_FORMATS:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

            if parsed_date is None:
                # Try pandas parser as fallback
                try:
                    parsed_date = pd.to_datetime(date_str)
                except:
                    logger.warning(f"Could not parse date at row {idx}: {date_str}")
                    parsed_date = pd.NaT

            parsed_dates.append(parsed_date)

        self.raw_df[date_col] = pd.Series(parsed_dates)

        # Drop rows with invalid dates
        invalid_dates = self.raw_df[date_col].isna().sum()
        if invalid_dates > 0:
            logger.warning(f"Dropping {invalid_dates} rows with invalid dates")
            self.raw_df = self.raw_df.dropna(subset=[date_col])

    def _clean_amounts(self):
        """Clean and parse amount column"""
        if 'Amount' not in self.raw_df.columns:
            raise DataLoadError("Amount column not found")

        def parse_amount(value) -> Optional[float]:
            """Parse various amount formats"""
            if pd.isna(value):
                return None

            # Convert to string and clean
            amount_str = str(value).strip()

            # Remove currency symbols and whitespace
            amount_str = re.sub(r'[$,\s]', '', amount_str)

            # Handle parentheses for negative numbers
            if amount_str.startswith('(') and amount_str.endswith(')'):
                amount_str = '-' + amount_str[1:-1]

            # Handle empty string
            if not amount_str:
                return None

            try:
                return float(amount_str)
            except ValueError:
                logger.warning(f"Could not parse amount: {value}")
                return None

        self.raw_df['Amount'] = self.raw_df['Amount'].apply(parse_amount)

        # Drop rows with invalid amounts
        invalid_amounts = self.raw_df['Amount'].isna().sum()
        if invalid_amounts > 0:
            logger.warning(f"Dropping {invalid_amounts} rows with invalid amounts")
            self.raw_df = self.raw_df.dropna(subset=['Amount'])

    def _clean_descriptions(self):
        """Clean transaction descriptions"""
        if 'Description' not in self.raw_df.columns:
            raise DataLoadError("Description column not found")

        def clean_description(desc) -> str:
            """Clean and standardize description"""
            if pd.isna(desc):
                return ""

            # Convert to string and clean
            desc = str(desc).strip()

            # Remove multiple spaces
            desc = re.sub(r'\s+', ' ', desc)

            # Remove special characters that might cause issues
            desc = desc.replace('\n', ' ').replace('\r', ' ')

            return desc.upper()  # Standardize to uppercase

        self.raw_df['Description'] = self.raw_df['Description'].apply(clean_description)

    def _validate_required_fields(self):
        """Validate that all required fields are present and valid"""
        required_columns = ['Posting Date', 'Description', 'Amount']

        for col in required_columns:
            if col not in self.raw_df.columns:
                raise DataLoadError(f"Required column missing: {col}")

            # Check for any remaining null values
            null_count = self.raw_df[col].isna().sum()
            if null_count > 0:
                raise DataLoadError(f"Column {col} has {null_count} null values")

        # Additional validation
        if len(self.raw_df) == 0:
            raise DataLoadError("CSV file contains no data rows")

        # Check that we have at least some valid amounts
        valid_amounts = self.raw_df['Amount'].notna().sum()
        if valid_amounts == 0:
            raise DataLoadError("No valid transaction amounts found")

        # Check date range reasonableness
        try:
            min_date = self.raw_df['Posting Date'].min()
            max_date = self.raw_df['Posting Date'].max()

            # Ensure dates are not in the future (with some tolerance)
            from datetime import datetime, timedelta
            future_threshold = datetime.now() + timedelta(days=30)

            if max_date > future_threshold:
                logger.warning(f"Found transactions with future dates (latest: {max_date})")

            # Ensure we have reasonable date span
            date_span = (max_date - min_date).days
            if date_span > 10 * 365:  # More than 10 years
                logger.warning(f"Large date span detected: {date_span} days")

        except Exception as e:
            logger.warning(f"Could not validate date range: {e}")

    def _create_transactions(self):
        """Convert DataFrame rows to Transaction objects"""
        self.transactions = []

        for idx, row in self.raw_df.iterrows():
            try:
                # Parse balance if available
                balance = Decimal('0')
                if 'Balance' in row and pd.notna(row['Balance']):
                    balance_str = str(row['Balance']).replace('$', '').replace(',', '')
                    if balance_str.strip():
                        balance = Decimal(balance_str)

                # Get transaction type if available
                trans_type = 'UNKNOWN'
                if 'Type' in row and pd.notna(row['Type']):
                    trans_type = str(row['Type']).upper()

                # Create Transaction object
                transaction = Transaction(
                    date=row['Posting Date'].to_pydatetime(),
                    description=row['Description'],
                    amount=Decimal(str(row['Amount'])),
                    balance=balance,
                    type=trans_type
                )

                self.transactions.append(transaction)

            except (InvalidOperation, ValueError) as e:
                logger.error(f"Error creating transaction at row {idx}: {e}")
                continue

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get the date range of loaded transactions"""
        if not self.transactions:
            raise DataLoadError("No transactions loaded")

        dates = [t.date for t in self.transactions]
        return min(dates), max(dates)

    def get_summary_stats(self) -> dict:
        """Get summary statistics of loaded data"""
        if not self.transactions:
            raise DataLoadError("No transactions loaded")

        amounts = [float(t.amount) for t in self.transactions]

        return {
            'total_transactions': len(self.transactions),
            'date_range': self.get_date_range(),
            'total_credits': sum(a for a in amounts if a > 0),
            'total_debits': sum(a for a in amounts if a < 0),
            'average_transaction': np.mean(amounts),
            'median_transaction': np.median(amounts),
            'largest_credit': max(amounts),
            'largest_debit': min(amounts)
        }