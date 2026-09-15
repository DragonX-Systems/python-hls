"""
Graph representation and symbolic tracing for PyTorch FX models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional, Tuple, Dict, List

from .spec import TensorSpec, normalize_dtype
from .diagnostics import PyTorchFrontendError, PyTorchShapeError

_LOWERABLE_TOKENS = (
    "add", "sub", "subtract", "mul", "multiply", "div", "divide", "truediv", "floordiv",
    "matmul", "linear", "relu", "clamp", "hardtanh", "neg", "negative", "abs",
    "sum", "mean"
)


@dataclass(frozen=True)
class TorchFXNode:
    """One node captured from a PyTorch FX graph."""
    name: str
    operation: str
    target: str
    op_type: str  # "placeholder", "call_module", "call_function", "call_method", "output"
    inputs: Tuple[str, ...]
    args: Tuple[Any, ...] = ()
    shape: Optional[Tuple[int, ...]] = None
    dtype: Optional[str] = None
    kwargs: Dict[str, Any] = field(default_factory=dict)
    lowerable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "operation": self.operation,
            "target": self.target,
            "op_type": self.op_type,
            "inputs": list(self.inputs),
            "args": list(self.args),
            "shape": list(self.shape) if self.shape else None,
            "dtype": self.dtype,
            "kwargs": self.kwargs,
            "lowerable": self.lowerable,
        }


@dataclass
class TorchFXGraph:
    """A hardware-analysis and lowering view of a traced PyTorch model."""
    name: str
    nodes: Tuple[TorchFXNode, ...]
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    tensor_specs: Dict[str, TensorSpec] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)  # parameter name -> tensor/array
    raw_graph_module: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "nodes": [n.to_dict() for n in self.nodes],
            "parameters": list(self.parameters.keys()),
        }


def trace_torch_model(
    model: Any,
    example_inputs: Iterable[Any] = (),
    model_name: Optional[str] = None,
) -> TorchFXGraph:
    """
    Trace a PyTorch module into a typed, hardware-lowerable TorchFXGraph.
    
    Args:
        model: A torch.nn.Module instance.
        example_inputs: Tuple/list of concrete example input tensors for shape propagation.
        model_name: Optional name for the model (defaults to class name).
        
    Returns:
        TorchFXGraph ready for inspection and lowering.
    """
    try:
        import torch
        import torch.fx
        from torch.fx.passes.shape_prop import ShapeProp
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch support requires the optional 'ml' dependency. "
            "Install it with: pip install -e '.[ml]'"
        ) from exc

    name = model_name or type(model).__name__
    graph_module = torch.fx.symbolic_trace(model.eval())
    inputs = tuple(example_inputs)

    # Propagate shapes and dtypes if concrete tensors provided
    if inputs:
        try:
            ShapeProp(graph_module).propagate(*inputs)
        except Exception as exc:
            raise PyTorchShapeError(f"Shape propagation failed: {exc}") from exc

    nodes: List[TorchFXNode] = []
    input_names: List[str] = []
    output_names: List[str] = []
    tensor_specs: Dict[str, TensorSpec] = {}
    parameters: Dict[str, Any] = {}

    # Extract all weights and biases from submodules and named parameters
    for param_name, param_tensor in model.named_parameters():
        clean_name = param_name.replace(".", "_")
        shape = tuple(param_tensor.shape)
        dtype = normalize_dtype(param_tensor.dtype)
        val = param_tensor.detach().cpu().numpy()
        tensor_specs[clean_name] = TensorSpec(
            name=clean_name,
            shape=shape,
            dtype=dtype,
            is_constant=True,
            value=val,
        )
        parameters[clean_name] = val

    for node in graph_module.graph.nodes:
        if node.op == "placeholder":
            input_names.append(node.name)
            metadata = node.meta.get("tensor_meta") if hasattr(node, "meta") else None
            if metadata is not None and getattr(metadata, "shape", None) is not None:
                shape = tuple(metadata.shape)
                dtype = normalize_dtype(metadata.dtype)
                tensor_specs[node.name] = TensorSpec(name=node.name, shape=shape, dtype=dtype)
            continue

        if node.op == "output":
            output_names.extend(_node_names(node.args))
            continue

        operation = _operation_name(node, graph_module)
        target_str = str(node.target)
        metadata = node.meta.get("tensor_meta") if hasattr(node, "meta") else None
        shape = tuple(metadata.shape) if (metadata is not None and getattr(metadata, "shape", None) is not None) else None
        dtype = normalize_dtype(metadata.dtype) if (metadata is not None and getattr(metadata, "dtype", None) is not None) else None

        if shape is not None and dtype is not None:
            tensor_specs[node.name] = TensorSpec(name=node.name, shape=shape, dtype=dtype)

        op_lower = operation.lower()
        lowerable = any(token in op_lower for token in _LOWERABLE_TOKENS)

        # Clean kwargs: serialize non-tensor arguments and submodule attributes
        kwargs_clean = {}
        if node.op == "call_module":
            try:
                submod = graph_module.get_submodule(node.target)
                for attr in ("min_val", "max_val", "min", "max"):
                    if hasattr(submod, attr):
                        val = getattr(submod, attr)
                        if isinstance(val, (int, float)):
                            kwargs_clean[attr] = val
            except Exception:
                pass

        for k, v in node.kwargs.items():
            if not hasattr(v, "op"):
                kwargs_clean[k] = v

        nodes.append(
            TorchFXNode(
                name=node.name,
                operation=operation,
                target=target_str,
                op_type=node.op,
                inputs=tuple(_node_names(node.args)),
                args=tuple(_format_arg(a) for a in node.args),
                shape=shape,
                dtype=dtype,
                kwargs=kwargs_clean,
                lowerable=lowerable,
            )
        )

    return TorchFXGraph(
        name=name,
        nodes=tuple(nodes),
        inputs=tuple(input_names),
        outputs=tuple(output_names),
        tensor_specs=tensor_specs,
        parameters=parameters,
        raw_graph_module=graph_module,
    )


def _operation_name(node: Any, graph_module: Any) -> str:
    """Extract human-readable operation name from an FX node."""
    if node.op == "call_module":
        submod = graph_module.get_submodule(node.target)
        return type(submod).__name__
    target = getattr(node, "target", None)
    if callable(target):
        return getattr(target, "__name__", str(target))
    return str(target) if target is not None else node.op


def _node_names(value: Any) -> List[str]:
    """Recursively collect node names from arguments."""
    if hasattr(value, "name") and hasattr(value, "op"):
        return [value.name]
    if isinstance(value, (tuple, list)):
        return [name for item in value for name in _node_names(item)]
    return []


def _format_arg(arg: Any) -> Any:
    """Format an FX argument into a string node name, scalar literal, or nested list."""
    if hasattr(arg, "name") and hasattr(arg, "op"):
        return arg.name
    if isinstance(arg, (int, float, bool, str)):
        return arg
    if isinstance(arg, (tuple, list)):
        return [_format_arg(item) for item in arg]
    return str(arg)

