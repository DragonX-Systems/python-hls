"""
Specification and contract definitions for statically bounded JAX arrays and kernels.
"""

from dataclasses import dataclass, field
import functools
import inspect
from typing import Dict, Tuple, Optional, Any, Callable, List, Union

from .diagnostics import JAXShapeError, JAXDTypeError

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

DTYPE_ALIASES: Dict[str, str] = {
    "int": "int32",
    "float": "float32",
    "double": "float64",
    "short": "int16",
    "long": "int64",
    "boolean": "bool",
    "b1": "bool",
    "i8": "int8",
    "i16": "int16",
    "i32": "int32",
    "i64": "int64",
    "u8": "uint8",
    "u16": "uint16",
    "u32": "uint32",
    "u64": "uint64",
    "f32": "float32",
    "f64": "float64",
    "jnp.int8": "int8",
    "jnp.int16": "int16",
    "jnp.int32": "int32",
    "jnp.int64": "int64",
    "jnp.uint8": "uint8",
    "jnp.uint16": "uint16",
    "jnp.uint32": "uint32",
    "jnp.uint64": "uint64",
    "jnp.float32": "float32",
    "jnp.float64": "float64",
    "jnp.bool_": "bool",
}


def normalize_jax_dtype(dtype: Any) -> str:
    """Normalize a JAX/NumPy dtype specifier to a canonical string name."""
    if hasattr(dtype, "name"):
        dt_str = str(dtype.name).lower()
    elif hasattr(dtype, "__name__"):
        dt_str = str(dtype.__name__).lower()
    else:
        dt_str = str(dtype).lower()

    dt_str = (
        dt_str.replace("jax.numpy.", "")
        .replace("jnp.", "")
        .replace("numpy.", "")
        .replace("np.", "")
        .replace("<class '", "")
        .replace("'>", "")
    )

    if dt_str in SUPPORTED_DTYPES:
        return dt_str
    if dt_str in DTYPE_ALIASES:
        return DTYPE_ALIASES[dt_str]

    raise JAXDTypeError(
        f"Unsupported JAX dtype '{dtype}'. Supported dtypes for hardware synthesis are: "
        f"{', '.join(sorted(SUPPORTED_DTYPES.keys()))}."
    )


@dataclass(frozen=True)
class JAXArraySpec:
    """Fixed-shape and dtype specification for a hardware-bounded JAX array."""
    shape: Tuple[int, ...]
    dtype: str = "int32"
    layout: str = "C"

    def __post_init__(self):
        if not isinstance(self.shape, (tuple, list)):
            raise JAXShapeError(f"Array shape must be a tuple of integers, got: {type(self.shape).__name__}")

        if len(self.shape) == 0:
            raise JAXShapeError("Array shape cannot be empty () for hardware buffers; scalars use standard variables.")

        for idx, dim in enumerate(self.shape):
            if not isinstance(dim, int) or dim <= 0:
                raise JAXShapeError(
                    f"Array dimension at axis {idx} must be a positive integer, got: {dim}. "
                    "Dynamic or non-positive shapes cannot be mapped to hardware registers."
                )

        norm_dtype = normalize_jax_dtype(self.dtype)
        object.__setattr__(self, "dtype", norm_dtype)
        object.__setattr__(self, "shape", tuple(self.shape))

        if self.layout.upper() not in ("C", "ROW_MAJOR"):
            raise JAXShapeError(
                f"Unsupported array layout '{self.layout}'. Only contiguous C-order ('C') layout is supported."
            )

    @property
    def ndim(self) -> int:
        """Number of dimensions."""
        return len(self.shape)

    @property
    def total_elements(self) -> int:
        """Total element count."""
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
        return self.total_elements * max(1, self.bit_width // 8)


def infer_jax_spec(value: Any) -> JAXArraySpec:
    """Infer JAXArraySpec from a concrete array, JAX ShapedArray, or nested list."""
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        shape = tuple(int(s) for s in value.shape)
        return JAXArraySpec(shape=shape, dtype=str(value.dtype))

    if isinstance(value, (list, tuple)):
        dims = []
        cur = value
        while isinstance(cur, (list, tuple)):
            dims.append(len(cur))
            cur = cur[0] if len(cur) > 0 else None
        return JAXArraySpec(shape=tuple(dims), dtype="int32")

    raise JAXShapeError(f"Cannot infer JAXArraySpec from non-array value of type {type(value).__name__}")


@dataclass
class JAXKernelSpec:
    """Contract specification for a bounded JAX kernel."""
    inputs: Dict[str, JAXArraySpec] = field(default_factory=dict)
    output: Optional[JAXArraySpec] = None
    layout: str = "C"


def jax_kernel(
    shapes: Optional[Dict[str, Tuple[int, ...]]] = None,
    dtypes: Optional[Dict[str, str]] = None,
    layout: str = "C",
) -> Callable:
    """
    Decorator declaring fixed shapes and data types for a bounded JAX kernel.

    Example:
        @jax_kernel(
            shapes={"x": (16,), "y": (16,)},
            dtypes={"x": "int32", "y": "int32"}
        )
        def vector_add(x, y):
            return x + y
    """
    def decorator(func: Callable) -> Callable:
        declared_shapes = shapes or {}
        declared_dtypes = dtypes or {}

        input_specs = {}
        for param_name, shp in declared_shapes.items():
            dt = declared_dtypes.get(param_name, "int32")
            input_specs[param_name] = JAXArraySpec(shape=shp, dtype=dt, layout=layout)

        spec = JAXKernelSpec(inputs=input_specs, layout=layout)
        setattr(func, "__jax_kernel_spec__", spec)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__jax_kernel_spec__ = spec
        return wrapper

    return decorator


def resolve_jax_specs(
    func: Callable,
    shapes: Optional[Dict[str, Tuple[int, ...]]] = None,
    dtypes: Optional[Dict[str, str]] = None,
    example_inputs: Optional[Tuple[Any, ...]] = None,
) -> Dict[str, JAXArraySpec]:
    """Resolve input JAXArraySpecs for a function from decorator, explicit args, or example inputs."""
    specs: Dict[str, JAXArraySpec] = {}

    if hasattr(func, "__jax_kernel_spec__"):
        kernel_spec = getattr(func, "__jax_kernel_spec__")
        specs.update(kernel_spec.inputs)

    if shapes:
        for name, shape in shapes.items():
            dt = (dtypes or {}).get(name, specs.get(name, JAXArraySpec(shape, "int32")).dtype)
            specs[name] = JAXArraySpec(shape=shape, dtype=dt)

    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    if example_inputs:
        for idx, val in enumerate(example_inputs):
            if idx < len(param_names):
                p_name = param_names[idx]
                if p_name not in specs:
                    specs[p_name] = infer_jax_spec(val)

    missing = [p for p in param_names if p not in specs]
    if missing:
        raise JAXShapeError(
            f"Missing fixed-shape specification for JAX parameter(s): {', '.join(missing)}. "
            "Use @jax_kernel(shapes={...}) or pass example_inputs to specify dimensions."
        )

    return specs
