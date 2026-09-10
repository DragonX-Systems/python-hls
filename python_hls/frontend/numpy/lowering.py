"""
Lowering engine for bounded NumPy kernels.

Transforms high-level NumPy operations (elementwise arithmetic, reductions,
vector dot product, matrix multiplication, and simple transforms) into
bounded loops with explicit memory accesses suitable for HLS synthesis.
"""

import ast
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from .spec import ArraySpec, normalize_dtype, SUPPORTED_DTYPES
from .diagnostics import (
    NumPyShapeError,
    NumPyDTypeError,
    NumPyUnsupportedOperationError,
)

# Supported NumPy function names (mapped from np.<name> or bare <name>)
SUPPORTED_ELEMENTWISE_BINARY = {
    "add": "+",
    "subtract": "-",
    "multiply": "*",
    "floor_divide": "//",
    "bitwise_and": "&",
    "bitwise_or": "|",
    "bitwise_xor": "^",
}

SUPPORTED_UNARY = {
    "negative": "-",
    "abs": "abs",
    "absolute": "abs",
}


class BroadcastingHelper:
    """Helper for evaluating and verifying bounded NumPy broadcasting rules."""

    @staticmethod
    def broadcast_shapes(
        s1: Tuple[int, ...],
        s2: Tuple[int, ...],
        op_name: str = "operation"
    ) -> Tuple[int, ...]:
        """
        Compute broadcast output shape for two shapes, or raise NumPyShapeError.
        Supports scalars (), identical shapes, and 1D/2D row/col broadcasting.
        """
        # Scalar with array
        if len(s1) == 0:
            return s2
        if len(s2) == 0:
            return s1

        # Identical shapes
        if s1 == s2:
            return s1

        # Check standard NumPy broadcasting backwards from trailing dimensions
        out_dims = []
        len1, len2 = len(s1), len(s2)
        max_len = max(len1, len2)

        for i in range(1, max_len + 1):
            dim1 = s1[-i] if i <= len1 else 1
            dim2 = s2[-i] if i <= len2 else 1

            if dim1 == dim2:
                out_dims.insert(0, dim1)
            elif dim1 == 1:
                out_dims.insert(0, dim2)
            elif dim2 == 1:
                out_dims.insert(0, dim1)
            else:
                raise NumPyShapeError(
                    f"Cannot broadcast shapes {s1} and {s2} in {op_name}: "
                    f"dimension mismatch at axis {-i} ({dim1} vs {dim2})."
                )

        return tuple(out_dims)


