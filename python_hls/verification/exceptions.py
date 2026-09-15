"""
Verification exceptions and diagnostic error classes for Python-HLS RTL verification.
"""

from typing import Optional, Any


class RTLVerificationError(Exception):
    """Base exception for all RTL verification failures."""

    def __init__(self, message: str, module_name: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.module_name = module_name
        self.details = details

    def __str__(self) -> str:
        prefix = f"[{self.module_name}] " if self.module_name else ""
        return f"{prefix}{self.message}"


class RTLVerificationInterfaceError(RTLVerificationError):
    """Raised when an interface signature is not supported by the qualified RTL verification harness."""
    pass


class RTLSimulationTimeoutError(RTLVerificationError):
    """Raised when an RTL simulation fails to assert done within the maximum allowed cycles."""

    def __init__(self, message: str, max_cycles: int, module_name: Optional[str] = None):
        super().__init__(message, module_name=module_name)
        self.max_cycles = max_cycles


class RTLMismatchError(RTLVerificationError):
    """Raised when Python execution and RTL simulation outputs differ."""

    def __init__(self, message: str, mismatch_count: int, total_tests: int, module_name: Optional[str] = None, mismatches: Optional[Any] = None):
        super().__init__(message, module_name=module_name, details=mismatches)
        self.mismatch_count = mismatch_count
        self.total_tests = total_tests
        self.mismatches = mismatches or []
