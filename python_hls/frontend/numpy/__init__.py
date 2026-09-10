"""
Bounded NumPy Frontend and Lowering Path for Python-HLS.

Provides hardware-friendly NumPy array specification, diagnostics,
broadcasting rules, and lowering into synthesizable loop constructs.
"""

from .diagnostics import (
    NumPyFrontendError,
    NumPyShapeError,
    NumPyDTypeError,
    NumPyUnsupportedOperationError,
)

from .spec import (
    ArraySpec,
    KernelSpec,
    numpy_kernel,
    resolve_kernel_specs,
    infer_spec_from_value,
    normalize_dtype,
    SUPPORTED_DTYPES,
    DTYPE_ALIASES,
)

from .lowering import (
    NumPyLowering,
    BroadcastingHelper,
)

from .parser import (
    NumPyFrontend,
)

__all__ = [
    "NumPyFrontendError",
    "NumPyShapeError",
    "NumPyDTypeError",
    "NumPyUnsupportedOperationError",
    "ArraySpec",
    "KernelSpec",
    "numpy_kernel",
    "resolve_kernel_specs",
    "infer_spec_from_value",
    "normalize_dtype",
    "SUPPORTED_DTYPES",
    "DTYPE_ALIASES",
    "NumPyLowering",
    "BroadcastingHelper",
    "NumPyFrontend",
]
