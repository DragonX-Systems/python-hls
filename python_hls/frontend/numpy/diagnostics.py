"""
Deterministic diagnostic exceptions for the bounded NumPy frontend.
"""

class NumPyFrontendError(Exception):
    """Base exception for all bounded NumPy frontend errors."""
    pass


class NumPyShapeError(NumPyFrontendError):
    """
    Exception raised when array shapes are dynamic, incompatible,
    or violate hardware-bounded constraints.
    """
    pass


class NumPyDTypeError(NumPyFrontendError):
    """
    Exception raised when an unsupported data type is used in a NumPy kernel.
    """
    pass


class NumPyUnsupportedOperationError(NumPyFrontendError):
    """
    Exception raised when encountering a NumPy operation or construct
    outside the qualified synthesizable subset.
    """
    pass
