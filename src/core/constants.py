"""Constants and enums for cash flow analysis"""

from enum import Enum
from typing import Dict, List

class FlowType(Enum):
    """
    Critical classification for accurate cash flow calculation.

    IMPORTANT:
    - INCOME: Money entering your financial system
    - EXPENSE: Money leaving your financial system (true expenses)
    - INTERNAL_TRANSFER: Money moving between your own accounts
    - EXCLUDED: Debt payments (credit cards, loans) - already counted when purchased

    Net Cash Flow = INCOME - EXPENSE (transfers and excluded NOT included)
    """
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    EXCLUDED = "EXCLUDED"

class TransactionType(Enum):
    """Chase transaction types from CSV"""
    ACH_DEBIT = "ACH_DEBIT"
    ACH_CREDIT = "ACH_CREDIT"
    DEBIT_CARD = "DEBIT_CARD"
    CHECK = "CHECK"
    DEPOSIT = "DEPOSIT"
    WIRE = "WIRE"
    FEE = "FEE"
    ADJUSTMENT = "ADJUSTMENT"
    TRANSFER = "TRANSFER"

# Category definitions with regex patterns
INCOME_CATEGORIES: Dict[str, List[str]] = {
    'Salary': [
        r'DIRECT DEP.*PAYROLL',
        r'ADP.*CREDIT',
        r'GUSTO',
        r'PAYROLL',
        r'SALARY',
        r'SEQUOIA ONE PEO.*EDI PYMNTS',
        r'EDI PYMNTS',
        r'PEO.*PAYROLL'
    ],
    'Government_Benefits': [
        r'APA.*TREAS.*310.*MISC PAY',
        r'WA ST EMPLOY SEC.*UI BENEFIT',
        r'UNEMPLOYMENT',
        r'UI BENEFIT',
        r'STATE.*BENEFIT'
    ],
    'Freelance': [
        r'ZELLE FROM',
        r'VENMO FROM',
        r'PAYPAL.*CREDIT',
        r'CASH APP.*FROM',
        r'FORTE LABS.*RECEIVABLE',
        r'RECEIVABLE'
    ],
    'Investment_Income': [
        r'DIVIDEND',
        r'INTEREST PAYMENT',
        r'CAPITAL GAIN',
        r'INVESTMENT.*INCOME',
        r'COINBASE.*INC',
        r'COINBASE\.COM',
        r'COINBASE',
        r'SOLIUM.*INC',
        r'STOCK.*OPTION',
        r'RSU.*VESTING'
    ],
    'Bank_Transfers': [
        r'GOLDMAN SACHS.*P2P',
        r'FEDWIRE CREDIT',
        r'BOOK TRANSFER CREDIT',
        r'P2P.*PAYMENT',
        r'SANTANDER BANK.*PAYMENT'
    ],
    'Deposits': [
        r'REMOTE.*ONLINE.*DEPOSIT',
        r'CHECK.*DEPOSIT',
        r'DEPOSIT.*\#',
        r'ATM CASH DEPOSIT',
        r'DEPOSIT ID NUMBER'
    ],
    'Venmo_Transfers': [
        r'VENMO.*CASHOUT',
        r'VENMO.*PAYMENT.*FROM'
    ],
    'Tax_Refund': [
        r'IRS.*TREAS',
        r'STATE.*REFUND',
        r'TAX REF',
        r'TREASURY.*REFUND'
    ],
    'Reimbursement': [
        r'EXPENSE REIMB',
        r'REFUND',
        r'REIMB',
        r'RETURN',
        r'FEE REVERSAL'
    ],
    'Gift': [
        r'GIFT',
        r'BIRTHDAY',
        r'WEDDING'
    ],
    'Other_Income': []  # Catch-all
}

