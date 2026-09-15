"""
JAX tracing and Jaxpr inspection graph representation for Python-HLS.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass, field
import inspect
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .diagnostics import (
    JAXFrontendError,
    JAXShapeError,
    JAXDTypeError,
    JAXUnsupportedPrimitiveError,
)
from .spec import (
    JAXArraySpec,
    normalize_jax_dtype,
    resolve_jax_specs,
    SUPPORTED_DTYPES,
)

# Supported lowerable JAX primitives in hardware
QUALIFIED_JAX_PRIMITIVES = {
    "add",
    "sub",
    "mul",
    "div",
    "floor_divide",
    "neg",
    "abs",
    "dot_general",
    "reduce_sum",
    "max",
    "min",
    "clamp",
    "transpose",
    "reshape",
    "broadcast_in_dim",
    "convert_element_type",
}


@dataclass(frozen=True)
class JaxprVariable:
    """A typed variable or constant in a Jaxpr graph."""
    name: str
    shape: Tuple[int, ...]
    dtype: str
    bit_width: int
    is_literal: bool = False
    literal_value: Optional[Any] = None

    @property
    def total_elements(self) -> int:
        prod = 1
        for d in self.shape:
            prod *= d
        return prod

    @property
    def size_bytes(self) -> int:
        return self.total_elements * max(1, self.bit_width // 8)


@dataclass(frozen=True)
class JaxprNode:
    """One primitive equation in a Jaxpr graph."""
    name: str
    primitive: str
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    params: Dict[str, Any]
    shape: Tuple[int, ...]
    dtype: str
    lowerable: bool


@dataclass(frozen=True)
class JaxprGraph:
    """A hardware-analysis and lowering view of a traced JAX kernel."""
    name: str
    nodes: Tuple[JaxprNode, ...]
    inputs: Tuple[JaxprVariable, ...]
    outputs: Tuple[JaxprVariable, ...]
    constants: Tuple[JaxprVariable, ...] = field(default_factory=tuple)
    variables: Dict[str, JaxprVariable] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph to dictionary for inspectability."""
        return {
            "name": self.name,
            "inputs": [asdict(v) for v in self.inputs],
            "outputs": [asdict(v) for v in self.outputs],
            "constants": [asdict(v) for v in self.constants],
            "nodes": [asdict(n) for n in self.nodes],
            "node_count": len(self.nodes),
            "all_lowerable": all(n.lowerable for n in self.nodes),
        }

    def summary(self) -> str:
        """Produce human-readable summary of the traced hardware graph."""
        lines = [f"JaxprGraph: {self.name}"]
        lines.append(f"  Inputs ({len(self.inputs)}):")
        for inp in self.inputs:
            lines.append(f"    %{inp.name}: {inp.dtype}{list(inp.shape)} ({inp.size_bytes}B)")
        lines.append(f"  Nodes ({len(self.nodes)}):")
        for node in self.nodes:
            status = "✓ [HW]" if node.lowerable else "✗ [UNSUPPORTED]"
            lines.append(
                f"    %{','.join(node.outputs)} = {node.primitive}({', '.join(node.inputs)}) -> {node.dtype}{list(node.shape)} {status}"
            )
        lines.append(f"  Outputs ({len(self.outputs)}):")
        for out in self.outputs:
            lines.append(f"    %{out.name}: {out.dtype}{list(out.shape)}")
        return "\n".join(lines)


def _var_name(atom: Any, name_map: Optional[Dict[Any, str]] = None) -> str:
    """Extract clean hardware identifier from a JAX atom (Var or Literal)."""
    if hasattr(atom, "val"):
        val_str = str(atom.val).replace(".", "_").replace("-", "m")
        return f"lit_{val_str}"
    if name_map:
        try:
            if atom in name_map:
                return name_map[atom]
        except TypeError:
            pass
    if hasattr(atom, "count"):
        return f"v_{atom.count}"
    clean_id = "".join(c for c in str(atom) if c.isalnum() or c == "_")
    return f"v_{clean_id}"


