"""
Lowering engine for PyTorch FX graphs to synthesizable Python-HLS kernels.

Transforms high-level PyTorch tensor operations (elementwise arithmetic, linear/matmul,
activations, and reductions) into bounded loops with explicit memory accesses and
memory size metadata suitable for hardware synthesis.
"""

import ast
from typing import Dict, List, Tuple, Optional, Any, Set
from .spec import TensorSpec, BroadcastingHelper, normalize_dtype
from .diagnostics import (
    PyTorchShapeError,
    PyTorchDTypeError,
    PyTorchUnsupportedOperationError,
)
from .graph import TorchFXGraph, TorchFXNode


class TorchFXLowering:
    """
    Lowers a TorchFXGraph into clean, synthesizable Python code and AST.
    """

    SUPPORTED_BINARY_OPS = {
        "add": "+",
        "sub": "-",
        "subtract": "-",
        "mul": "*",
        "multiply": "*",
        "div": "//",
        "divide": "//",
        "truediv": "//",
        "floordiv": "//",
        "floor_divide": "//",
    }

    SUPPORTED_UNARY_OPS = {
        "neg": "-",
        "negative": "-",
        "abs": "abs",
    }

    def __init__(self, graph: TorchFXGraph, embed_weights: bool = False):
        self.graph = graph
        self.embed_weights = embed_weights
        self.temp_id = 0
        self.node_output_map: Dict[str, str] = {}  # FX node name -> variable name in code
        self.tensor_specs: Dict[str, TensorSpec] = dict(graph.tensor_specs)

    def _next_temp(self, prefix: str = "_t") -> str:
        name = f"{prefix}_{self.temp_id}"
        self.temp_id += 1
        return name

    def lower_to_code(self) -> str:
        """
        Lower the PyTorch FX graph into inspectable, synthesizable Python source code.
        """
        self._validate_graph()

        lines: List[str] = []
        indent = "    "

        # Determine parameter names and model inputs
        input_args = list(self.graph.inputs)
        param_args = []
        if not self.embed_weights:
            param_args = list(self.graph.parameters.keys())

        # Check output tensor
        out_node_name = self.graph.outputs[0] if self.graph.outputs else "out"
        out_spec = self.tensor_specs.get(out_node_name)
        is_scalar_out = out_spec is not None and out_spec.rank == 0

        # Function signature
        all_args = list(input_args) + list(param_args)
        if not is_scalar_out:
            all_args.append("out")

        func_name = self._sanitize_name(self.graph.name.lower())
        lines.append(f"def {func_name}({', '.join(all_args)}):")
        lines.append(f'{indent}"""Synthesized from PyTorch model: {self.graph.name}"""')

        # 1. Memory size annotations
        for inp_name in input_args:
            spec = self.tensor_specs.get(inp_name)
            if spec:
                lines.append(f"{indent}{inp_name}_memory_size = {spec.size_bytes}")

        if not self.embed_weights:
            for p_name in param_args:
                spec = self.tensor_specs.get(p_name)
                if spec:
                    lines.append(f"{indent}{p_name}_memory_size = {spec.size_bytes}")
        else:
            # Embed parameters as constant arrays
            for p_name, p_val in self.graph.parameters.items():
                val_list = p_val.tolist() if hasattr(p_val, "tolist") else list(p_val)
                lines.append(f"{indent}{p_name} = {repr(val_list)}")
                spec = self.tensor_specs.get(p_name)
                if spec:
                    lines.append(f"{indent}{p_name}_memory_size = {spec.size_bytes}")

        if not is_scalar_out and out_spec:
            lines.append(f"{indent}out_memory_size = {out_spec.size_bytes}")

        lines.append("")

        # 2. Lower operations node-by-node
        for idx, node in enumerate(self.graph.nodes):
            is_final_node = (idx == len(self.graph.nodes) - 1) or (node.name == out_node_name)
            target_var = "out" if (is_final_node and not is_scalar_out) else self._next_temp(f"_{node.name}")
            self.node_output_map[node.name] = target_var

            node_lines = self._lower_node(node, target_var, indent)
            lines.extend(node_lines)
            lines.append("")

        # 3. Return statement
        if is_scalar_out:
            final_var = self.node_output_map.get(out_node_name, "0")
            lines.append(f"{indent}return {final_var}")
        else:
            lines.append(f"{indent}return out")

        return "\n".join(lines)

    def lower_to_ast(self) -> ast.FunctionDef:
        """Parse the generated code into an ast.FunctionDef."""
        code = self.lower_to_code()
        module_ast = ast.parse(code)
        for stmt in module_ast.body:
            if isinstance(stmt, ast.FunctionDef):
                return stmt
        raise RuntimeError("Failed to extract FunctionDef from lowered PyTorch code")

    def _validate_graph(self) -> None:
        """Verify that all nodes have valid static shapes and supported operations."""
        for node in self.graph.nodes:
            # Check shape
            if node.shape is None:
                raise PyTorchShapeError(
                    "Missing static shape metadata. Ensure example_inputs are passed for shape propagation.",
                    node_name=node.name,
                )
            for d in node.shape:
                if not isinstance(d, int) or d <= 0:
                    raise PyTorchShapeError(
                        f"Dynamic or invalid dimension '{d}' in shape {node.shape}. "
                        f"All dimensions must be positive static integers.",
                        node_name=node.name,
                        shape=node.shape,
                    )
            if len(node.shape) > 2:
                raise PyTorchShapeError(
                    f"Unsupported tensor rank {len(node.shape)} with shape {node.shape}. "
                    f"Only 1D vectors and 2D matrices are synthesizable.",
                    node_name=node.name,
                    shape=node.shape,
                )

            # Check operation
            if not self._is_supported_operation(node):
                raise PyTorchUnsupportedOperationError(
                    operation=node.operation,
                    node_name=node.name,
                    details="Qualified operations are: elementwise arithmetic (add, sub, mul, div), "
                            "linear/matmul, activations (relu, clamp, hardtanh), and reductions (sum, mean).",
                )

    def _is_supported_operation(self, node: TorchFXNode) -> bool:
        op = node.operation.lower()
        if any(b in op for b in self.SUPPORTED_BINARY_OPS):
            return True
        if any(u in op for u in self.SUPPORTED_UNARY_OPS):
            return True
        if any(k in op for k in ("linear", "matmul", "bmm", "dot")):
            return True
        if any(a in op for a in ("relu", "clamp", "hardtanh")):
            return True
        if any(r in op for r in ("sum", "mean")):
            return True
        return False

    def _lower_node(self, node: TorchFXNode, target_var: str, indent: str) -> List[str]:
        """Dispatch lowering to specialized generator."""
        op = node.operation.lower()

        # Allocate buffer if target_var is not 'out'
        alloc_lines = []
        if target_var != "out" and node.shape is not None and len(node.shape) > 0:
            alloc_lines = self._allocate_buffer(target_var, node.shape, indent)

        # 1. Linear layer (call_module with Linear)
        if "linear" in op:
            return alloc_lines + self._lower_linear(node, target_var, indent)

        # 2. Matmul
        if any(m in op for m in ("matmul", "bmm", "dot")):
            return alloc_lines + self._lower_matmul(node, target_var, indent)

        # 3. Activations
        if "relu" in op:
            return alloc_lines + self._lower_relu(node, target_var, indent)
        if "clamp" in op or "hardtanh" in op:
            return alloc_lines + self._lower_clamp(node, target_var, indent)

        # 4. Reductions
        if "sum" in op:
            return self._lower_reduction(node, target_var, indent, is_mean=False)
        if "mean" in op:
            return self._lower_reduction(node, target_var, indent, is_mean=True)

        # 5. Elementwise binary
        for b_name, b_op in self.SUPPORTED_BINARY_OPS.items():
            if b_name in op:
                return alloc_lines + self._lower_elementwise_binary(node, b_op, target_var, indent)

        # 6. Elementwise unary
        for u_name, u_op in self.SUPPORTED_UNARY_OPS.items():
            if u_name in op:
                return alloc_lines + self._lower_elementwise_unary(node, u_op, target_var, indent)

        raise PyTorchUnsupportedOperationError(node.operation, node_name=node.name)

    def _allocate_buffer(self, var_name: str, shape: Tuple[int, ...], indent: str) -> List[str]:
        """Generate static buffer allocation."""
        if len(shape) == 1:
            return [f"{indent}{var_name} = [0] * {shape[0]}"]
        elif len(shape) == 2:
            r, c = shape
            return [f"{indent}{var_name} = [[0] * {c} for _ in range({r})]"]
        return []

    def _resolve_input(self, input_name: str) -> str:
        """Resolve FX node name to generated variable name or parameter."""
        return self.node_output_map.get(input_name, input_name)

    def _lower_linear(self, node: TorchFXNode, target_var: str, indent: str) -> List[str]:
        """
        Lower nn.Linear or F.linear: y = x * W^T + b.
        In PyTorch, Linear weight has shape [out_features, in_features].
        """
        lines = []
        inp_var = self._resolve_input(node.inputs[0])
        inp_spec = self.tensor_specs.get(node.inputs[0])
        out_shape = node.shape or (1,)

        # Identify weight and bias parameter names
        prefix = node.target.replace(".", "_")
        weight_name = f"{prefix}_weight"
        bias_name = f"{prefix}_bias"
        has_bias = bias_name in self.graph.parameters or f"{prefix}.bias" in self.graph.parameters

        # Check if 1D input or 2D batch
        if len(out_shape) == 1:
            out_features = out_shape[0]
            in_features = inp_spec.shape[0] if inp_spec else 1

            lines.append(f"{indent}for _i in range({out_features}):")
            if has_bias:
                lines.append(f"{indent}    _acc = {bias_name}[_i]")
            else:
                lines.append(f"{indent}    _acc = 0")
            lines.append(f"{indent}    for _j in range({in_features}):")
            lines.append(f"{indent}        _acc += {weight_name}[_i][_j] * {inp_var}[_j]")
            lines.append(f"{indent}    {target_var}[_i] = _acc")

        elif len(out_shape) == 2:
            batch_size, out_features = out_shape
            in_features = inp_spec.shape[1] if inp_spec and len(inp_spec.shape) == 2 else 1

            lines.append(f"{indent}for _b in range({batch_size}):")
            lines.append(f"{indent}    for _i in range({out_features}):")
            if has_bias:
                lines.append(f"{indent}        _acc = {bias_name}[_i]")
            else:
                lines.append(f"{indent}        _acc = 0")
            lines.append(f"{indent}        for _j in range({in_features}):")
            lines.append(f"{indent}            _acc += {weight_name}[_i][_j] * {inp_var}[_b][_j]")
            lines.append(f"{indent}        {target_var}[_b][_i] = _acc")

        return lines

    def _lower_matmul(self, node: TorchFXNode, target_var: str, indent: str) -> List[str]:
        """Lower 2D matrix multiplication: target = A @ B."""
        lines = []
        if len(node.inputs) < 2:
            raise PyTorchShapeError("Matmul requires at least 2 input tensors", node_name=node.name)

        a_var = self._resolve_input(node.inputs[0])
        b_var = self._resolve_input(node.inputs[1])
        a_spec = self.tensor_specs.get(node.inputs[0])
        b_spec = self.tensor_specs.get(node.inputs[1])

        if not a_spec or not b_spec:
            raise PyTorchShapeError("Missing tensor shapes for matmul operands", node_name=node.name)

        m = a_spec.shape[0]
        k = a_spec.shape[1] if len(a_spec.shape) > 1 else a_spec.shape[0]
        n = b_spec.shape[1] if len(b_spec.shape) > 1 else 1

        lines.append(f"{indent}for _i in range({m}):")
        lines.append(f"{indent}    for _j in range({n}):")
        lines.append(f"{indent}        _acc = 0")
        lines.append(f"{indent}        for _k in range({k}):")
        lines.append(f"{indent}            _acc += {a_var}[_i][_k] * {b_var}[_k][_j]")
        lines.append(f"{indent}        {target_var}[_i][_j] = _acc")
        return lines

    def _lower_relu(self, node: TorchFXNode, target_var: str, indent: str) -> List[str]:
        """Lower ReLU activation: target = max(0, x)."""
        lines = []
        inp_var = self._resolve_input(node.inputs[0])
        shape = node.shape or (1,)

        if len(shape) == 1:
            lines.append(f"{indent}for _i in range({shape[0]}):")
            lines.append(f"{indent}    _val = {inp_var}[_i]")
            lines.append(f"{indent}    if _val < 0:")
            lines.append(f"{indent}        _val = 0")
            lines.append(f"{indent}    {target_var}[_i] = _val")
        elif len(shape) == 2:
            r, c = shape
            lines.append(f"{indent}for _i in range({r}):")
            lines.append(f"{indent}    for _j in range({c}):")
            lines.append(f"{indent}        _val = {inp_var}[_i][_j]")
            lines.append(f"{indent}        if _val < 0:")
            lines.append(f"{indent}            _val = 0")
            lines.append(f"{indent}        {target_var}[_i][_j] = _val")
        return lines

    def _lower_clamp(self, node: TorchFXNode, target_var: str, indent: str) -> List[str]:
        """Lower clamp / hardtanh: target = min(max(x, min_val), max_val)."""
        lines = []
        inp_var = self._resolve_input(node.inputs[0]) if node.inputs else ""
        shape = node.shape or (1,)

        min_val = node.kwargs.get("min")
        if min_val is None:
            min_val = node.kwargs.get("min_val")
        if min_val is None and len(node.args) > 1 and node.args[1] is not None:
            min_val = node.args[1]
        if min_val is None:
            min_val = -1 if "hardtanh" in node.operation.lower() else 0

        max_val = node.kwargs.get("max")
        if max_val is None:
            max_val = node.kwargs.get("max_val")
        if max_val is None and len(node.args) > 2 and node.args[2] is not None:
            max_val = node.args[2]
        if max_val is None:
            max_val = 1 if "hardtanh" in node.operation.lower() else 100

        if len(shape) == 1:
            lines.append(f"{indent}for _i in range({shape[0]}):")
            lines.append(f"{indent}    _val = {inp_var}[_i]")
            lines.append(f"{indent}    if _val < {min_val}:")
            lines.append(f"{indent}        _val = {min_val}")
            lines.append(f"{indent}    if _val > {max_val}:")
            lines.append(f"{indent}        _val = {max_val}")
            lines.append(f"{indent}    {target_var}[_i] = _val")
        elif len(shape) == 2:
            r, c = shape
            lines.append(f"{indent}for _i in range({r}):")
            lines.append(f"{indent}    for _j in range({c}):")
            lines.append(f"{indent}        _val = {inp_var}[_i][_j]")
            lines.append(f"{indent}        if _val < {min_val}:")
            lines.append(f"{indent}            _val = {min_val}")
            lines.append(f"{indent}        if _val > {max_val}:")
            lines.append(f"{indent}            _val = {max_val}")
            lines.append(f"{indent}        {target_var}[_i][_j] = _val")
        return lines

    def _resolve_operand(self, node: TorchFXNode, arg_idx: int, fallback_name: str) -> Tuple[str, Optional[TensorSpec], bool]:
        """Resolve an operand to (var_name_or_literal, spec, is_scalar)."""
        arg_val = node.args[arg_idx] if len(node.args) > arg_idx else None

        if isinstance(arg_val, (int, float, bool)):
            return str(arg_val), None, True

        target_name = ""
        if isinstance(arg_val, str) and (arg_val in self.tensor_specs or arg_val in self.graph.inputs):
            target_name = arg_val
        elif fallback_name:
            target_name = fallback_name
        elif isinstance(arg_val, str):
            return arg_val, None, True

        if target_name:
            spec = self.tensor_specs.get(target_name)
            var_name = self._resolve_input(target_name)
            is_scalar = (spec is not None and spec.rank == 0)
            return var_name, spec, is_scalar

        return "0", None, True

    def _lower_reduction(self, node: TorchFXNode, target_var: str, indent: str, is_mean: bool) -> List[str]:
        """Lower sum or mean reduction to scalar."""
        lines = []
        inp_var = self._resolve_input(node.inputs[0])
        inp_spec = self.tensor_specs.get(node.inputs[0])
        shape = inp_spec.shape if inp_spec else (1,)

        lines.append(f"{indent}_acc = 0")
        if len(shape) == 1:
            lines.append(f"{indent}for _i in range({shape[0]}):")
            lines.append(f"{indent}    _acc += {inp_var}[_i]")
            denom = shape[0]
        elif len(shape) == 2:
            r, c = shape
            lines.append(f"{indent}for _i in range({r}):")
            lines.append(f"{indent}    for _j in range({c}):")
            lines.append(f"{indent}        _acc += {inp_var}[_i][_j]")
            denom = r * c
        else:
            denom = 1

        if is_mean and denom > 1:
            lines.append(f"{indent}{target_var} = _acc // {denom}")
        else:
            lines.append(f"{indent}{target_var} = _acc")
        return lines

    def _lower_elementwise_binary(self, node: TorchFXNode, op_str: str, target_var: str, indent: str) -> List[str]:
        """Lower elementwise binary operations with static broadcasting support."""
        lines = []
        left_name = node.inputs[0] if len(node.inputs) > 0 else ""
        right_name = node.inputs[1] if len(node.inputs) > 1 else ""

        left_var, left_spec, left_is_scalar = self._resolve_operand(node, 0, left_name)
        right_var, right_spec, right_is_scalar = self._resolve_operand(node, 1, right_name)

        out_shape = node.shape or (1,)

        if len(out_shape) == 1:
            length = out_shape[0]
            lines.append(f"{indent}for _i in range({length}):")
            if left_is_scalar or left_spec is None or left_spec.rank == 0:
                l_expr = left_var
            elif left_spec.rank == 1 and left_spec.shape[0] == length:
                l_expr = f"{left_var}[_i]"
            elif left_spec.rank == 1 and left_spec.shape[0] == 1:
                l_expr = f"{left_var}[0]"
            else:
                l_expr = f"{left_var}[_i]"

            if right_is_scalar or right_spec is None or right_spec.rank == 0:
                r_expr = right_var
            elif right_spec.rank == 1 and right_spec.shape[0] == length:
                r_expr = f"{right_var}[_i]"
            elif right_spec.rank == 1 and right_spec.shape[0] == 1:
                r_expr = f"{right_var}[0]"
            else:
                r_expr = f"{right_var}[_i]"

            lines.append(f"{indent}    {target_var}[_i] = {l_expr} {op_str} {r_expr}")

        elif len(out_shape) == 2:
            r, c = out_shape
            lines.append(f"{indent}for _i in range({r}):")
            lines.append(f"{indent}    for _j in range({c}):")

            l_expr = left_var if left_is_scalar else self._index_2d_broadcast(left_var, left_spec, r, c)
            r_expr = right_var if right_is_scalar else self._index_2d_broadcast(right_var, right_spec, r, c)
            lines.append(f"{indent}        {target_var}[_i][_j] = {l_expr} {op_str} {r_expr}")

        return lines

    def _index_2d_broadcast(self, var: str, spec: Optional[TensorSpec], r: int, c: int) -> str:
        """Helper for 2D broadcasting indices."""
        if spec is None or spec.rank == 0:
            return var
        if spec.rank == 1:
            # 1D broadcast across rows (length matches columns)
            if spec.shape[0] == c:
                return f"{var}[_j]"
            elif spec.shape[0] == 1:
                return f"{var}[0]"
            return f"{var}[0]"
        if spec.rank == 2:
            sr, sc = spec.shape
            i_idx = "_i" if sr == r else "0"
            j_idx = "_j" if sc == c else "0"
            return f"{var}[{i_idx}][{j_idx}]"
        return var

    def _lower_elementwise_unary(self, node: TorchFXNode, op_str: str, target_var: str, indent: str) -> List[str]:
        """Lower unary negation or abs."""
        lines = []
        inp_var = self._resolve_input(node.inputs[0])
        shape = node.shape or (1,)

        if len(shape) == 1:
            lines.append(f"{indent}for _i in range({shape[0]}):")
            if op_str == "abs":
                lines.append(f"{indent}    _val = {inp_var}[_i]")
                lines.append(f"{indent}    if _val < 0:")
                lines.append(f"{indent}        _val = -_val")
                lines.append(f"{indent}    {target_var}[_i] = _val")
            else:
                lines.append(f"{indent}    {target_var}[_i] = {op_str}{inp_var}[_i]")
        elif len(shape) == 2:
            r, c = shape
            lines.append(f"{indent}for _i in range({r}):")
            lines.append(f"{indent}    for _j in range({c}):")
            if op_str == "abs":
                lines.append(f"{indent}        _val = {inp_var}[_i][_j]")
                lines.append(f"{indent}        if _val < 0:")
                lines.append(f"{indent}            _val = -_val")
                lines.append(f"{indent}        {target_var}[_i][_j] = _val")
            else:
                lines.append(f"{indent}        {target_var}[_i][_j] = {op_str}{inp_var}[_i][_j]")
        return lines

    def _sanitize_name(self, name: str) -> str:
        clean = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
        if clean and clean[0].isdigit():
            clean = "m_" + clean
        return clean
