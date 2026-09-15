"""
JAX Frontend and Jaxpr Lowering Path for Python-HLS.

Provides hardware-bounded JAX array specification, Jaxpr tracing,
IR dataflow mapping, and synthesizable loop lowering for JAX kernels.
"""

from .diagnostics import (
    JAXFrontendError,
    JAXShapeError,
    JAXDTypeError,
    JAXUnsupportedPrimitiveError,
)

from .spec import (
    JAXArraySpec,
    JAXKernelSpec,
    jax_kernel,
    resolve_jax_specs,
    infer_jax_spec,
    normalize_jax_dtype,
    SUPPORTED_DTYPES,
    DTYPE_ALIASES,
)

from .tracing import (
    JaxprGraph,
    JaxprNode,
    JaxprVariable,
    trace_jax_kernel,
    QUALIFIED_JAX_PRIMITIVES,
)

from .ir_mapping import (
    JaxprIRMapper,
    jaxpr_to_ir,
)

from .lowering import (
    JaxprLowering,
    lower_jaxpr_to_ast,
    compile_jaxpr_to_callable,
)

__all__ = [
    "JAXFrontendError",
    "JAXShapeError",
    "JAXDTypeError",
    "JAXUnsupportedPrimitiveError",
    "JAXArraySpec",
    "JAXKernelSpec",
    "jax_kernel",
    "resolve_jax_specs",
    "infer_jax_spec",
    "normalize_jax_dtype",
    "SUPPORTED_DTYPES",
    "DTYPE_ALIASES",
    "JaxprGraph",
    "JaxprNode",
    "JaxprVariable",
    "trace_jax_kernel",
    "QUALIFIED_JAX_PRIMITIVES",
    "JaxprIRMapper",
    "jaxpr_to_ir",
    "JaxprLowering",
    "lower_jaxpr_to_ast",
    "compile_jaxpr_to_callable",
]
