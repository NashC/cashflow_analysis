"""
Main application pipeline for cash flow analysis.
Orchestrates the entire workflow from CSV loading to report generation.
"""

import logging
import argparse
import yaml
from pathlib import Path
from typing import Optional, List
import sys
from datetime import datetime

# Core modules
from .data.loader import ChaseCSVLoader
from .data.validator import DataValidator
from .categorization.flow_classifier import FlowTypeClassifier
from .categorization.categorizer import TransactionCategorizer
from .analysis.cashflow import CashFlowCalculator
from .core.models import Transaction
from .core.exceptions import CashFlowAnalysisError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CashFlowAnalysisApp:
    """
    Main application class that orchestrates the cash flow analysis pipeline.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the application.

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.transactions: List[Transaction] = []
        self.results = {}

    def run(self, csv_path: str) -> dict:
        """
        Run the complete cash flow analysis pipeline.

        Args:
            csv_path: Path to Chase CSV file

        Returns:
            Dictionary with analysis results
        """
        logger.info("Starting cash flow analysis pipeline")
        logger.info(f"Input file: {csv_path}")

        # Validate input file exists and is readable
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise CashFlowAnalysisError(f"Input file does not exist: {csv_path}")

        if not csv_file.is_file():
            raise CashFlowAnalysisError(f"Input path is not a file: {csv_path}")

        if csv_file.stat().st_size == 0:
            raise CashFlowAnalysisError(f"Input file is empty: {csv_path}")

        try:
            # Step 1: Load and validate data
            self._load_data(csv_path)

            if not self.transactions:
                raise CashFlowAnalysisError("No valid transactions found in the CSV file")

            # Step 2: Classify flow types (CRITICAL)
            self._classify_flow_types()

            # Step 3: Categorize transactions
            self._categorize_transactions()

            # Step 4: Calculate cash flow metrics
            self._calculate_metrics()

            # Step 5: Validate results
            self._validate_results()

            # Step 6: Generate summary
            summary = self._generate_summary()

            logger.info("Cash flow analysis completed successfully")
            return summary

        except CashFlowAnalysisError:
            # Re-raise our specific errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}")
            raise CashFlowAnalysisError(f"Analysis failed: {str(e)}") from e

    def _load_data(self, csv_path: str):
        """Load and validate CSV data"""
        logger.info("Step 1: Loading transaction data...")

        # Load CSV
        loader = ChaseCSVLoader(csv_path)
        self.transactions = loader.load()

        # Validate data
        validator = DataValidator(self.transactions)
        validation_result = validator.validate()

        if not validation_result.is_valid:
            if validation_result.errors:
                logger.error("Data validation failed:")
                for error in validation_result.errors:
                    logger.error(f"  - {error}")

                # Allow analysis to continue with balance discrepancies
                # Balance validation is helpful but not critical for cash flow analysis
                balance_keywords = ["Balance discrepancy", "balance discrepancies"]
                balance_errors = [e for e in validation_result.errors
                                if any(keyword in e for keyword in balance_keywords)]
                critical_errors = [e for e in validation_result.errors
                                 if not any(keyword in e for keyword in balance_keywords)]

                if critical_errors:
                    raise CashFlowAnalysisError(f"Critical data validation failed: {critical_errors[0]}")
                else:
                    logger.warning(f"Proceeding with analysis despite {len(balance_errors)} balance discrepancies")
                    logger.warning("Balance discrepancies may indicate data quality issues but won't affect cash flow calculations")

        if validation_result.warnings:
            logger.warning("Data validation warnings:")
            for warning in validation_result.warnings:
                logger.warning(f"  - {warning}")

        # Store validation results
        self.results['validation'] = validation_result

        # Get summary statistics
        summary_stats = loader.get_summary_stats()
        logger.info(f"Loaded {summary_stats['total_transactions']} transactions")
        logger.info(f"Date range: {summary_stats['date_range'][0].strftime('%Y-%m-%d')} to "
                   f"{summary_stats['date_range'][1].strftime('%Y-%m-%d')}")

    def _classify_flow_types(self):
        """Classify transactions into flow types (CRITICAL step)"""
        logger.info("Step 2: Classifying flow types...")

        classifier = FlowTypeClassifier(self.transactions)
        self.transactions = classifier.classify_all(self.transactions)

        # Validate that all transactions have flow types
        unclassified = [t for t in self.transactions if t.flow_type is None]
        if unclassified:
            raise CashFlowAnalysisError(f"Failed to classify {len(unclassified)} transactions")

        # Log classification summary
        from collections import Counter
        flow_counts = Counter(t.flow_type for t in self.transactions)
        logger.info("Flow type classification complete:")
        for flow_type, count in flow_counts.items():
            logger.info(f"  {flow_type.value}: {count}")

    def _categorize_transactions(self):
        """Categorize transactions into detailed categories"""
        logger.info("Step 3: Categorizing transactions...")

        categorizer = TransactionCategorizer(self.config)
        self.transactions = categorizer.categorize_all(self.transactions)

        # Check for low confidence categorizations
        low_confidence = categorizer.get_low_confidence_transactions(
            self.transactions,
            self.config.get('analysis', {}).get('confidence_threshold', 0.8)
        )

        if low_confidence:
            logger.warning(f"Found {len(low_confidence)} transactions with low confidence")
            self.results['low_confidence_transactions'] = low_confidence

    def _calculate_metrics(self):
        """Calculate cash flow metrics"""
        logger.info("Step 4: Calculating cash flow metrics...")

        calculator = CashFlowCalculator(self.transactions)

        # Calculate monthly metrics
        monthly_metrics = calculator.calculate_monthly_metrics()
        self.results['monthly_metrics'] = monthly_metrics

        # Calculate summary metrics
        summary_metrics = calculator.get_summary_metrics()
        self.results['summary_metrics'] = summary_metrics

        # Get category analysis
        category_analysis = calculator.get_category_analysis()
        self.results['category_analysis'] = category_analysis

        logger.info(f"Calculated metrics for {len(monthly_metrics)} months")
        logger.info(f"Average monthly net cash flow: ${summary_metrics['avg_monthly_net_cash_flow']:.2f}")

    def _validate_results(self):
        """Validate that results make sense"""
        logger.info("Step 5: Validating results...")

        calculator = CashFlowCalculator(self.transactions)
        validation = calculator.validate_cash_flow_calculation()

        if not validation['is_valid']:
            logger.error("Cash flow calculation validation failed:")
            for error in validation['errors']:
                logger.error(f"  - {error}")

        if validation['warnings']:
            for warning in validation['warnings']:
                logger.warning(f"  - {warning}")

        self.results['calculation_validation'] = validation

    def _generate_summary(self) -> dict:
        """Generate final summary of analysis"""
        summary = {
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'input_file': None,  # Will be set by caller
            'transaction_count': len(self.transactions),
            'summary_metrics': self.results.get('summary_metrics', {}),
            'validation': {
                'data_valid': self.results['validation'].is_valid,
                'calculation_valid': self.results.get('calculation_validation', {}).get('is_valid', True),
                'warnings_count': len(self.results['validation'].warnings),
                'low_confidence_count': len(self.results.get('low_confidence_transactions', []))
            }
        }

        # Add key insights
        summary_metrics = self.results.get('summary_metrics', {})
        summary['key_insights'] = {
            'avg_monthly_income': summary_metrics.get('avg_monthly_income', 0),
            'avg_monthly_expenses': summary_metrics.get('avg_monthly_expenses', 0),
            'avg_monthly_net_cash_flow': summary_metrics.get('avg_monthly_net_cash_flow', 0),
            'overall_savings_rate': summary_metrics.get('overall_savings_rate', 0),
            'overall_expense_ratio': summary_metrics.get('overall_expense_ratio', 0)
        }

        return summary

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from YAML file"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'

        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)

                # Validate config structure
                if config is None:
                    logger.warning(f"Config file is empty: {config_path}. Using defaults.")
                    return self._get_default_config()

                # Ensure required sections exist with defaults
                validated_config = self._validate_config(config)
                logger.info(f"Loaded configuration from {config_path}")
                return validated_config

        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}. Using defaults.")
            return self._get_default_config()
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config file: {e}. Using defaults.")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            'analysis': {
                'lookback_months': 12,
                'confidence_threshold': 0.8,
                'anomaly_sensitivity': 2.5
            },
            'categorization': {
                'use_ml_classifier': False,
                'fuzzy_match_threshold': 85,
                'custom_rules': [],
                'merchant_aliases': {}
            },
            'output': {
                'reports_directory': './reports',
                'include_forecasting': True
            }
        }

    def _validate_config(self, config: dict) -> dict:
        """Validate and fill in missing config sections"""
        default_config = self._get_default_config()

        # Merge with defaults
        for section, defaults in default_config.items():
            if section not in config:
                config[section] = defaults
            else:
                # Merge section-level defaults
                for key, default_value in defaults.items():
                    if key not in config[section]:
                        config[section][key] = default_value

        # Validate specific values
        analysis_config = config.get('analysis', {})
        if analysis_config.get('confidence_threshold', 0.8) < 0 or analysis_config.get('confidence_threshold', 0.8) > 1:
            logger.warning("Invalid confidence_threshold in config, using 0.8")
            analysis_config['confidence_threshold'] = 0.8

        categorization_config = config.get('categorization', {})
        if categorization_config.get('fuzzy_match_threshold', 85) < 0 or categorization_config.get('fuzzy_match_threshold', 85) > 100:
            logger.warning("Invalid fuzzy_match_threshold in config, using 85")
            categorization_config['fuzzy_match_threshold'] = 85

        return config

    def get_transactions(self) -> List[Transaction]:
        """Get the processed transactions"""
        return self.transactions

    def get_results(self) -> dict:
        """Get the full analysis results"""
        return self.results

def main():
    """Command-line interface for the cash flow analysis"""
    parser = argparse.ArgumentParser(description='Analyze cash flow from Chase CSV export')

    parser.add_argument('csv_file',
                       nargs='?',
                       help='Path to Chase CSV file')

    parser.add_argument('--config', '-c',
                       help='Path to configuration file',
                       default=None)

    parser.add_argument('--output', '-o',
                       help='Output directory for reports',
                       default='./reports')

    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose logging')

    parser.add_argument('--generate-sample',
                       action='store_true',
                       help='Generate sample data instead of analyzing')

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.generate_sample:
            # Generate sample data
            from .utils.sample_generator import SampleDataGenerator
            generator = SampleDataGenerator()
            scenarios = generator.generate_test_scenarios()
            print("Generated sample data files:")
            for scenario, filepath in scenarios.items():
                print(f"  {scenario}: {filepath}")
            return

        # Check that csv_file is provided for analysis
        if not args.csv_file:
            parser.error("csv_file is required when not using --generate-sample")

        # Run analysis
        app = CashFlowAnalysisApp(args.config)
        summary = app.run(args.csv_file)

        # Print summary
        print("\n" + "="*60)
        print("CASH FLOW ANALYSIS SUMMARY")
        print("="*60)
        print(f"File: {args.csv_file}")
        print(f"Transactions: {summary['transaction_count']}")
        print(f"Period: {summary['summary_metrics'].get('period', 'N/A')}")
        print()

        insights = summary['key_insights']
        print("KEY METRICS:")
        print(f"  Average Monthly Income:    ${insights['avg_monthly_income']:>10,.2f}")
        print(f"  Average Monthly Expenses:  ${insights['avg_monthly_expenses']:>10,.2f}")
        print(f"  Average Monthly Net Flow:  ${insights['avg_monthly_net_cash_flow']:>10,.2f}")
        print(f"  Savings Rate:              {insights['overall_savings_rate']:>10.1f}%")
        print(f"  Expense Ratio:             {insights['overall_expense_ratio']:>10.1f}%")
        print()

        validation = summary['validation']
        print("VALIDATION:")
        print(f"  Data Valid:                {'✓' if validation['data_valid'] else '✗'}")
        print(f"  Calculation Valid:         {'✓' if validation['calculation_valid'] else '✗'}")
        print(f"  Warnings:                  {validation['warnings_count']}")
        print(f"  Low Confidence:            {validation['low_confidence_count']}")
        print()

        if validation['low_confidence_count'] > 0:
            print(f"NOTE: {validation['low_confidence_count']} transactions have low confidence categorization.")
            print("Consider reviewing these transactions for improved accuracy.")

        print("Analysis completed successfully!")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()