def _extract_shape_and_dtype(atom: Any) -> Tuple[Tuple[int, ...], str]:
    """Extract static shape and normalized dtype from a JAX atom or aval."""
    aval = getattr(atom, "aval", atom)
    shape: Tuple[int, ...] = ()
    if hasattr(aval, "shape"):
        dims = []
        for d in aval.shape:
            if not isinstance(d, int) or d <= 0:
                raise JAXShapeError(
                    f"Dynamic or variable-length dimension '{d}' in shape {aval.shape} cannot be synthesized to hardware."
                )
            dims.append(d)
        shape = tuple(dims)

    dtype_raw = getattr(aval, "dtype", "int32")
    norm_dtype = normalize_jax_dtype(dtype_raw)
    return shape, norm_dtype


def _flatten_jaxpr_eqns(eqns: Sequence[Any]) -> List[Any]:
    """Recursively inline and unwrap nested pjit / call equations."""
    flat: List[Any] = []
    for eqn in eqns:
        if eqn.primitive.name in ("pjit", "call", "xla_call") and "jaxpr" in eqn.params:
            sub = eqn.params["jaxpr"]
            sub_jaxpr = sub.jaxpr if hasattr(sub, "jaxpr") else sub
            sub_eqns = _flatten_jaxpr_eqns(sub_jaxpr.eqns)
            v_map = {id(k): v for k, v in zip(sub_jaxpr.invars, eqn.invars)}
            outvar_ids = [id(x) for x in sub_jaxpr.outvars]
            for sub_eqn in sub_eqns:
                new_invars = [v_map.get(id(v), v) for v in sub_eqn.invars]
                new_outvars = []
                for out_v in sub_eqn.outvars:
                    if id(out_v) in outvar_ids:
                        idx = outvar_ids.index(id(out_v))
                        target = eqn.outvars[idx]
                        v_map[id(out_v)] = target
                        new_outvars.append(target)
                    else:
                        new_outvars.append(out_v)
                flat.append(sub_eqn.replace(invars=new_invars, outvars=new_outvars))
        else:
            flat.append(eqn)
    return flat


