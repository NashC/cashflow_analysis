"""Custom exceptions for cash flow analysis"""

class CashFlowAnalysisError(Exception):
    """Base exception for cash flow analysis errors"""
    pass

class DataLoadError(CashFlowAnalysisError):
    """Error loading CSV data"""
    pass

class ValidationError(CashFlowAnalysisError):
    """Data validation error"""
    pass

class BalanceReconciliationError(ValidationError):
    """Balance doesn't reconcile within tolerance"""
    def __init__(self, expected: float, actual: float, tolerance: float):
        self.expected = expected
        self.actual = actual
        self.tolerance = tolerance
        self.difference = abs(expected - actual)
        super().__init__(
            f"Balance reconciliation failed: Expected {expected:.2f}, "
            f"got {actual:.2f}, difference {self.difference:.2f} "
            f"exceeds tolerance {tolerance:.2f}"
        )

class CategorizationError(CashFlowAnalysisError):
    """Error during transaction categorization"""
    pass

class FlowTypeError(CategorizationError):
    """Error determining flow type"""
    pass

class ConfigurationError(CashFlowAnalysisError):
    """Configuration file error"""
    pass

class VisualizationError(CashFlowAnalysisError):
    """Error creating visualizations"""
    pass

class ReportGenerationError(CashFlowAnalysisError):
    """Error generating reports"""
    pass