"""
Specification and configuration dataclasses for constraint-driven pipelines
and standard interfaces in Python-HLS.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, Callable
import functools


class PipelineInterfaceType(str, Enum):
    """Supported standard interfaces for pipelined accelerators."""
    AXIS = "axis"                  # AXI4-Stream (s_axis_* -> m_axis_*)
    READY_VALID = "ready_valid"    # Standard decoupled stream (in_* -> out_*)
    MEMORY = "memory"              # Decoupled memory lane with waitstate backpressure


@dataclass
class PipelineSpec:
    """
    Specification for a cycle-accounted hardware pipeline.

    Attributes:
        ii: Target initiation interval in clock cycles (default 1).
        depth: Number of pipeline stages / total latency in cycles (>= 1).
        interface: Selected hardware interface protocol.
        data_width: Bit width of data channel (default 32).
        addr_width: Bit width of address channel for memory interfaces (default 32).
        enable_stall: Whether downstream backpressure / stalls are handled (default True).
        enable_drain: Whether in-flight transactions drain when input ceases (default True).
        enable_bubbles: Whether invalid/sparse input bubbles advance cleanly (default True).
    """
    ii: int = 1
    depth: int = 2
    interface: Union[PipelineInterfaceType, str] = PipelineInterfaceType.AXIS
    data_width: int = 32
    addr_width: int = 32
    enable_stall: bool = True
    enable_drain: bool = True
    enable_bubbles: bool = True

    def __post_init__(self):
        if self.ii < 1:
            raise ValueError(f"Initiation interval (ii) must be >= 1, got {self.ii}")
        if self.depth < 1:
            raise ValueError(f"Pipeline depth must be >= 1, got {self.depth}")
        if self.data_width < 1:
            raise ValueError(f"Data width must be >= 1, got {self.data_width}")
        if self.addr_width < 1:
            raise ValueError(f"Address width must be >= 1, got {self.addr_width}")

        if isinstance(self.interface, str):
            try:
                self.interface = PipelineInterfaceType(self.interface.lower())
            except ValueError:
                valid = [e.value for e in PipelineInterfaceType]
                raise ValueError(f"Unknown interface '{self.interface}'. Supported: {valid}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize specification to dictionary."""
        return {
            "ii": self.ii,
            "depth": self.depth,
            "interface": self.interface.value if isinstance(self.interface, PipelineInterfaceType) else str(self.interface),
            "data_width": self.data_width,
            "addr_width": self.addr_width,
            "enable_stall": self.enable_stall,
            "enable_drain": self.enable_drain,
            "enable_bubbles": self.enable_bubbles,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineSpec':
        """Deserialize specification from dictionary."""
        return cls(**data)


# Global registry for pipeline specifications
_pipeline_specs: Dict[str, PipelineSpec] = {}


def pipeline(ii: int = 1, depth: Optional[int] = None, 
             interface: Union[PipelineInterfaceType, str] = PipelineInterfaceType.AXIS,
             data_width: int = 32) -> Callable:
    """
    Decorator to mark a Python function as a constraint-driven pipelined accelerator.

    Args:
        ii: Target initiation interval (throughput rate in cycles/transaction). Default: 1.
        depth: Number of pipeline stages / latency in cycles. Default: 2.
        interface: Interface protocol ('axis', 'ready_valid', or 'memory'). Default: 'axis'.
        data_width: Width in bits of the data stream. Default: 32.

    Example:
        @pipeline(ii=1, depth=3, interface='axis')
        def mac_lane(a: int, b: int, c: int) -> int:
            return a * b + c
    """
    stage_depth = depth if depth is not None else 2
    spec = PipelineSpec(
        ii=ii,
        depth=stage_depth,
        interface=interface,
        data_width=data_width
    )

    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        _pipeline_specs[func_name] = spec
        func._hls_pipeline_spec = spec

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._hls_pipeline_spec = spec
        return wrapper

    return decorator


def get_pipeline_spec(func_name: str) -> Optional[PipelineSpec]:
    """Retrieve registered pipeline specification for a function."""
    return _pipeline_specs.get(func_name)


def clear_pipeline_specs():
    """Clear all registered pipeline specifications (for testing)."""
    _pipeline_specs.clear()