EXPENSE_CATEGORIES: Dict[str, List[str]] = {
    'Housing': [
        r'RENT',
        r'MORTGAGE',
        r'HOA FEE',
        r'PROPERTY TAX',
        r'HOME.*INSURANCE'
    ],
    'Utilities': [
        r'ELECTRIC',
        r'GAS COMP',
        r'WATER',
        r'INTERNET',
        r'CABLE',
        r'TRASH',
        r'SEWER',
        r'UTILITY',
        r'FIRSTENERGY.*OPCO',
        r'PUGET SOUND ENER',
        r'COMCAST',
        r'VERIZON.*PAYMENTREC'
    ],
    'Banking_Fees': [
        r'NON-CHASE ATM FEE',
        r'ATM.*FEE',
        r'WIRE.*FEE',
        r'INCOMING.*WIRE.*FEE',
        r'DOMESTIC.*WIRE.*FEE',
        r'INTERNATIONAL.*WIRE.*FEE',
        r'OVERDRAFT.*FEE',
        r'MONTHLY.*SERVICE.*FEE'
    ],
    'Insurance': [
        r'INSURANCE',
        r'GEICO',
        r'STATE FARM',
        r'ALLSTATE',
        r'PROGRESSIVE',
        r'LIBERTY MUTUAL',
        r'LEMONADE'
    ],
    'Taxes': [
        r'IRS.*USATAXPYMT',
        r'TAX.*PAYMENT',
        r'ESTIMATED.*TAX',
        r'FEDERAL.*TAX',
        r'STATE.*TAX',
        r'TOWNSHIP.*TAX',
        r'TAX BILL',
        r'PROPERTY.*TAX',
        r'NC DEPT REVENUE',
        r'STATE.*REVENUE.*TAX'
    ],
    'Subscriptions': [
        r'NETFLIX',
        r'SPOTIFY',
        r'AMAZON.*PRIME',
        r'APPLE\.COM.*BILL',
        r'PAYPAL.*INST.*XFER.*APPLE\.COM',
        r'YOUTUBE',
        r'HULU',
        r'DISNEY\+',
        r'HBO',
        r'ADOBE',
        r'MICROSOFT',
        r'SG\*V\*',
        r'PAYPAL.*INST.*XFER.*ECONOMISTNE'
    ],
    'Business_Services': [
        r'SAMMPLAT.*BILL PAY',
        r'REPUBLICSERVICES.*RSIBILLPAY',
        r'BUSINESS.*SERVICE',
        r'PROFESSIONAL.*SERVICE',
        r'LINELEADER',
        r'ANGELLIST.*PAYMENT',
        r'SHOPIFY.*PAYMENTS'
    ],
    'Healthcare': [
        r'CVS',
        r'WALGREENS',
        r'RITE AID',
        r'PHARMACY',
        r'MEDICAL',
        r'DENTAL',
        r'DOCTOR',
        r'HOSPITAL',
        r'CLINIC',
        r'LABCORP',
        r'QUEST',
        r'PERIODONTICS'
    ],
    'Groceries': [
        r'SAFEWAY',
        r'WHOLE FOODS',
        r'TRADER JOE',
        r'KROGER',
        r'WALMART.*GROCERY',
        r'TARGET.*GROCERY',
        r'COSTCO',
        r'SAMS CLUB'
    ],
    'Dining': [
        r'RESTAURANT',
        r'UBER.*EATS',
        r'DOORDASH',
        r'GRUBHUB',
        r'POSTMATES',
        r'SEAMLESS',
        r'STARBUCKS',
        r'COFFEE',
        r'CAFE',
        r'PIZZA',
        r'MCDONALD',
        r'SUBWAY',
        r'CHIPOTLE'
    ],
    'Transportation': [
        r'UBER(?!.*EATS)',
        r'LYFT',
        r'SHELL',
        r'CHEVRON',
        r'EXXON',
        r'BP',
        r'PARKING',
        r'TOLL',
        r'PUBLIC TRANS',
        r'METRO',
        r'BUS'
    ],
    'Shopping': [
        r'AMAZON(?!.*PRIME)',
        r'TARGET(?!.*GROCERY)',
        r'WALMART(?!.*GROCERY)',
        r'BEST BUY',
        r'HOME DEPOT',
        r'LOWES',
        r'IKEA',
        r'MACYS',
        r'NORDSTROM'
    ],
    'Entertainment': [
        r'MOVIE',
        r'THEATER',
        r'CONCERT',
        r'TICKETMASTER',
        r'STUBHUB',
        r'STEAM',
        r'PLAYSTATION',
        r'XBOX',
        r'NINTENDO'
    ],
    'Personal_Care': [
        r'HAIRCUT',
        r'SALON',
        r'SPA',
        r'BARBER',
        r'NAILS',
        r'MASSAGE'
    ],
    'Fitness': [
        r'GYM',
        r'FITNESS',
        r'PLANET FITNESS',
        r'ANYTIME FITNESS',
        r'CROSSFIT',
        r'YOGA',
        r'PILATES'
    ],
    'Crypto_Purchases': [
        r'COINBASE.*RTL',
        r'COINBASE.*BUY',
        r'CRYPTO.*PURCHASE'
    ],
    'Education': [
        r'TUITION',
        r'COURSE',
        r'UDEMY',
        r'COURSERA',
        r'BOOKS',
        r'SCHOOL'
    ],
    'Government_Services': [
        r'WA STATE DOL',
        r'STATE.*DMV',
        r'DMV',
        r'DEPARTMENT OF LICENSING',
        r'GOVERNMENT.*FEE',
        r'STATE.*FEE'
    ],
    'Pets': [
        r'PETCO',
        r'PETSMART',
        r'VET',
        r'VETERINARY',
        r'PET.*FOOD'
    ],
    'Large_Withdrawals': [
        r'WITHDRAWAL.*\d{2}/\d{2}',
        r'CHECK.*\d{3,}',
        r'ATM WITHDRAWAL'
    ],
    'Other_Expense': []  # Catch-all
}

