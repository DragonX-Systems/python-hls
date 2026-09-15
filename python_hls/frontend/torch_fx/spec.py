"""
Tensor specifications, dtype mappings, and broadcasting helpers for PyTorch FX lowering.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict
from .diagnostics import PyTorchShapeError, PyTorchDTypeError

# Canonical dtype table with bit-widths and signedness
SUPPORTED_DTYPES: Dict[str, Dict[str, Any]] = {
    "int8": {"bit_width": 8, "signed": True, "bytes": 1},
    "int16": {"bit_width": 16, "signed": True, "bytes": 2},
    "int32": {"bit_width": 32, "signed": True, "bytes": 4},
    "int64": {"bit_width": 64, "signed": True, "bytes": 8},
    "uint8": {"bit_width": 8, "signed": False, "bytes": 1},
    "float32": {"bit_width": 32, "signed": True, "bytes": 4},
    "float64": {"bit_width": 64, "signed": True, "bytes": 8},
    "qint8": {"bit_width": 8, "signed": True, "bytes": 1},
    "quint8": {"bit_width": 8, "signed": False, "bytes": 1},
    "bool": {"bit_width": 1, "signed": False, "bytes": 1},
}


def normalize_dtype(dtype: Any) -> str:
    """Convert torch.dtype, string, or type object into a canonical dtype string."""
    s = str(dtype).lower()
    if s.startswith("torch."):
        s = s[len("torch."):]
    # Handle aliases
    aliases = {
        "float": "float32",
        "double": "float64",
        "int": "int32",
        "long": "int64",
        "short": "int16",
        "byte": "uint8",
        "char": "int8",
    }
    canonical = aliases.get(s, s)
    if canonical not in SUPPORTED_DTYPES:
        raise PyTorchDTypeError(
            f"Unsupported dtype '{dtype}'. Supported dtypes are: "
            + ", ".join(SUPPORTED_DTYPES.keys()),
            dtype=str(dtype),
        )
    return canonical


@dataclass(frozen=True)
class TensorSpec:
    """Fixed-shape, statically-typed tensor contract for hardware synthesis."""
    name: str
    shape: Tuple[int, ...]
    dtype: str = "float32"
    is_constant: bool = False
    value: Optional[Any] = None
    stride: Optional[Tuple[int, ...]] = None

    def __post_init__(self):
        # Validate shape
        if not isinstance(self.shape, (tuple, list)):
            raise PyTorchShapeError(f"Shape must be a tuple, got {type(self.shape)}", node_name=self.name)
        for d in self.shape:
            if not isinstance(d, int) or d <= 0:
                raise PyTorchShapeError(
                    f"Invalid or dynamic shape dimension '{d}' in shape {self.shape}. "
                    f"All dimensions must be positive compile-time constants.",
                    node_name=self.name,
                    shape=tuple(self.shape),
                )
        if len(self.shape) > 2:
            raise PyTorchShapeError(
                f"Unsupported tensor rank {len(self.shape)} with shape {self.shape}. "
                f"Only 1D vectors and 2D matrices are lowerable to hardware netlists.",
                node_name=self.name,
                shape=tuple(self.shape),
            )

    @property
    def rank(self) -> int:
        return len(self.shape)

    @property
    def total_elements(self) -> int:
        count = 1
        for d in self.shape:
            count *= d
        return count

    @property
    def bytes_per_element(self) -> int:
        norm = normalize_dtype(self.dtype)
        return SUPPORTED_DTYPES[norm]["bytes"]

    @property
    def size_bytes(self) -> int:
        return self.total_elements * self.bytes_per_element


class BroadcastingHelper:
    """Evaluates and verifies broadcasting rules for bounded PyTorch operations."""

    @staticmethod
    def broadcast_shapes(
        s1: Tuple[int, ...],
        s2: Tuple[int, ...],
        op_name: str = "operation",
        node_name: Optional[str] = None,
    ) -> Tuple[int, ...]:
        """
        Compute broadcast output shape for two shapes, or raise PyTorchShapeError.
        Supports scalars (), identical shapes, and 1D/2D row/col broadcasting.
        """
        if len(s1) == 0:
            return s2
        if len(s2) == 0:
            return s1
        if s1 == s2:
            return s1

        # Align lengths from trailing dimensions
        r1 = list(s1)
        r2 = list(s2)
        max_len = max(len(r1), len(r2))
        r1 = [1] * (max_len - len(r1)) + r1
        r2 = [1] * (max_len - len(r2)) + r2

        out_dims = []
        for d1, d2 in zip(r1, r2):
            if d1 == d2:
                out_dims.append(d1)
            elif d1 == 1:
                out_dims.append(d2)
            elif d2 == 1:
                out_dims.append(d1)
            else:
                raise PyTorchShapeError(
                    f"Cannot broadcast shapes {s1} and {s2} in '{op_name}'. "
                    f"Dimensions {d1} and {d2} are incompatible.",
                    node_name=node_name,
                )
        return tuple(out_dims)
