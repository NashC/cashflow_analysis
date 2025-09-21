#!/usr/bin/env python3
"""
Cash Flow Analyzer - Entry point script

Usage:
    python cashflow_analyzer.py path/to/chase_export.csv
    python cashflow_analyzer.py --generate-sample  # Generate test data
    python cashflow_analyzer.py --help              # Show help
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.main import main

if __name__ == '__main__':
    main()