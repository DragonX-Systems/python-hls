"""
Deterministic diagnostics and exception hierarchy for the PyTorch FX frontend.
"""

from typing import Optional


class PyTorchFrontendError(Exception):
    """Base exception for all PyTorch FX frontend and lowering errors."""
    pass


class PyTorchShapeError(PyTorchFrontendError):
    """Raised when tensor shapes are dynamic, have invalid rank, or fail broadcasting."""

    def __init__(self, message: str, node_name: Optional[str] = None, shape: Optional[tuple] = None):
        self.node_name = node_name
        self.shape = shape
        prefix = f"[Node '{node_name}'] " if node_name else ""
        super().__init__(f"{prefix}{message}")


class PyTorchDTypeError(PyTorchFrontendError):
    """Raised when a tensor has an unsupported or non-synthesizable dtype."""

    def __init__(self, message: str, node_name: Optional[str] = None, dtype: Optional[str] = None):
        self.node_name = node_name
        self.dtype = dtype
        prefix = f"[Node '{node_name}'] " if node_name else ""
        super().__init__(f"{prefix}{message}")


class PyTorchUnsupportedOperationError(PyTorchFrontendError):
    """Raised when an FX graph node targets an unsupported PyTorch operation."""

    def __init__(self, operation: str, node_name: Optional[str] = None, details: Optional[str] = None):
        self.operation = operation
        self.node_name = node_name
        msg = f"Unsupported PyTorch operation '{operation}'"
        if node_name:
            msg = f"[Node '{node_name}'] {msg}"
        if details:
            msg += f": {details}"
        super().__init__(msg)