class NumPyLowering:
    """
    Lowering pass that transforms bounded NumPy AST into synthesizable loops.
    """

    def __init__(self, input_specs: Dict[str, ArraySpec]):
        self.var_specs: Dict[str, ArraySpec] = dict(input_specs)
        self.temp_var_id = 0

    def _next_temp(self, prefix: str = "_t") -> str:
        name = f"{prefix}_{self.temp_var_id}"
        self.temp_var_id += 1
        return name

    def lower_function(self, func_node: ast.FunctionDef) -> ast.FunctionDef:
        """Lower all NumPy operations in a function definition into synthesizable loops."""
        new_body: List[ast.stmt] = []

        # Prepend memory size annotations for input array variables
        for arg in func_node.args.args:
            if arg.arg in self.var_specs:
                spec = self.var_specs[arg.arg]
                if spec.shape:
                    new_body.append(
                        ast.Assign(
                            targets=[ast.Name(id=f"{arg.arg}_memory_size", ctx=ast.Store())],
                            value=ast.Constant(value=spec.size_bytes)
                        )
                    )

        for stmt in func_node.body:
            lowered_stmts = self._lower_statement(stmt)
            new_body.extend(lowered_stmts)

        # Build modified FunctionDef, stripping NumPy decorators
        cleaned_decorators = []
        for dec in func_node.decorator_list:
            # Drop numpy_kernel decorator from the lowered AST
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "numpy_kernel":
                continue
            if isinstance(dec, ast.Name) and dec.id == "numpy_kernel":
                continue
            cleaned_decorators.append(dec)

        lowered_func = ast.FunctionDef(
            name=func_node.name,
            args=func_node.args,
            body=new_body,
            decorator_list=cleaned_decorators,
            returns=None,
            type_comment=func_node.type_comment,
        )
        ast.fix_missing_locations(lowered_func)
        return lowered_func

    def _lower_statement(self, stmt: ast.stmt) -> List[ast.stmt]:
        """Lower a single statement."""
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                raise NumPyUnsupportedOperationError("Only single-variable assignments (x = ...) are supported.")
            target_name = stmt.targets[0].id
            return self._lower_assignment(target_name, stmt.value)

        elif isinstance(stmt, ast.Return):
            if stmt.value is None:
                return [stmt]
            # If returning an expression directly (e.g. `return a + b`), lower it to a temp variable first
            if not isinstance(stmt.value, ast.Name):
                ret_var = self._next_temp("_ret")
                assign_stmts = self._lower_assignment(ret_var, stmt.value)
                return assign_stmts + [ast.Return(value=ast.Name(id=ret_var, ctx=ast.Load()))]
            return [stmt]

        elif isinstance(stmt, ast.Expr):
            # Evaluate expression statements if any
            return []

        elif isinstance(stmt, (ast.For, ast.While, ast.If)):
            # Pass through standard control flow
            return [stmt]

        raise NumPyUnsupportedOperationError(
            f"Unsupported statement construct in NumPy kernel: {type(stmt).__name__}"
        )

    def _lower_assignment(self, target: str, expr: ast.expr) -> List[ast.stmt]:
        """Lower an expression assigned to target variable."""
        # 1. Binary Operations: +, -, *, //, @
        if isinstance(expr, ast.BinOp):
            return self._lower_binop(target, expr)

        # 2. Unary Operations: -x
        elif isinstance(expr, ast.UnaryOp):
            return self._lower_unaryop(target, expr)

        # 3. Call Operations: np.add, np.sum, np.dot, np.matmul, np.maximum, etc.
        elif isinstance(expr, ast.Call):
            return self._lower_call(target, expr)

        # 4. Attribute access: x.T
        elif isinstance(expr, ast.Attribute):
            return self._lower_attribute(target, expr)

        # 5. Direct variable assignment: b = a
        elif isinstance(expr, ast.Name):
            source_name = expr.id
            if source_name in self.var_specs:
                self.var_specs[target] = self.var_specs[source_name]
            return [ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=expr)]

        # 6. Constant assignment
        elif isinstance(expr, ast.Constant):
            return [ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=expr)]

        raise NumPyUnsupportedOperationError(
            f"Unsupported expression in NumPy assignment: {ast.dump(expr)}"
        )

    def _lower_binop(self, target: str, expr: ast.BinOp) -> List[ast.stmt]:
        """Lower binary operators (+, -, *, //, @, &, |, ^)."""
        op_type = type(expr.op)

        # Matrix multiplication (@ operator)
        if op_type == ast.MatMult:
            return self._lower_matmul(target, expr.left, expr.right)

        # Elementwise binary arithmetic
        op_map = {
            ast.Add: ast.Add(),
            ast.Sub: ast.Sub(),
            ast.Mult: ast.Mult(),
            ast.FloorDiv: ast.FloorDiv(),
            ast.BitAnd: ast.BitAnd(),
            ast.BitOr: ast.BitOr(),
            ast.BitXor: ast.BitXor(),
        }
        if op_type not in op_map:
            raise NumPyUnsupportedOperationError(f"Unsupported binary operator: {op_type.__name__}")

        return self._lower_elementwise_binary(target, expr.left, expr.right, op_map[op_type])

    def _lower_unaryop(self, target: str, expr: ast.UnaryOp) -> List[ast.stmt]:
        """Lower unary operators (-x)."""
        if isinstance(expr.op, ast.USub):
            return self._lower_negation(target, expr.operand)
        raise NumPyUnsupportedOperationError(f"Unsupported unary operator: {type(expr.op).__name__}")

    def _lower_call(self, target: str, expr: ast.Call) -> List[ast.stmt]:
        """Lower function calls (np.sum, np.dot, np.matmul, np.maximum, np.zeros, etc.)."""
        func_name = self._get_call_name(expr)

        if func_name in ("add", "subtract", "multiply", "floor_divide"):
            if len(expr.args) < 2:
                raise NumPyShapeError(f"np.{func_name} requires 2 arguments, got {len(expr.args)}")
            op_map = {
                "add": ast.Add(),
                "subtract": ast.Sub(),
                "multiply": ast.Mult(),
                "floor_divide": ast.FloorDiv(),
            }
            return self._lower_elementwise_binary(target, expr.args[0], expr.args[1], op_map[func_name])

        elif func_name in ("matmul",):
            if len(expr.args) < 2:
                raise NumPyShapeError(f"np.matmul requires 2 arguments, got {len(expr.args)}")
            return self._lower_matmul(target, expr.args[0], expr.args[1])

        elif func_name in ("dot",):
            if len(expr.args) < 2:
                raise NumPyShapeError(f"np.dot requires 2 arguments, got {len(expr.args)}")
            return self._lower_dot(target, expr.args[0], expr.args[1])

        elif func_name in ("sum",):
            if len(expr.args) < 1:
                raise NumPyShapeError("np.sum requires at least 1 argument")
            axis = None
            if len(expr.args) >= 2 and isinstance(expr.args[1], ast.Constant):
                axis = expr.args[1].value
            for kw in expr.keywords:
                if kw.arg == "axis" and isinstance(kw.value, ast.Constant):
                    axis = kw.value.value
            return self._lower_sum(target, expr.args[0], axis=axis)

        elif func_name in ("mean",):
            if len(expr.args) < 1:
                raise NumPyShapeError("np.mean requires at least 1 argument")
            return self._lower_mean(target, expr.args[0])

        elif func_name in ("maximum", "minimum"):
            if len(expr.args) < 2:
                raise NumPyShapeError(f"np.{func_name} requires 2 arguments")
            return self._lower_max_min(target, expr.args[0], expr.args[1], is_max=(func_name == "maximum"))

        elif func_name in ("clip",):
            if len(expr.args) < 3:
                raise NumPyShapeError("np.clip requires 3 arguments: (a, a_min, a_max)")
            return self._lower_clip(target, expr.args[0], expr.args[1], expr.args[2])

        elif func_name in ("abs", "absolute"):
            if len(expr.args) < 1:
                raise NumPyShapeError("np.abs requires 1 argument")
            return self._lower_abs(target, expr.args[0])

        elif func_name in ("transpose",):
            if len(expr.args) < 1:
                raise NumPyShapeError("np.transpose requires 1 argument")
            return self._lower_transpose(target, expr.args[0])

        elif func_name in ("reshape",):
            if len(expr.args) < 2:
                raise NumPyShapeError("np.reshape requires 2 arguments: (a, newshape)")
            new_shape = self._extract_shape_tuple(expr.args[1])
            return self._lower_reshape(target, expr.args[0], new_shape)

        elif func_name in ("zeros", "ones"):
            if len(expr.args) < 1:
                raise NumPyShapeError(f"np.{func_name} requires shape argument")
            shape = self._extract_shape_tuple(expr.args[0])
            val = 0 if func_name == "zeros" else 1
            return self._lower_constant_array(target, shape, val)

        raise NumPyUnsupportedOperationError(
            f"Unsupported NumPy function 'np.{func_name}'. "
            "Supported operations in bounded frontend: add, subtract, multiply, floor_divide, "
            "matmul, dot, sum, mean, maximum, minimum, clip, abs, transpose, reshape, zeros, ones."
        )

    def _lower_attribute(self, target: str, expr: ast.Attribute) -> List[ast.stmt]:
        """Lower attribute expressions like a.T."""
        if expr.attr == "T":
            return self._lower_transpose(target, expr.value)
        raise NumPyUnsupportedOperationError(f"Unsupported array attribute: '.{expr.attr}'")

    # -------------------------------------------------------------------------
    # Core Lowering Implementations
    # -------------------------------------------------------------------------

    def _lower_elementwise_binary(
        self,
        target: str,
        left: ast.expr,
        right: ast.expr,
        op: ast.operator
    ) -> List[ast.stmt]:
        """Lower elementwise binary operations with broadcasting support."""
        s1, is_arr1 = self._get_expr_shape(left)
        s2, is_arr2 = self._get_expr_shape(right)

        out_shape = BroadcastingHelper.broadcast_shapes(s1, s2, "elementwise binary operation")
        dtype = self._infer_common_dtype(left, right)
        self.var_specs[target] = ArraySpec(shape=out_shape, dtype=dtype)

        stmts = []
        stmts.extend(self._create_array_allocation(target, out_shape, 0))

        if len(out_shape) == 1:
            size = out_shape[0]
            loop_var = self._next_temp("_i")

            # Left operand indexing
            left_elem = self._index_expr(left, loop_var, s1)
            right_elem = self._index_expr(right, loop_var, s2)

            loop_body = [
                ast.Assign(
                    targets=[ast.Subscript(
                        value=ast.Name(id=target, ctx=ast.Load()),
                        slice=ast.Name(id=loop_var, ctx=ast.Load()),
                        ctx=ast.Store()
                    )],
                    value=ast.BinOp(left=left_elem, op=op, right=right_elem)
                )
            ]
            loop = ast.For(
                target=ast.Name(id=loop_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=size)], keywords=[]),
                body=loop_body,
                orelse=[]
            )
            stmts.append(loop)

        elif len(out_shape) == 2:
            m, n = out_shape
            i_var = self._next_temp("_i")
            j_var = self._next_temp("_j")

            left_elem = self._index_expr_2d(left, i_var, j_var, s1)
            right_elem = self._index_expr_2d(right, i_var, j_var, s2)

            inner_body = [
                ast.Assign(
                    targets=[ast.Subscript(
                        value=ast.Subscript(
                            value=ast.Name(id=target, ctx=ast.Load()),
                            slice=ast.Name(id=i_var, ctx=ast.Load()),
                            ctx=ast.Load()
                        ),
                        slice=ast.Name(id=j_var, ctx=ast.Load()),
                        ctx=ast.Store()
                    )],
                    value=ast.BinOp(left=left_elem, op=op, right=right_elem)
                )
            ]
            inner_loop = ast.For(
                target=ast.Name(id=j_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=inner_body,
                orelse=[]
            )
            outer_loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                body=[inner_loop],
                orelse=[]
            )
            stmts.append(outer_loop)
        else:
            raise NumPyShapeError(f"Elementwise operations currently support up to 2D arrays, got {len(out_shape)}D")

        return stmts

    def _lower_matmul(self, target: str, left: ast.expr, right: ast.expr) -> List[ast.stmt]:
        """Lower 2D matrix multiplication (A @ B)."""
        s1, _ = self._get_expr_shape(left)
        s2, _ = self._get_expr_shape(right)

        if len(s1) != 2 or len(s2) != 2:
            raise NumPyShapeError(
                f"Matrix multiplication (@) requires 2D matrices, got shapes {s1} and {s2}"
            )

        m, k1 = s1
        k2, n = s2
        if k1 != k2:
            raise NumPyShapeError(
                f"Cannot perform matmul between shapes {s1} and {s2}: "
                f"inner dimensions ({k1} and {k2}) must match."
            )

        out_shape = (m, n)
        dtype = self._infer_common_dtype(left, right)
        self.var_specs[target] = ArraySpec(shape=out_shape, dtype=dtype)

        stmts = []
        stmts.extend(self._create_array_allocation(target, out_shape, 0))

        i_var = self._next_temp("_i")
        j_var = self._next_temp("_j")
        k_var = self._next_temp("_k")
        sum_var = self._next_temp("_acc")

        # Inner accumulation loop: sum_var = sum_var + a[i][k] * b[k][j]
        a_elem = ast.Subscript(
            value=ast.Subscript(value=left, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
            slice=ast.Name(id=k_var, ctx=ast.Load()),
            ctx=ast.Load()
        )
        b_elem = ast.Subscript(
            value=ast.Subscript(value=right, slice=ast.Name(id=k_var, ctx=ast.Load()), ctx=ast.Load()),
            slice=ast.Name(id=j_var, ctx=ast.Load()),
            ctx=ast.Load()
        )

        k_loop = ast.For(
            target=ast.Name(id=k_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=k1)], keywords=[]),
            body=[
                ast.Assign(
                    targets=[ast.Name(id=sum_var, ctx=ast.Store())],
                    value=ast.BinOp(
                        left=ast.Name(id=sum_var, ctx=ast.Load()),
                        op=ast.Add(),
                        right=ast.BinOp(left=a_elem, op=ast.Mult(), right=b_elem)
                    )
                )
            ],
            orelse=[]
        )

        j_loop = ast.For(
            target=ast.Name(id=j_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
            body=[
                ast.Assign(targets=[ast.Name(id=sum_var, ctx=ast.Store())], value=ast.Constant(value=0)),
                k_loop,
                ast.Assign(
                    targets=[ast.Subscript(
                        value=ast.Subscript(
                            value=ast.Name(id=target, ctx=ast.Load()),
                            slice=ast.Name(id=i_var, ctx=ast.Load()),
                            ctx=ast.Load()
                        ),
                        slice=ast.Name(id=j_var, ctx=ast.Load()),
                        ctx=ast.Store()
                    )],
                    value=ast.Name(id=sum_var, ctx=ast.Load())
                )
            ],
            orelse=[]
        )

        i_loop = ast.For(
            target=ast.Name(id=i_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
            body=[j_loop],
            orelse=[]
        )

        stmts.append(i_loop)
        return stmts

    def _lower_dot(self, target: str, left: ast.expr, right: ast.expr) -> List[ast.stmt]:
        """Lower 1D vector dot product (or 2D matmul)."""
        s1, _ = self._get_expr_shape(left)
        s2, _ = self._get_expr_shape(right)

        if len(s1) == 1 and len(s2) == 1:
            if s1[0] != s2[0]:
                raise NumPyShapeError(
                    f"Dimension mismatch in dot product: {s1} and {s2} cannot be contracted."
                )
            n = s1[0]
            i_var = self._next_temp("_i")

            # Scalar result
            stmts = [ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=ast.Constant(value=0))]

            a_elem = ast.Subscript(value=left, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            b_elem = ast.Subscript(value=right, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())

            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=target, ctx=ast.Store())],
                        value=ast.BinOp(
                            left=ast.Name(id=target, ctx=ast.Load()),
                            op=ast.Add(),
                            right=ast.BinOp(left=a_elem, op=ast.Mult(), right=b_elem)
                        )
                    )
                ],
                orelse=[]
            )
            stmts.append(loop)
            return stmts

        elif len(s1) == 2 and len(s2) == 2:
            return self._lower_matmul(target, left, right)
        else:
            raise NumPyShapeError(f"np.dot supports 1D or 2D arrays, got shapes {s1} and {s2}")

    def _lower_sum(self, target: str, operand: ast.expr, axis: Optional[int] = None) -> List[ast.stmt]:
        """Lower np.sum reduction."""
        shape, _ = self._get_expr_shape(operand)

        if axis is not None:
            raise NumPyUnsupportedOperationError("Axis-specific reductions are not yet supported in early DSE; full reductions supported.")

        stmts = [ast.Assign(targets=[ast.Name(id=target, ctx=ast.Store())], value=ast.Constant(value=0))]

        if len(shape) == 1:
            n = shape[0]
            i_var = self._next_temp("_i")
            elem = ast.Subscript(value=operand, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())

            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=target, ctx=ast.Store())],
                        value=ast.BinOp(left=ast.Name(id=target, ctx=ast.Load()), op=ast.Add(), right=elem)
                    )
                ],
                orelse=[]
            )
            stmts.append(loop)

        elif len(shape) == 2:
            m, n = shape
            i_var = self._next_temp("_i")
            j_var = self._next_temp("_j")
            elem = ast.Subscript(
                value=ast.Subscript(value=operand, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
                slice=ast.Name(id=j_var, ctx=ast.Load()),
                ctx=ast.Load()
            )

            inner_loop = ast.For(
                target=ast.Name(id=j_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=target, ctx=ast.Store())],
                        value=ast.BinOp(left=ast.Name(id=target, ctx=ast.Load()), op=ast.Add(), right=elem)
                    )
                ],
                orelse=[]
            )
            outer_loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                body=[inner_loop],
                orelse=[]
            )
            stmts.append(outer_loop)
        else:
            raise NumPyShapeError(f"Reduction supports up to 2D arrays, got {len(shape)}D")

        return stmts

    def _lower_mean(self, target: str, operand: ast.expr) -> List[ast.stmt]:
        """Lower np.mean reduction (sum / total_elements)."""
        shape, _ = self._get_expr_shape(operand)
        total_elements = 1
        for d in shape:
            total_elements *= d

        sum_temp = self._next_temp("_sum")
        sum_stmts = self._lower_sum(sum_temp, operand)

        div_stmt = ast.Assign(
            targets=[ast.Name(id=target, ctx=ast.Store())],
            value=ast.BinOp(
                left=ast.Name(id=sum_temp, ctx=ast.Load()),
                op=ast.FloorDiv(),
                right=ast.Constant(value=total_elements)
            )
        )
        return sum_stmts + [div_stmt]

    def _lower_max_min(self, target: str, a: ast.expr, b: ast.expr, is_max: bool = True) -> List[ast.stmt]:
        """Lower elementwise maximum / minimum (e.g. ReLU activation: np.maximum(x, 0))."""
        s1, _ = self._get_expr_shape(a)
        s2, _ = self._get_expr_shape(b)

        out_shape = BroadcastingHelper.broadcast_shapes(s1, s2, "maximum/minimum")
        dtype = self._infer_common_dtype(a, b)
        self.var_specs[target] = ArraySpec(shape=out_shape, dtype=dtype)

        stmts = []
        stmts.extend(self._create_array_allocation(target, out_shape, 0))

        cmp_op = ast.Gt() if is_max else ast.Lt()

        if len(out_shape) == 1:
            n = out_shape[0]
            i_var = self._next_temp("_i")
            elem_a = self._index_expr(a, i_var, s1)
            elem_b = self._index_expr(b, i_var, s2)

            cond = ast.Compare(left=elem_a, ops=[cmp_op], comparators=[elem_b])
            body = [
                ast.Assign(
                    targets=[ast.Subscript(
                        value=ast.Name(id=target, ctx=ast.Load()),
                        slice=ast.Name(id=i_var, ctx=ast.Load()),
                        ctx=ast.Store()
                    )],
                    value=ast.IfExp(test=cond, body=elem_a, orelse=elem_b)
                )
            ]
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=body,
                orelse=[]
            )
            stmts.append(loop)

        elif len(out_shape) == 2:
            m, n = out_shape
            i_var = self._next_temp("_i")
            j_var = self._next_temp("_j")
            elem_a = self._index_expr_2d(a, i_var, j_var, s1)
            elem_b = self._index_expr_2d(b, i_var, j_var, s2)

            cond = ast.Compare(left=elem_a, ops=[cmp_op], comparators=[elem_b])
            inner_body = [
                ast.Assign(
                    targets=[ast.Subscript(
                        value=ast.Subscript(
                            value=ast.Name(id=target, ctx=ast.Load()),
                            slice=ast.Name(id=i_var, ctx=ast.Load()),
                            ctx=ast.Load()
                        ),
                        slice=ast.Name(id=j_var, ctx=ast.Load()),
                        ctx=ast.Store()
                    )],
                    value=ast.IfExp(test=cond, body=elem_a, orelse=elem_b)
                )
            ]
            inner_loop = ast.For(
                target=ast.Name(id=j_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=inner_body,
                orelse=[]
            )
            outer_loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                body=[inner_loop],
                orelse=[]
            )
            stmts.append(outer_loop)
        else:
            raise NumPyShapeError(f"Max/Min supports up to 2D arrays, got {len(out_shape)}D")

        return stmts

    def _lower_clip(self, target: str, a: ast.expr, a_min: ast.expr, a_max: ast.expr) -> List[ast.stmt]:
        """Lower np.clip(a, a_min, a_max)."""
        temp1 = self._next_temp("_clip_max")
        stmts1 = self._lower_max_min(temp1, a, a_min, is_max=True)
        stmts2 = self._lower_max_min(target, ast.Name(id=temp1, ctx=ast.Load()), a_max, is_max=False)
        return stmts1 + stmts2

    def _lower_abs(self, target: str, operand: ast.expr) -> List[ast.stmt]:
        """Lower np.abs(a) / abs(a)."""
        zero_const = ast.Constant(value=0)
        neg_temp = self._next_temp("_neg")
        neg_stmts = self._lower_negation(neg_temp, operand)
        max_stmts = self._lower_max_min(target, operand, ast.Name(id=neg_temp, ctx=ast.Load()), is_max=True)
        return neg_stmts + max_stmts

    def _lower_negation(self, target: str, operand: ast.expr) -> List[ast.stmt]:
        """Lower elementwise negation (-x)."""
        shape, _ = self._get_expr_shape(operand)
        dtype = self._infer_dtype(operand)
        self.var_specs[target] = ArraySpec(shape=shape, dtype=dtype)

        stmts = []
        stmts.extend(self._create_array_allocation(target, shape, 0))

        if len(shape) == 1:
            n = shape[0]
            i_var = self._next_temp("_i")
            elem = ast.Subscript(value=operand, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load())
            loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(
                            value=ast.Name(id=target, ctx=ast.Load()),
                            slice=ast.Name(id=i_var, ctx=ast.Load()),
                            ctx=ast.Store()
                        )],
                        value=ast.UnaryOp(op=ast.USub(), operand=elem)
                    )
                ],
                orelse=[]
            )
            stmts.append(loop)

        elif len(shape) == 2:
            m, n = shape
            i_var = self._next_temp("_i")
            j_var = self._next_temp("_j")
            elem = ast.Subscript(
                value=ast.Subscript(value=operand, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
                slice=ast.Name(id=j_var, ctx=ast.Load()),
                ctx=ast.Load()
            )
            inner_loop = ast.For(
                target=ast.Name(id=j_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                body=[
                    ast.Assign(
                        targets=[ast.Subscript(
                            value=ast.Subscript(
                                value=ast.Name(id=target, ctx=ast.Load()),
                                slice=ast.Name(id=i_var, ctx=ast.Load()),
                                ctx=ast.Load()
                            ),
                            slice=ast.Name(id=j_var, ctx=ast.Load()),
                            ctx=ast.Store()
                        )],
                        value=ast.UnaryOp(op=ast.USub(), operand=elem)
                    )
                ],
                orelse=[]
            )
            outer_loop = ast.For(
                target=ast.Name(id=i_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                body=[inner_loop],
                orelse=[]
            )
            stmts.append(outer_loop)
        else:
            raise NumPyShapeError(f"Negation supports up to 2D arrays, got {len(shape)}D")

        return stmts

    def _lower_transpose(self, target: str, operand: ast.expr) -> List[ast.stmt]:
        """Lower 2D matrix transpose (A.T or np.transpose(A))."""
        shape, _ = self._get_expr_shape(operand)
        if len(shape) != 2:
            raise NumPyShapeError(f"Transpose (.T) requires a 2D matrix, got shape {shape}")

        m, n = shape
        out_shape = (n, m)
        dtype = self._infer_dtype(operand)
        self.var_specs[target] = ArraySpec(shape=out_shape, dtype=dtype)

        stmts = []
        stmts.extend(self._create_array_allocation(target, out_shape, 0))

        i_var = self._next_temp("_i")
        j_var = self._next_temp("_j")

        # target[j][i] = operand[i][j]
        src_elem = ast.Subscript(
            value=ast.Subscript(value=operand, slice=ast.Name(id=i_var, ctx=ast.Load()), ctx=ast.Load()),
            slice=ast.Name(id=j_var, ctx=ast.Load()),
            ctx=ast.Load()
        )

        inner_loop = ast.For(
            target=ast.Name(id=j_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
            body=[
                ast.Assign(
                    targets=[ast.Subscript(
                        value=ast.Subscript(
                            value=ast.Name(id=target, ctx=ast.Load()),
                            slice=ast.Name(id=j_var, ctx=ast.Load()),
                            ctx=ast.Load()
                        ),
                        slice=ast.Name(id=i_var, ctx=ast.Load()),
                        ctx=ast.Store()
                    )],
                    value=src_elem
                )
            ],
            orelse=[]
        )

        outer_loop = ast.For(
            target=ast.Name(id=i_var, ctx=ast.Store()),
            iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
            body=[inner_loop],
            orelse=[]
        )

        stmts.append(outer_loop)
        return stmts

    def _lower_reshape(self, target: str, operand: ast.expr, new_shape: Tuple[int, ...]) -> List[ast.stmt]:
        """Lower reshape operation between compatible shapes."""
        old_shape, _ = self._get_expr_shape(operand)

        old_prod = 1
        for d in old_shape:
            old_prod *= d
        new_prod = 1
        for d in new_shape:
            new_prod *= d

        if old_prod != new_prod:
            raise NumPyShapeError(
                f"Cannot reshape array of size {old_prod} (shape {old_shape}) into shape {new_shape} (size {new_prod})"
            )

        dtype = self._infer_dtype(operand)
        self.var_specs[target] = ArraySpec(shape=new_shape, dtype=dtype)

        stmts = []
        stmts.extend(self._create_array_allocation(target, new_shape, 0))

        # Flattened transfer loop: target flat index = operand flat index
        idx_var = self._next_temp("_flat_idx")
        total = old_prod

        # Simple 1D to 2D or 2D to 1D mapping
        if len(old_shape) == 1 and len(new_shape) == 2:
            m, n = new_shape
            i_expr = ast.BinOp(left=ast.Name(id=idx_var, ctx=ast.Load()), op=ast.FloorDiv(), right=ast.Constant(value=n))
            j_expr = ast.BinOp(left=ast.Name(id=idx_var, ctx=ast.Load()), op=ast.Mod(), right=ast.Constant(value=n))

            src_elem = ast.Subscript(value=operand, slice=ast.Name(id=idx_var, ctx=ast.Load()), ctx=ast.Load())
            dst_target = ast.Subscript(
                value=ast.Subscript(value=ast.Name(id=target, ctx=ast.Load()), slice=i_expr, ctx=ast.Load()),
                slice=j_expr,
                ctx=ast.Store()
            )

            loop = ast.For(
                target=ast.Name(id=idx_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=total)], keywords=[]),
                body=[ast.Assign(targets=[dst_target], value=src_elem)],
                orelse=[]
            )
            stmts.append(loop)

        elif len(old_shape) == 2 and len(new_shape) == 1:
            m, n = old_shape
            i_expr = ast.BinOp(left=ast.Name(id=idx_var, ctx=ast.Load()), op=ast.FloorDiv(), right=ast.Constant(value=n))
            j_expr = ast.BinOp(left=ast.Name(id=idx_var, ctx=ast.Load()), op=ast.Mod(), right=ast.Constant(value=n))

            src_elem = ast.Subscript(
                value=ast.Subscript(value=operand, slice=i_expr, ctx=ast.Load()),
                slice=j_expr,
                ctx=ast.Load()
            )
            dst_target = ast.Subscript(value=ast.Name(id=target, ctx=ast.Load()), slice=ast.Name(id=idx_var, ctx=ast.Load()), ctx=ast.Store())

            loop = ast.For(
                target=ast.Name(id=idx_var, ctx=ast.Store()),
                iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=total)], keywords=[]),
                body=[ast.Assign(targets=[dst_target], value=src_elem)],
                orelse=[]
            )
            stmts.append(loop)
        else:
            raise NumPyShapeError(f"Reshape between {old_shape} and {new_shape} not supported in initial subset")

        return stmts

    def _lower_constant_array(self, target: str, shape: Tuple[int, ...], fill_val: int) -> List[ast.stmt]:
        """Lower np.zeros(shape) / np.ones(shape)."""
        self.var_specs[target] = ArraySpec(shape=shape, dtype="int32")
        return self._create_array_allocation(target, shape, fill_val)

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------

    def _get_call_name(self, call_node: ast.Call) -> str:
        """Extract canonical function name from Call node."""
        if isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        raise NumPyUnsupportedOperationError(f"Unsupported call expression: {ast.dump(call_node.func)}")

    def _extract_shape_tuple(self, node: ast.expr) -> Tuple[int, ...]:
        """Extract constant integer shape tuple from AST node."""
        if isinstance(node, (ast.Tuple, ast.List)):
            dims = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, int):
                    dims.append(elt.value)
                else:
                    raise NumPyShapeError(f"Shape elements must be constant integers, got {ast.dump(elt)}")
            return tuple(dims)
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            return (node.value,)
        raise NumPyShapeError(f"Expected shape tuple or integer, got {ast.dump(node)}")

    def _get_expr_shape(self, expr: ast.expr) -> Tuple[Tuple[int, ...], bool]:
        """
        Return (shape, is_array).
        For scalars, returns ((), False).
        """
        if isinstance(expr, ast.Name) and expr.id in self.var_specs:
            return self.var_specs[expr.id].shape, True

        if isinstance(expr, ast.Constant):
            return (), False

        # Nested binary operation shape inference
        if isinstance(expr, ast.BinOp):
            s1, _ = self._get_expr_shape(expr.left)
            s2, _ = self._get_expr_shape(expr.right)
            return BroadcastingHelper.broadcast_shapes(s1, s2), True

        # Default fallback
        return (), False

    def _infer_dtype(self, expr: ast.expr) -> str:
        if isinstance(expr, ast.Name) and expr.id in self.var_specs:
            return self.var_specs[expr.id].dtype
        return "int32"

    def _infer_common_dtype(self, e1: ast.expr, e2: ast.expr) -> str:
        dt1 = self._infer_dtype(e1)
        dt2 = self._infer_dtype(e2)
        if "float" in dt1 or "float" in dt2:
            return "float32"
        return "int32"

    def _create_array_allocation(self, name: str, shape: Tuple[int, ...], fill_val: int = 0) -> List[ast.stmt]:
        """Generate list comprehension allocation in AST."""
        dtype = self.var_specs[name].dtype if name in self.var_specs else "int32"
        element_bytes = max(1, SUPPORTED_DTYPES.get(dtype, 32) // 8)
        tot_bytes = 1
        for s in shape:
            tot_bytes *= s
        tot_bytes *= element_bytes
        mem_stmt = ast.Assign(
            targets=[ast.Name(id=f"{name}_memory_size", ctx=ast.Store())],
            value=ast.Constant(value=tot_bytes)
        )

        if len(shape) == 1:
            # name = [fill_val] * N
            alloc = ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=ast.BinOp(
                    left=ast.List(elts=[ast.Constant(value=fill_val)], ctx=ast.Load()),
                    op=ast.Mult(),
                    right=ast.Constant(value=shape[0])
                )
            )
            return [mem_stmt, alloc]
        elif len(shape) == 2:
            m, n = shape
            # name = [[fill_val for _ in range(N)] for _ in range(M)]
            inner_comp = ast.ListComp(
                elt=ast.Constant(value=fill_val),
                generators=[ast.comprehension(
                    target=ast.Name(id="_", ctx=ast.Store()),
                    iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=n)], keywords=[]),
                    ifs=[],
                    is_async=0
                )]
            )
            outer_comp = ast.ListComp(
                elt=inner_comp,
                generators=[ast.comprehension(
                    target=ast.Name(id="_", ctx=ast.Store()),
                    iter=ast.Call(func=ast.Name(id="range", ctx=ast.Load()), args=[ast.Constant(value=m)], keywords=[]),
                    ifs=[],
                    is_async=0
                )]
            )
            return [mem_stmt, ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=outer_comp)]
        else:
            raise NumPyShapeError(f"Array allocation currently supports up to 2D, got {len(shape)}D")

    def _index_expr(self, expr: ast.expr, idx_var: str, shape: Tuple[int, ...]) -> ast.expr:
        """Index into 1D array or return scalar for broadcasting, handling nested expressions recursively."""
        if len(shape) == 0:  # Scalar
            return expr
        if isinstance(expr, ast.BinOp):
            s_left, _ = self._get_expr_shape(expr.left)
            s_right, _ = self._get_expr_shape(expr.right)
            return ast.BinOp(
                left=self._index_expr(expr.left, idx_var, s_left),
                op=expr.op,
                right=self._index_expr(expr.right, idx_var, s_right),
            )
        elif isinstance(expr, ast.UnaryOp):
            s_op, _ = self._get_expr_shape(expr.operand)
            return ast.UnaryOp(
                op=expr.op,
                operand=self._index_expr(expr.operand, idx_var, s_op),
            )
        return ast.Subscript(
            value=expr,
            slice=ast.Name(id=idx_var, ctx=ast.Load()),
            ctx=ast.Load()
        )

    def _index_expr_2d(self, expr: ast.expr, i_var: str, j_var: str, shape: Tuple[int, ...]) -> ast.expr:
        """Index into 2D array or return broadcast element, handling nested expressions recursively."""
        if len(shape) == 0:  # Scalar
            return expr
        if isinstance(expr, ast.BinOp):
            s_left, _ = self._get_expr_shape(expr.left)
            s_right, _ = self._get_expr_shape(expr.right)
            return ast.BinOp(
                left=self._index_expr_2d(expr.left, i_var, j_var, s_left),
                op=expr.op,
                right=self._index_expr_2d(expr.right, i_var, j_var, s_right),
            )
        elif isinstance(expr, ast.UnaryOp):
            s_op, _ = self._get_expr_shape(expr.operand)
            return ast.UnaryOp(
                op=expr.op,
                operand=self._index_expr_2d(expr.operand, i_var, j_var, s_op),
            )
        elif len(shape) == 1:  # 1D row broadcast
            return ast.Subscript(
                value=expr,
                slice=ast.Name(id=j_var, ctx=ast.Load()),
                ctx=ast.Load()
            )
        elif len(shape) == 2:
            m, n = shape
            i_idx = ast.Name(id=i_var, ctx=ast.Load()) if m > 1 else ast.Constant(value=0)
            j_idx = ast.Name(id=j_var, ctx=ast.Load()) if n > 1 else ast.Constant(value=0)
            return ast.Subscript(
                value=ast.Subscript(value=expr, slice=i_idx, ctx=ast.Load()),
                slice=j_idx,
                ctx=ast.Load()
            )
        return expr