def trace_jax_kernel(
    kernel: Any,
    example_inputs: Optional[Sequence[Any]] = None,
    array_specs: Optional[Dict[str, JAXArraySpec]] = None,
    strict_primitives: bool = False,
) -> JaxprGraph:
    """
    Trace a JAX function into an inspectable JaxprGraph.

    Args:
        kernel: Python callable, or an existing JAX ClosedJaxpr/Jaxpr object.
        example_inputs: Sample input tensors or ShapedArrays.
        array_specs: Explicit mapping of parameter names to JAXArraySpecs.
        strict_primitives: If True, raise JAXUnsupportedPrimitiveError on non-lowerable primitives.

    Returns:
        A JaxprGraph representing the typed dataflow equations.
    """
    if isinstance(kernel, JaxprGraph):
        return kernel

    try:
        import jax
        import jax.core
        import jax.numpy as jnp
    except ImportError as exc:
        raise JAXFrontendError(
            "JAX support requires the 'jax' package. Install it with: pip install 'jax<=0.4.30' 'jaxlib<=0.4.30'"
        ) from exc

    func_name = getattr(kernel, "__name__", "jax_kernel")
    jaxpr_obj = None
    param_names = []

    if callable(kernel):
        specs = resolve_jax_specs(kernel, example_inputs=tuple(example_inputs) if example_inputs else None)
        if array_specs:
            specs.update(array_specs)

        sig = inspect.signature(kernel)
        param_names = list(sig.parameters.keys())
        dummy_args = []
        for param_name in param_names:
            spec = specs[param_name]
            jnp_dt = getattr(jnp, spec.dtype, jnp.int32)
            dummy_args.append(jax.core.ShapedArray(spec.shape, jnp_dt))

        closed_jaxpr = jax.make_jaxpr(kernel)(*dummy_args)
        jaxpr_obj = closed_jaxpr.jaxpr
    elif hasattr(kernel, "jaxpr"):
        jaxpr_obj = kernel.jaxpr
    elif hasattr(kernel, "eqns"):
        jaxpr_obj = kernel
    else:
        raise JAXFrontendError(f"Expected JAX callable or Jaxpr object, got {type(kernel).__name__}")

    flat_eqns = _flatten_jaxpr_eqns(jaxpr_obj.eqns)

    # Build consistent variable naming map
    atom_name_map: Dict[Any, str] = {}
    for idx, invar in enumerate(jaxpr_obj.invars):
        if idx < len(param_names):
            atom_name_map[invar] = param_names[idx]
        else:
            atom_name_map[invar] = f"in_{idx}"

    for idx, eqn in enumerate(flat_eqns):
        for out_idx, out_var in enumerate(eqn.outvars):
            suffix = f"_{out_idx}" if len(eqn.outvars) > 1 else ""
            atom_name_map[out_var] = f"t_{idx}{suffix}"

    var_dict: Dict[str, JaxprVariable] = {}
    inputs_list: List[JaxprVariable] = []
    outputs_list: List[JaxprVariable] = []
    constants_list: List[JaxprVariable] = []

    # Map inputs
    for invar in jaxpr_obj.invars:
        name = _var_name(invar, atom_name_map)
        shape, dtype = _extract_shape_and_dtype(invar)
        bit_width = SUPPORTED_DTYPES.get(dtype, 32)
        v = JaxprVariable(name=name, shape=shape, dtype=dtype, bit_width=bit_width)
        var_dict[name] = v
        inputs_list.append(v)

    # Map constants
    for cvar in jaxpr_obj.constvars:
        name = _var_name(cvar)
        shape, dtype = _extract_shape_and_dtype(cvar)
        bit_width = SUPPORTED_DTYPES.get(dtype, 32)
        v = JaxprVariable(name=name, shape=shape, dtype=dtype, bit_width=bit_width, is_literal=True)
        var_dict[name] = v
        constants_list.append(v)

    # Map equations
    nodes_list: List[JaxprNode] = []
    for idx, eqn in enumerate(flat_eqns):
        prim_name = eqn.primitive.name
        is_lowerable = prim_name in QUALIFIED_JAX_PRIMITIVES

        if strict_primitives and not is_lowerable:
            raise JAXUnsupportedPrimitiveError(
                f"Unsupported JAX primitive equation '{prim_name}' in hardware flow. "
                f"Qualified primitives: {', '.join(sorted(QUALIFIED_JAX_PRIMITIVES))}."
            )

        in_names = []
        for in_atom in eqn.invars:
            atom_name = _var_name(in_atom, atom_name_map)
            if atom_name not in var_dict:
                sh, dt = _extract_shape_and_dtype(in_atom)
                bw = SUPPORTED_DTYPES.get(dt, 32)
                lit_val = getattr(in_atom, "val", None)
                var_dict[atom_name] = JaxprVariable(
                    name=atom_name, shape=sh, dtype=dt, bit_width=bw, is_literal=(lit_val is not None), literal_value=lit_val
                )
            in_names.append(atom_name)

        out_names = []
        node_shape: Tuple[int, ...] = ()
        node_dtype: str = "int32"
        for out_var in eqn.outvars:
            atom_name = _var_name(out_var, atom_name_map)
            sh, dt = _extract_shape_and_dtype(out_var)
            bw = SUPPORTED_DTYPES.get(dt, 32)
            var_dict[atom_name] = JaxprVariable(name=atom_name, shape=sh, dtype=dt, bit_width=bw)
            out_names.append(atom_name)
            node_shape = sh
            node_dtype = dt

        node_name = f"eqn_{idx}_{prim_name}"
        node = JaxprNode(
            name=node_name,
            primitive=prim_name,
            inputs=tuple(in_names),
            outputs=tuple(out_names),
            params=dict(eqn.params),
            shape=node_shape,
            dtype=node_dtype,
            lowerable=is_lowerable,
        )
        nodes_list.append(node)

    # Map outputs
    for outvar in jaxpr_obj.outvars:
        name = _var_name(outvar, atom_name_map)
        if name in var_dict:
            outputs_list.append(var_dict[name])
        else:
            sh, dt = _extract_shape_and_dtype(outvar)
            bw = SUPPORTED_DTYPES.get(dt, 32)
            v = JaxprVariable(name=name, shape=sh, dtype=dt, bit_width=bw)
            var_dict[name] = v
            outputs_list.append(v)

    return JaxprGraph(
        name=func_name,
        nodes=tuple(nodes_list),
        inputs=tuple(inputs_list),
        outputs=tuple(outputs_list),
        constants=tuple(constants_list),
        variables=var_dict,
    )
