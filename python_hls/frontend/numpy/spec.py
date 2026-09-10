"""
Specification and contract definitions for bounded NumPy arrays and kernels.
"""

from dataclasses import dataclass, field
import functools
import inspect
from typing import Dict, Tuple, Optional, Any, Callable, List, Union

from .diagnostics import NumPyShapeError, NumPyDTypeError

# Canonical supported dtypes and bit widths
SUPPORTED_DTYPES: Dict[str, int] = {
    "int8": 8,
    "int16": 16,
    "int32": 32,
    "int64": 64,
    "uint8": 8,
    "uint16": 16,
    "uint32": 32,
    "uint64": 64,
    "float32": 32,
    "float64": 64,
    "bool": 1,
}

# Aliases to canonical dtype names
DTYPE_ALIASES: Dict[str, str] = {
    "int": "int32",
    "float": "float32",
    "double": "float64",
    "short": "int16",
    "long": "int64",
    "char": "int8",
    "boolean": "bool",
    "np.int8": "int8",
    "np.int16": "int16",
    "np.int32": "int32",
    "np.int64": "int64",
    "np.uint8": "uint8",
    "np.uint16": "uint16",
    "np.uint32": "uint32",
    "np.uint64": "uint64",
    "np.float32": "float32",
    "np.float64": "float64",
    "np.bool_": "bool",
}


def normalize_dtype(dtype: Any) -> str:
    """Normalize a data type specifier to a canonical string name."""
    if hasattr(dtype, "name"):
        dt_str = str(dtype.name).lower()
    elif hasattr(dtype, "__name__"):
        dt_str = str(dtype.__name__).lower()
    else:
        dt_str = str(dtype).lower()
    dt_str = dt_str.replace("numpy.", "").replace("np.", "").replace("<class '", "").replace("'>", "")

    if dt_str in SUPPORTED_DTYPES:
        return dt_str
    if dt_str in DTYPE_ALIASES:
        return DTYPE_ALIASES[dt_str]

    raise NumPyDTypeError(
        f"Unsupported dtype '{dtype}'. Supported dtypes for hardware synthesis are: "
        f"{', '.join(sorted(SUPPORTED_DTYPES.keys()))}."
    )


@dataclass(frozen=True)
class ArraySpec:
    """Fixed-shape and dtype specification for a hardware-bounded array."""
    shape: Tuple[int, ...]
    dtype: str = "int32"
    layout: str = "C"

    def __post_init__(self):
        # Validate shape
        if not isinstance(self.shape, (tuple, list)):
            raise NumPyShapeError(f"Array shape must be a tuple of integers, got: {type(self.shape).__name__}")

        if len(self.shape) == 0:
            raise NumPyShapeError("Array shape cannot be empty () for array buffers; scalars use standard variables.")

        for idx, dim in enumerate(self.shape):
            if not isinstance(dim, int) or dim <= 0:
                raise NumPyShapeError(
                    f"Array dimension at axis {idx} must be a positive integer, got: {dim}. "
                    "Dynamic or variable-length shapes are not synthesizable."
                )

        # Normalize and validate dtype
        norm_dtype = normalize_dtype(self.dtype)
        # object.__setattr__ because frozen=True
        object.__setattr__(self, "dtype", norm_dtype)
        object.__setattr__(self, "shape", tuple(self.shape))

        # Validate layout
        if self.layout.upper() not in ("C", "ROW_MAJOR"):
            raise NumPyShapeError(
                f"Unsupported array layout '{self.layout}'. Only contiguous C-order ('C') layout is supported."
            )

    @property
    def ndim(self) -> int:
        """Number of dimensions."""
        return len(self.shape)

    @property
    def total_elements(self) -> int:
        """Total number of elements in array."""
        prod = 1
        for d in self.shape:
            prod *= d
        return prod

    @property
    def bit_width(self) -> int:
        """Hardware bit width per element."""
        return SUPPORTED_DTYPES[self.dtype]

    @property
    def size_bytes(self) -> int:
        """Total memory size in bytes."""
        return (self.total_elements * max(1, self.bit_width // 8))


def infer_spec_from_value(value: Any) -> ArraySpec:
    """Infer an ArraySpec from a concrete NumPy ndarray or Python nested list."""
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        shape = tuple(int(s) for s in value.shape)
        return ArraySpec(shape=shape, dtype=str(value.dtype))

    if isinstance(value, (list, tuple)):
        # Infer shape from nested lists
        dims = []
        cur = value
        while isinstance(cur, (list, tuple)):
            dims.append(len(cur))
            cur = cur[0] if len(cur) > 0 else None
        return ArraySpec(shape=tuple(dims), dtype="int32")

    raise NumPyShapeError(f"Cannot infer ArraySpec from non-array value of type {type(value).__name__}")


@dataclass
class KernelSpec:
    """Contract specification for a bounded NumPy kernel function."""
    inputs: Dict[str, ArraySpec] = field(default_factory=dict)
    output: Optional[ArraySpec] = None
    layout: str = "C"


def numpy_kernel(
    shapes: Optional[Dict[str, Tuple[int, ...]]] = None,
    dtypes: Optional[Dict[str, str]] = None,
    layout: str = "C",
) -> Callable:
    """
    Decorator declaring fixed shapes and data types for a bounded NumPy kernel.

    Example:
        @numpy_kernel(
            shapes={"a": (16,), "b": (16,)},
            dtypes={"a": "int32", "b": "int32"}
        )
        def vector_add(a, b):
            return a + b
    """
    def decorator(func: Callable) -> Callable:
        declared_shapes = shapes or {}
        declared_dtypes = dtypes or {}

        input_specs = {}
        for param_name, shape in declared_shapes.items():
            dt = declared_dtypes.get(param_name, "int32")
            input_specs[param_name] = ArraySpec(shape=shape, dtype=dt, layout=layout)

        spec = KernelSpec(inputs=input_specs, layout=layout)
        setattr(func, "__numpy_kernel_spec__", spec)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__numpy_kernel_spec__ = spec
        return wrapper

    return decorator


def resolve_kernel_specs(
    func: Callable,
    shapes: Optional[Dict[str, Tuple[int, ...]]] = None,
    dtypes: Optional[Dict[str, str]] = None,
    example_inputs: Optional[Tuple[Any, ...]] = None,
) -> Dict[str, ArraySpec]:
    """
    Resolve input array specifications for a function from decorator, arguments, or example inputs.
    """
    specs: Dict[str, ArraySpec] = {}

    # 1. Start with decorator specifications if present
    if hasattr(func, "__numpy_kernel_spec__"):
        kernel_spec = getattr(func, "__numpy_kernel_spec__")
        specs.update(kernel_spec.inputs)

    # 2. Apply explicit shapes / dtypes overrides
    if shapes:
        for name, shape in shapes.items():
            dt = (dtypes or {}).get(name, specs.get(name, ArraySpec(shape, "int32")).dtype)
            specs[name] = ArraySpec(shape=shape, dtype=dt)

    # 3. If example_inputs provided, fill in missing specs
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    if example_inputs:
        for idx, val in enumerate(example_inputs):
            if idx < len(param_names):
                p_name = param_names[idx]
                if p_name not in specs:
                    specs[p_name] = infer_spec_from_value(val)

    # Validate that all parameters have specs
    missing = [p for p in param_names if p not in specs]
    if missing:
        raise NumPyShapeError(
            f"Missing fixed-shape specification for parameter(s): {', '.join(missing)}. "
            "Use @numpy_kernel(shapes={...}) or pass example_inputs to specify dimensions."
        )

    return specs
