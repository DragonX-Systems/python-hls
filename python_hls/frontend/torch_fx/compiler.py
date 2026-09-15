"""
Compiler integration for end-to-end PyTorch FX model synthesis to hardware netlists.
"""

import os
import tempfile
from typing import Any, Iterable, Optional, Tuple

from .graph import TorchFXGraph, trace_torch_model
from .lowering import TorchFXLowering


def lower_torch_model(
    model: Any,
    example_inputs: Iterable[Any] = (),
    embed_weights: bool = False,
    output_file: Optional[str] = None,
) -> Tuple[str, TorchFXGraph]:
    """
    Trace and lower a PyTorch model into inspectable, synthesizable Python code.
    
    Args:
        model: A torch.nn.Module instance.
        example_inputs: Example concrete tensors for shape propagation.
        embed_weights: Whether to embed weights as constant arrays or parameter ports.
        output_file: Optional path to save the generated Python file.
        
    Returns:
        Tuple of (lowered_python_code, fx_graph).
    """
    fx_graph = trace_torch_model(model, example_inputs=example_inputs)
    lowering = TorchFXLowering(fx_graph, embed_weights=embed_weights)
    lowered_code = lowering.lower_to_code()

    if output_file:
        with open(output_file, "w") as f:
            f.write(lowered_code)

    return lowered_code, fx_graph


def compile_torch_model(
    model: Any,
    example_inputs: Iterable[Any] = (),
    target: str = "verilog",
    output_file: Optional[str] = None,
    opt_level: int = 1,
    tech_node: int = 45,
    embed_weights: bool = False,
    **kwargs: Any,
) -> Any:
    """
    End-to-end compilation of a PyTorch module to hardware netlist (Verilog/VHDL).
    
    Args:
        model: A torch.nn.Module instance.
        example_inputs: Example concrete tensors for shape propagation.
        target: Target hardware description language ("verilog" or "vhdl").
        output_file: Optional path for the generated RTL file.
        opt_level: HLS optimization level (0-3).
        tech_node: Technology node in nm.
        embed_weights: Whether to embed weights as constants or interface ports.
        
    Returns:
        Netlist result or tuple of (netlist, synthesis_logs).
    """
    lowered_code, fx_graph = lower_torch_model(
        model,
        example_inputs=example_inputs,
        embed_weights=embed_weights,
    )

    # Save to temporary or companion .py file for HLS compilation
    if output_file:
        base, _ = os.path.splitext(output_file)
        py_source = f"{base}_lowered.py"
    else:
        fd, py_source = tempfile.mkstemp(suffix=".py", prefix="torch_fx_")
        os.close(fd)

    try:
        with open(py_source, "w") as f:
            f.write(lowered_code)

        from python_hls.hls import HLS
        hls = HLS(optimization_level=opt_level, tech_node=tech_node, **kwargs)
        func_name = fx_graph.name.lower()
        result = hls.compile(
            py_source,
            target=target,
            output_file=output_file,
            entry_function=func_name,
        )
        return result
    finally:
        # Keep py_source if output_file was specified, otherwise remove temp file
        if not output_file and os.path.exists(py_source):
            try:
                os.remove(py_source)
            except OSError:
                pass
