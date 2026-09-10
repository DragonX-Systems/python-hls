"""
Lowering pass that transforms a JaxprGraph into synthesizable loop nests and memory operations.
"""

import ast
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .diagnostics import JAXShapeError, JAXUnsupportedPrimitiveError
from .spec import SUPPORTED_DTYPES
from .tracing import JaxprGraph, JaxprNode, JaxprVariable


class JaxprLowering:
    """Lowers a JaxprGraph into a synthesizable ast.FunctionDef."""

    def __init__(self, graph: JaxprGraph):
        self.graph = graph
        self.var_map: Dict[str, JaxprVariable] = dict(graph.variables)
        self.temp_id = 0

    def _next_temp(self, prefix: str = "_t") -> str:
        name = f"{prefix}_{self.temp_id}"
        self.temp_id += 1
        return name

    def lower(self) -> ast.FunctionDef:
        """Lower the entire JaxprGraph into an ast.FunctionDef."""
        body: List[ast.stmt] = []

        # 1. Prepend input memory sizes
        for inp in self.graph.inputs:
            if inp.shape:
                body.append(
                    ast.Assign(
                        targets=[ast.Name(id=f"{inp.name}_memory_size", ctx=ast.Store())],
                        value=ast.Constant(value=inp.size_bytes),
                    )
                )

        # 2. Lower each equation in sequence
        for node in self.graph.nodes:
            node_stmts = self._lower_node(node)
            body.extend(node_stmts)

        # 3. Return statement
        if self.graph.outputs:
            out_var = self.graph.outputs[0]
            body.append(ast.Return(value=ast.Name(id=out_var.name, ctx=ast.Load())))
        else:
            body.append(ast.Return(value=ast.Constant(value=0)))

        # Build args
        func_args = [ast.arg(arg=inp.name) for inp in self.graph.inputs]
        func_def = ast.FunctionDef(
            name=self.graph.name,
            args=ast.arguments(
                posonlyargs=[],
                args=func_args,
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=body,
            decorator_list=[],
            returns=None,
        )
        ast.fix_missing_locations(func_def)
        return func_def

    def _lower_node(self, node: JaxprNode) -> List[ast.stmt]:
        """Dispatch equation lowering by primitive."""
        p = node.primitive

        if p in ("add", "sub", "mul", "div", "floor_divide"):
            return self._lower_binary_elementwise(node)
        elif p == "neg":
            return self._lower_neg(node)
        elif p == "abs":
            return self._lower_abs(node)
        elif p in ("max", "min"):
            return self._lower_max_min(node)
        elif p == "clamp":
            return self._lower_clamp(node)
        elif p == "dot_general":
            return self._lower_dot_general(node)
        elif p == "reduce_sum":
            return self._lower_reduce_sum(node)
        elif p == "transpose":
            return self._lower_transpose(node)
        elif p in ("reshape", "broadcast_in_dim"):
            return self._lower_reshape_or_broadcast(node)
        elif p == "convert_element_type":
            return self._lower_convert_element_type(node)

        raise JAXUnsupportedPrimitiveError(
            f"Cannot lower JAX primitive '{p}' into hardware loop nests."
        )

    def _resolve_atom(self, atom_name: str) -> Tuple[ast.expr, Tuple[int, ...]]:
        """Resolve operand name to AST expression and shape."""
        if atom_name in self.var_map:
            v = self.var_map[atom_name]
            if v.is_literal:
                val = v.literal_value if v.literal_value is not None else 0
                if hasattr(val, "item"):
                    val = val.item()
                elif hasattr(val, "tolist"):
                    val = val.tolist()
                return ast.Constant(value=val), v.shape
            return ast.Name(id=v.name, ctx=ast.Load()), v.shape

        # Literal constant
        if atom_name.startswith("lit_"):
            val_str = atom_name.replace("lit_", "").replace("m", "-")
            try:
                val = int(val_str)
            except ValueError:
                try:
                    val = float(val_str)
                except ValueError:
                    val = 0
            return ast.Constant(value=val), ()

        return ast.Name(id=atom_name, ctx=ast.Load()), ()

    def _create_allocation(self, name: str, shape: Tuple[int, ...], fill_val: int = 0) -> List[ast.stmt]:
        """Emit memory size annotation and buffer allocation."""
        if not shape:
            return [ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=ast.Constant(value=fill_val))]

        dtype = self.var_map[name].dtype if name in self.var_map else "int32"
        element_bytes = max(1, SUPPORTED_DTYPES.get(dtype, 32) // 8)
        tot_bytes = 1
        for s in shape:
            tot_bytes *= s
        tot_bytes *= element_bytes

        mem_stmt = ast.Assign(
            targets=[ast.Name(id=f"{name}_memory_size", ctx=ast.Store())],
            value=ast.Constant(value=tot_bytes),
        )

        if len(shape) == 1:
            alloc = ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.BinOp(
                    left=ast.List(elts=[ast.Constant(value=fill_val)], ctx=ast.Load()),
                    op=ast.Mult(),
                    right=ast.Constant(value=shape[0]),
                ),
            )
            return [mem_stmt, alloc]
        elif len(shape) == 2:
            m, n = shape
            inner_comp = ast.ListComp(
                elt=ast.Constant(value=fill_val),
                generators=[ast.comprehension(
                    target=ast.Name(id="_", ctx=ast.Store()),
                    iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                    ifs=[],
                    is_async=0,
                )],
            )
            outer_comp = ast.ListComp(
                elt=inner_comp,
                generators=[ast.comprehension(
                    target=ast.Name(id="_", ctx=ast.Store()),
                    iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                    ifs=[],
                    is_async=0,
                )],
            )
            return [mem_stmt, ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=outer_comp)]
        else:
            raise JAXShapeError(f"Hardware buffer allocation currently supports up to 2D arrays, got {len(shape)}D")

    def _lower_binary_elementwise(self, node: JaxprNode) -> List[ast.stmt]:
        """Lower elementwise add, sub, mul, div."""
        out_name = node.outputs[0]
        out_shape = node.shape
        in1_expr, s1 = self._resolve_atom(node.inputs[0])
        in2_expr, s2 = self._resolve_atom(node.inputs[1])

        op_map = {
            "add": ast.Add(),
            "sub": ast.Sub(),
            "mul": ast.Mult(),
            "div": ast.FloorDiv(),
            "floor_divide": ast.FloorDiv(),
        }
        op = op_map[node.primitive]

        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))

        if len(out_shape) == 0:
            # Scalar operation
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=out_name, ctx=ast.Store())],
                    value=ast.BinOp(left=in1_expr, op=op, right=in2_expr),
                )
            )
        elif len(out_shape) == 1:
            loop_i = self._next_temp("_i")
            e1 = in1_expr if len(s1) == 0 else ast.Subscript(value=in1_expr, slice=ast.Name(id=loop_i, ctx=ast.Load()), ctx=ast.Load())
            e2 = in2_expr if len(s2) == 0 else ast.Subscript(value=in2_expr, slice=ast.Name(id=loop_i, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=loop_i, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=out_shape[0])], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=loop_i, ctx=ast.Load()), ctx=ast.Store())],
                        value=ast.BinOp(left=e1, op=op, right=e2),
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        elif len(out_shape) == 2:
            m, n = out_shape
            i_var = self._next_temp("_i")
            j_var = self._next_temp("_j")
            e1 = self._index_2d(in1_expr, s1, i_var, j_var)
            e2 = self._index_2d(in2_expr, s2, i_var, j_var)
            inner_loop = ast.For(
                target=ast.Name(id=j_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[
                            ast.Subscript(
                                value=ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
                                slice=ast.Name(id=j_var, ctx=ast.Load()),
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.BinOp(left=e1, op=op, right=e2),
                    )
                ],
                orelse=[],
            )
            outer_loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                body=[inner_loop],
                orelse=[],
            )
            stmts.append(outer_loop)
        return stmts

    def _index_2d(self, expr: ast.expr, shape: Tuple[int, ...], i_var: str, j_var: str) -> ast.expr:
        if len(shape) == 0:
            return expr
        if len(shape) == 1:
            return ast.Subscript(value=expr, slice=ast.Name(id=j_var, ctx=ast.Load()), ctx=ast.Load())
        m, n = shape
        i_idx = ast.Name(id=i_var, ctx=ast.Load()) if m > 1 else ast.Constant(value=0)
        j_idx = ast.Name(id=j_var, ctx=ast.Load()) if n > 1 else ast.Constant(value=0)
        return ast.Subscript(
            value=ast.Subscript(value=expr, slice=i_idx, ctx=ast.Load()),
            slice=j_idx,
            ctx=ast.Load(),
        )

    def _lower_neg(self, node: JaxprNode) -> List[ast.stmt]:
        out_name = node.outputs[0]
        out_shape = node.shape
        in_expr, _ = self._resolve_atom(node.inputs[0])
        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))
        if len(out_shape) == 1:
            i_var = self._next_temp("_i")
            elem = ast.Subscript(value=in_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=out_shape[0])], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Store())],
                        value=ast.UnaryOp(op=ast.USub(), operand=elem),
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        return stmts

    def _lower_abs(self, node: JaxprNode) -> List[ast.stmt]:
        out_name = node.outputs[0]
        out_shape = node.shape
        in_expr, _ = self._resolve_atom(node.inputs[0])
        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))
        if len(out_shape) == 1:
            i_var = self._next_temp("_i")
            elem = ast.Subscript(value=in_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=out_shape[0])], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Store())],
                        value=ast.IfExp(
                            test=ast.Compare(left=elem, ops=[ast.GtE()], comparators=[ast.Constant(value=0)]),
                            body=elem,
                            orelse=ast.UnaryOp(op=ast.USub(), operand=elem),
                        ),
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        return stmts

    def _lower_max_min(self, node: JaxprNode) -> List[ast.stmt]:
        out_name = node.outputs[0]
        out_shape = node.shape
        in1_expr, s1 = self._resolve_atom(node.inputs[0])
        in2_expr, s2 = self._resolve_atom(node.inputs[1])
        is_max = node.primitive == "max"
        cmp_op = ast.Gt() if is_max else ast.Lt()

        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))

        if len(out_shape) == 1:
            i_var = self._next_temp("_i")
            e1 = in1_expr if len(s1) == 0 else ast.Subscript(value=in1_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            e2 = in2_expr if len(s2) == 0 else ast.Subscript(value=in2_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            val_expr = ast.IfExp(
                test=ast.Compare(left=e1, ops=[cmp_op], comparators=[e2]),
                body=e1,
                orelse=e2,
            )
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=out_shape[0])], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Store())],
                        value=val_expr,
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        return stmts

    def _lower_clamp(self, node: JaxprNode) -> List[ast.stmt]:
        out_name = node.outputs[0]
        out_shape = node.shape
        min_expr, _ = self._resolve_atom(node.inputs[0])
        x_expr, _ = self._resolve_atom(node.inputs[1])
        max_expr, _ = self._resolve_atom(node.inputs[2])

        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))

        if len(out_shape) == 1:
            i_var = self._next_temp("_i")
            elem = ast.Subscript(value=x_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            clamped_expr = ast.IfExp(
                test=ast.Compare(left=elem, ops=[ast.Lt()], comparators=[min_expr]),
                body=min_expr,
                orelse=ast.IfExp(
                    test=ast.Compare(left=elem, ops=[ast.Gt()], comparators=[max_expr]),
                    body=max_expr,
                    orelse=elem,
                ),
            )
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=out_shape[0])], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Store())],
                        value=clamped_expr,
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        return stmts

    def _lower_dot_general(self, node: JaxprNode) -> List[ast.stmt]:
        """Lower generalized dot / matmul / vector dot product."""
        out_name = node.outputs[0]
        out_shape = node.shape
        in1_expr, s1 = self._resolve_atom(node.inputs[0])
        in2_expr, s2 = self._resolve_atom(node.inputs[1])

        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape, fill_val=0))

        if len(s1) == 1 and len(s2) == 1:
            # 1D vector dot product
            n = s1[0]
            i_var = self._next_temp("_i")
            a_elem = ast.Subscript(value=in1_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            b_elem = ast.Subscript(value=in2_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=out_name, ctx=ast.Store())],
                        value=ast.BinOp(
                            left=ast.Name(id=out_name, ctx=ast.Load()),
                            op=ast.Add(),
                            right=ast.BinOp(left=a_elem, op=ast.Mult(), right=b_elem),
                        ),
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
            return stmts

        elif len(s1) == 2 and len(s2) == 2:
            # 2D matrix multiplication (M x K @ K x N)
            m, k1 = s1
            k2, n = s2
            i_var = self._next_temp("_i")
            j_var = self._next_temp("_j")
            k_var = self._next_temp("_k")
            acc_var = self._next_temp("_acc")

            a_elem = ast.Subscript(
                value=ast.Subscript(value=in1_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
                slice=ast.Name(id=k_var, ctx=ast.Load()),
                ctx=ast.Load(),
            )
            b_elem = ast.Subscript(
                value=ast.Subscript(value=in2_expr, slice=ast.Name(id=k_var, ctx=ast.Load()), ctx=ast.Load()),
                slice=ast.Name(id=j_var, ctx=ast.Load()),
                ctx=ast.Load(),
            )

            k_loop = ast.For(
                target=ast.Name(id=k_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=k1)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=acc_var, ctx=ast.Store())],
                        value=ast.BinOp(
                            left=ast.Name(id=acc_var, ctx=ast.Load()),
                            op=ast.Add(),
                            right=ast.BinOp(left=a_elem, op=ast.Mult(), right=b_elem),
                        ),
                    )
                ],
                orelse=[],
            )

            j_loop = ast.For(
                target=ast.Name(id=j_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(targets=[ast.Name(id=acc_var, ctx=ast.Store())], value=ast.Constant(value=0)),
                    k_loop,
                    ast.Assign(
                        targets=[
                            ast.Subscript(
                                value=ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
                                slice=ast.Name(id=j_var, ctx=ast.Load()),
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Name(id=acc_var, ctx=ast.Load()),
                    ),
                ],
                orelse=[],
            )

            i_loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                body=[j_loop],
                orelse=[],
            )
            stmts.append(i_loop)
            return stmts

        raise JAXShapeError(f"dot_general currently supports 1D dot products or 2D matrix multiplies, got {s1} and {s2}")

    def _lower_reduce_sum(self, node: JaxprNode) -> List[ast.stmt]:
        """Lower sum reduction."""
        out_name = node.outputs[0]
        out_shape = node.shape
        in_expr, s = self._resolve_atom(node.inputs[0])

        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape, fill_val=0))

        if len(s) == 1:
            n = s[0]
            i_var = self._next_temp("_i")
            elem = ast.Subscript(value=in_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=out_name, ctx=ast.Store())],
                        value=ast.BinOp(
                            left=ast.Name(id=out_name, ctx=ast.Load()),
                            op=ast.Add(),
                            right=elem,
                        ),
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        return stmts

    def _lower_transpose(self, node: JaxprNode) -> List[ast.stmt]:
        """Lower 2D matrix transpose."""
        out_name = node.outputs[0]
        out_shape = node.shape
        in_expr, s = self._resolve_atom(node.inputs[0])

        if len(s) != 2:
            raise JAXShapeError(f"Transpose currently supports 2D arrays, got shape {s}")

        m, n = s
        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))

        i_var = self._next_temp("_i")
        j_var = self._next_temp("_j")
        inner_loop = ast.For(
            target=ast.Name(id=j_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
            body=[
                ast.Assign(
                    targets=[
                        ast.Subscript(
                            value=ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=j_var, ctx=ast.Load()), ctx=ast.Load()),
                            slice=ast.Name(id=i_var, ctx=ast.Load()),
                            ctx=ast.Store(),
                        )
                    ],
                    value=ast.Subscript(
                        value=ast.Subscript(value=in_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
                        slice=ast.Name(id=j_var, ctx=ast.Load()),
                        ctx=ast.Load(),
                    ),
                )
            ],
            orelse=[],
        )
        outer_loop = ast.For(
            target=ast.Name(id=i_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
            body=[inner_loop],
            orelse=[],
        )
        stmts.append(outer_loop)
        return stmts

    def _lower_reshape_or_broadcast(self, node: JaxprNode) -> List[ast.stmt]:
        """Direct copy or identity remapping."""
        out_name = node.outputs[0]
        in_expr, _ = self._resolve_atom(node.inputs[0])
        return [ast.Assign(targets=[ast.Name(id=out_name, ctx=ast.Store())], value=in_expr)]

    def _lower_convert_element_type(self, node: JaxprNode) -> List[ast.stmt]:
        """Lower convert_element_type primitive (elementwise type conversion or copy)."""
        out_name = node.outputs[0]
        out_shape = node.shape
        in_expr, in_shape = self._resolve_atom(node.inputs[0])
        stmts = []
        stmts.extend(self._create_allocation(out_name, out_shape))
        if len(out_shape) == 0:
            stmts.append(
                ast.Assign(
                    targets=[ast.Name(id=out_name, ctx=ast.Store())],
                    value=in_expr,
                )
            )
        elif len(out_shape) == 1:
            i_var = self._next_temp("_i")
            elem = in_expr if len(in_shape) == 0 else ast.Subscript(value=in_expr, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=out_shape[0])], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(value=ast.Name(id=out_name, ctx=ast.Load()), slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Store())],
                        value=elem,
                    )
                ],
                orelse=[],
            )
            stmts.append(loop)
        return stmts


def lower_jaxpr_to_ast(graph: JaxprGraph) -> ast.FunctionDef:
    """Lower a JaxprGraph to an ast.FunctionDef."""
    lowering = JaxprLowering(graph)
    return lowering.lower()


def compile_jaxpr_to_callable(graph: JaxprGraph) -> Callable:
    """Compile JaxprGraph to an executable pure Python callable for bit-accurate validation."""
    func_ast = lower_jaxpr_to_ast(graph)
    module = ast.Module(body=[func_ast], type_ignores=[])
    ast.fix_missing_locations(module)
    code_obj = compile(module, filename=f"<jaxpr_{graph.name}>", mode="exec")
    exec_env: Dict[str, Any] = {}
    exec(code_obj, exec_env)
    return exec_env[graph.name]
