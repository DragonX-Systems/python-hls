"""PyTorch FX graph import for Python-HLS analysis.

This optional frontend captures a ``torch.nn.Module`` as a stable, serializable
operation graph. It deliberately does not claim that every PyTorch operator is
hardware-lowerable: tensor lowering, quantization, memory mapping, and interface
generation remain separate HLS steps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class TorchFXNode:
    """One node captured from a PyTorch FX graph."""

    name: str
    operation: str
    inputs: tuple[str, ...]
    shape: Optional[tuple[int, ...]]
    dtype: Optional[str]
    lowerable: bool


@dataclass(frozen=True)
class TorchFXGraph:
    """A hardware-analysis view of a traced PyTorch model."""

    nodes: tuple[TorchFXNode, ...]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "nodes": [asdict(node) for node in self.nodes],
        }


_LOWERABLE_TOKENS = ("add", "sub", "mul", "matmul", "linear", "relu")


def trace_torch_model(model: Any, example_inputs: Iterable[Any] = ()) -> TorchFXGraph:
    """Trace a PyTorch module into an analysis graph.

    PyTorch is an optional dependency. ``example_inputs`` enables shape
    propagation when concrete tensors are supplied. The result is intentionally
    analysis-only until an operation has a qualified lowering to Python-HLS IR.
    """
    try:
        import torch.fx
        from torch.fx.passes.shape_prop import ShapeProp
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PyTorch support requires the optional 'ml' dependency. "
            "Install it with: pip install -e '.[ml]'"
        ) from exc

    graph_module = torch.fx.symbolic_trace(model.eval())
    inputs = tuple(example_inputs)
    if inputs:
        ShapeProp(graph_module).propagate(*inputs)

    nodes: list[TorchFXNode] = []
    input_names: list[str] = []
    output_names: list[str] = []
    for node in graph_module.graph.nodes:
        if node.op == "placeholder":
            input_names.append(node.name)
            continue
        if node.op == "output":
            output_names.extend(_node_names(node.args))
            continue

        operation = _operation_name(node, graph_module)
        metadata = node.meta.get("tensor_meta") if hasattr(node, "meta") else None
        shape = tuple(metadata.shape) if metadata and metadata.shape else None
        dtype = str(metadata.dtype) if metadata and metadata.dtype else None
        nodes.append(
            TorchFXNode(
                name=node.name,
                operation=operation,
                inputs=tuple(_node_names(node.args)),
                shape=shape,
                dtype=dtype,
                lowerable=any(token in operation.lower() for token in _LOWERABLE_TOKENS),
            )
        )

    return TorchFXGraph(tuple(nodes), tuple(input_names), tuple(output_names))


def _operation_name(node: Any, graph_module: Any) -> str:
    if node.op == "call_module":
        return type(graph_module.get_submodule(node.target)).__name__
    target = getattr(node, "target", None)
    return str(target) if target is not None else node.op


def _node_names(value: Any) -> list[str]:
    if hasattr(value, "name") and hasattr(value, "op"):
        return [value.name]
    if isinstance(value, (tuple, list)):
        return [name for item in value for name in _node_names(item)]
    return []