INTERNAL_TRANSFER_CATEGORIES: Dict[str, List[str]] = {
    'To_Savings': [
        r'TRANSFER TO.*SAV',
        r'ONLINE TRANSFER TO SAV',
        r'SAVINGS TRANSFER'
    ],
    'From_Savings': [
        r'TRANSFER FROM.*SAV',
        r'ONLINE TRANSFER FROM SAV'
    ],
    'To_Investment': [
        r'CHARLES SCHWAB',
        r'SCHWAB',
        r'FIDELITY',
        r'VANGUARD.*BUY',
        r'VANGUARD',
        r'INTERACTIVE.*BROK',
        r'E\*TRADE',
        r'ETRADE',
        r'ROBINHOOD',
        r'BETTERMENT',
        r'WEALTHFRONT'
    ],
    'To_External_Checking': [
        r'TRANSFER TO.*CHK',
        r'EXTERNAL TRANSFER',
        r'WIRE TRANSFER OUT'
    ],
    'From_External_Checking': [
        r'TRANSFER FROM.*CHK',
        r'WIRE TRANSFER IN',
        r'REMOTE.*ONLINE.*DEPOSIT'
    ],
    'Treasury_Direct': [
        r'TREASURYDIRECT',
        r'US TREASURY',
        r'TREASURY DIRECT'
    ],
    'Personal_Transfers': [
        r'ZELLE PAYMENT TO',
        r'ZELLE PAYMENT FROM',
        r'VENMO PAYMENT',
        r'VENMO.*CASHOUT',
        r'P2P.*PAYMENT'
    ]
}

EXCLUDED_CATEGORIES: Dict[str, List[str]] = {
    'Credit_Card_Payment': [
        r'CHASE CARD.*PAYMENT',
        r'CHASE CREDIT CRD',
        r'CHASE CREDIT CRD AUTOPAY',
        r'Payment to Chase card',
        r'AMEX.*PAYMENT',
        r'AMERICAN EXPRESS.*PAYMENT',
        r'DISCOVER.*PAYMENT',
        r'CAPITAL ONE.*PAYMENT',
        r'CAPITAL ONE.*PMT',
        r'CAPITAL ONE.*CRCARDPMT',
        r'CAPITAL ONE ONLINE PMT',
        r'CAPITAL ONE MOBILE PMT',
        r'CITI.*PAYMENT',
        r'BARCLAYS.*PAYMENT',
        r'CREDIT CARD PAYMENT'
    ],
    'Loan_Payment': [
        r'LOAN PAYMENT',
        r'AUTO LOAN',
        r'CAR LOAN',
        r'STUDENT LOAN',
        r'PERSONAL LOAN',
        r'NAVIENT',
        r'NELNET',
        r'SOFI.*LOAN'
    ],
    'Mortgage_Payment': [
        r'MORTGAGE PAYMENT',
        r'ONLINE PAYMENT.*TO MORTGAGE',
        r'PAYMENT.*TO MORTGAGE'
    ]
}

# Confidence thresholds
CONFIDENCE_HIGH = 0.9
CONFIDENCE_MEDIUM = 0.7
CONFIDENCE_LOW = 0.5

# Date formats to try when parsing
DATE_FORMATS = [
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d"
]

# Balance reconciliation tolerance (in dollars)
BALANCE_TOLERANCE = 0.01

# Transaction matching for transfers
TRANSFER_MATCH_DAYS = 3  # Look for matching transfer within 3 days
TRANSFER_AMOUNT_TOLERANCE = 0.01  # Amounts must match within 1 cent