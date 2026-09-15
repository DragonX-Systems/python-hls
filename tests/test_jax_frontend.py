"""
Comprehensive test suite for the JAX Frontend and Jaxpr Lowering Path (Issue #1).
"""

import os
import tempfile
import unittest
import jax.lax as lax
import jax.numpy as jnp
import numpy as np

from python_hls import (
    HLS,
    jax_kernel,
    JAXArraySpec,
    JAXKernelSpec,
    JaxprGraph,
    JaxprNode,
    JaxprVariable,
    trace_jax_kernel,
    jaxpr_to_ir,
    JAXFrontendError,
    JAXShapeError,
    JAXDTypeError,
    JAXUnsupportedPrimitiveError,
)
from python_hls.frontend.jax.spec import (
    normalize_jax_dtype,
    resolve_jax_specs,
    infer_jax_spec,
    SUPPORTED_DTYPES,
)
from python_hls.frontend.jax.lowering import (
    lower_jaxpr_to_ast,
    compile_jaxpr_to_callable,
)
from python_hls.ir.ir_nodes import OperationType, DataType


class TestJAXSpec(unittest.TestCase):
    """Test JAXArraySpec and specification contract rules."""

    def test_valid_spec(self):
        spec = JAXArraySpec(shape=(16,), dtype="int32")
        self.assertEqual(spec.shape, (16,))
        self.assertEqual(spec.dtype, "int32")
        self.assertEqual(spec.ndim, 1)
        self.assertEqual(spec.total_elements, 16)
        self.assertEqual(spec.bit_width, 32)
        self.assertEqual(spec.size_bytes, 64)

    def test_2d_spec(self):
        spec = JAXArraySpec(shape=(4, 8), dtype="uint16", layout="C")
        self.assertEqual(spec.shape, (4, 8))
        self.assertEqual(spec.ndim, 2)
        self.assertEqual(spec.total_elements, 32)
        self.assertEqual(spec.bit_width, 16)
        self.assertEqual(spec.size_bytes, 64)

    def test_empty_shape_rejected(self):
        with self.assertRaises(JAXShapeError):
            JAXArraySpec(shape=(), dtype="int32")

    def test_non_positive_dim_rejected(self):
        with self.assertRaises(JAXShapeError):
            JAXArraySpec(shape=(4, 0), dtype="int32")
        with self.assertRaises(JAXShapeError):
            JAXArraySpec(shape=(-2, 4), dtype="int32")

    def test_dtype_normalization(self):
        self.assertEqual(normalize_jax_dtype("int"), "int32")
        self.assertEqual(normalize_jax_dtype("float"), "float32")
        self.assertEqual(normalize_jax_dtype("jnp.int16"), "int16")
        self.assertEqual(normalize_jax_dtype(jnp.int64), "int64")
        self.assertEqual(normalize_jax_dtype("uint8"), "uint8")
        self.assertEqual(normalize_jax_dtype("bool"), "bool")

    def test_unsupported_dtype_rejected(self):
        with self.assertRaises(JAXDTypeError):
            normalize_jax_dtype("complex128")
        with self.assertRaises(JAXDTypeError):
            normalize_jax_dtype("object")
        with self.assertRaises(JAXDTypeError):
            JAXArraySpec(shape=(4,), dtype="bfloat16")

    def test_unsupported_layout_rejected(self):
        with self.assertRaises(JAXShapeError):
            JAXArraySpec(shape=(4, 4), dtype="int32", layout="Fortran")

    def test_infer_spec_from_jax_array(self):
        arr = jnp.zeros((3, 7), dtype=jnp.int32)
        spec = infer_jax_spec(arr)
        self.assertEqual(spec.shape, (3, 7))
        self.assertEqual(spec.dtype, "int32")

    def test_infer_spec_from_nested_list(self):
        lst = [[1, 2], [3, 4], [5, 6]]
        spec = infer_jax_spec(lst)
        self.assertEqual(spec.shape, (3, 2))
        self.assertEqual(spec.dtype, "int32")

    def test_resolve_jax_specs_decorator(self):
        @jax_kernel(shapes={"x": (8,), "y": (8,)}, dtypes={"x": "int32", "y": "int32"})
        def add_fn(x, y):
            return x + y

        specs = resolve_jax_specs(add_fn)
        self.assertIn("x", specs)
        self.assertIn("y", specs)
        self.assertEqual(specs["x"].shape, (8,))
        self.assertEqual(specs["y"].shape, (8,))

    def test_resolve_jax_specs_missing_param_error(self):
        def unannotated(a, b):
            return a + b

        with self.assertRaises(JAXShapeError):
            resolve_jax_specs(unannotated, shapes={"a": (4,)})


class TestJAXDiagnostics(unittest.TestCase):
    """Test deterministic shape, dtype, and primitive diagnostics."""

    def test_unsupported_primitive_error(self):
        # Using a primitive not in the qualified hardware subset with strict_primitives=True
        @jax_kernel(shapes={"a": (4,)})
        def sin_fn(a):
            return jnp.sin(a)

        with self.assertRaises(JAXUnsupportedPrimitiveError):
            trace_jax_kernel(sin_fn, strict_primitives=True)

    def test_non_lowerable_primitive_flag(self):
        @jax_kernel(shapes={"a": (4,)})
        def sin_fn(a):
            return jnp.sin(a)

        graph = trace_jax_kernel(sin_fn, strict_primitives=False)
        self.assertFalse(graph.to_dict()["all_lowerable"])


class TestJAXTracingAndGraph(unittest.TestCase):
    """Test Jaxpr graph tracing, inspection, and serialization."""

    def test_trace_vector_add(self):
        @jax_kernel(shapes={"a": (8,), "b": (8,)}, dtypes={"a": "int32", "b": "int32"})
        def vec_add(a, b):
            return a + b

        graph = trace_jax_kernel(vec_add)
        self.assertEqual(graph.name, "vec_add")
        self.assertEqual(len(graph.inputs), 2)
        self.assertEqual(graph.inputs[0].name, "a")
        self.assertEqual(graph.inputs[0].shape, (8,))
        self.assertEqual(graph.inputs[1].name, "b")
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.nodes[0].primitive, "add")
        self.assertTrue(graph.nodes[0].lowerable)

        # Verify summary output
        summary = graph.summary()
        self.assertIn("JaxprGraph: vec_add", summary)
        self.assertIn("%a: int32[8]", summary)
        self.assertIn("[HW]", summary)

        # Verify dictionary export
        d = graph.to_dict()
        self.assertTrue(d["all_lowerable"])
        self.assertEqual(d["node_count"], 1)

    def test_trace_matmul(self):
        @jax_kernel(shapes={"a": (3, 4), "b": (4, 2)}, dtypes={"a": "int32", "b": "int32"})
        def matmul_fn(a, b):
            return jnp.matmul(a, b)

        graph = trace_jax_kernel(matmul_fn)
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.nodes[0].primitive, "dot_general")
        self.assertEqual(graph.nodes[0].shape, (3, 2))
        self.assertIn("dimension_numbers", graph.nodes[0].params)


class TestJAXIRMapping(unittest.TestCase):
    """Test direct mapping from JaxprGraph to Python-HLS IRFunction."""

    def test_ir_mapping_vector_add(self):
        @jax_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def add_fn(a, b):
            return a + b

        graph = trace_jax_kernel(add_fn)
        ir_func = jaxpr_to_ir(graph)

        self.assertEqual(ir_func.name, "add_fn")
        self.assertEqual(len(ir_func.parameters), 2)
        self.assertEqual(ir_func.parameters[0].name, "a")
        self.assertEqual(ir_func.parameters[0].data_type, DataType.ARRAY)
        self.assertEqual(ir_func.parameters[0].memory_size, 16)

        # Check instruction operations
        ops = [op for instr in ir_func.entry_block.instructions for op in instr.operations]
        self.assertTrue(any(op.op_type == OperationType.ADD for op in ops))
        self.assertTrue(any(op.op_type == OperationType.RETURN for op in ops))
        self.assertIsNotNone(ir_func.return_var)


class TestJAXLoweringSemantics(unittest.TestCase):
    """Validate numerical equivalence against the JAX reference for the qualified subset."""

    def test_elementwise_arithmetic(self):
        @jax_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def add_fn(a, b):
            return a + b

        @jax_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def sub_fn(a, b):
            return a - b

        @jax_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def mul_fn(a, b):
            return a * b

        @jax_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def div_fn(a, b):
            return lax.div(a, b)

        a = [12, 24, 36, 48]
        b = [2, 4, 6, 8]

        fn_add = compile_jaxpr_to_callable(trace_jax_kernel(add_fn))
        fn_sub = compile_jaxpr_to_callable(trace_jax_kernel(sub_fn))
        fn_mul = compile_jaxpr_to_callable(trace_jax_kernel(mul_fn))
        fn_div = compile_jaxpr_to_callable(trace_jax_kernel(div_fn))

        self.assertEqual(fn_add(a, b), (jnp.array(a) + jnp.array(b)).tolist())
        self.assertEqual(fn_sub(a, b), (jnp.array(a) - jnp.array(b)).tolist())
        self.assertEqual(fn_mul(a, b), (jnp.array(a) * jnp.array(b)).tolist())
        self.assertEqual(fn_div(a, b), (jnp.array(a) // jnp.array(b)).tolist())

    def test_neg_and_abs(self):
        @jax_kernel(shapes={"x": (4,)}, dtypes={"x": "int32"})
        def neg_fn(x):
            return -x

        @jax_kernel(shapes={"x": (4,)}, dtypes={"x": "int32"})
        def abs_fn(x):
            return jnp.abs(x)

        x = [-10, 5, -2, 0]
        fn_neg = compile_jaxpr_to_callable(trace_jax_kernel(neg_fn))
        fn_abs = compile_jaxpr_to_callable(trace_jax_kernel(abs_fn))

        self.assertEqual(fn_neg(x), (-jnp.array(x)).tolist())
        self.assertEqual(fn_abs(x), jnp.abs(jnp.array(x)).tolist())

    def test_scalar_broadcasting(self):
        @jax_kernel(shapes={"a": (4,)}, dtypes={"a": "int32"})
        def scalar_add(a):
            return a + 15

        a = [1, 2, 3, 4]
        fn = compile_jaxpr_to_callable(trace_jax_kernel(scalar_add))
        self.assertEqual(fn(a), (jnp.array(a) + 15).tolist())

    def test_matmul_2d(self):
        @jax_kernel(shapes={"a": (2, 3), "b": (3, 2)}, dtypes={"a": "int32", "b": "int32"})
        def matmul_fn(a, b):
            return jnp.matmul(a, b)

        a = [[1, 2, 3], [4, 5, 6]]
        b = [[7, 8], [9, 1], [2, 3]]
        fn = compile_jaxpr_to_callable(trace_jax_kernel(matmul_fn))
        ref = jnp.matmul(jnp.array(a), jnp.array(b)).tolist()
        self.assertEqual(fn(a, b), ref)

    def test_dot_product_1d(self):
        @jax_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def dot_fn(a, b):
            return jnp.dot(a, b)

        a = [1, 3, -5, 7]
        b = [4, -2, -1, 3]
        fn = compile_jaxpr_to_callable(trace_jax_kernel(dot_fn))
        ref = int(jnp.dot(jnp.array(a), jnp.array(b)))
        self.assertEqual(fn(a, b), ref)

    def test_sum_reduction(self):
        @jax_kernel(shapes={"x": (5,)}, dtypes={"x": "int32"})
        def sum_fn(x):
            return jnp.sum(x)

        x = [10, 20, 30, 40, 50]
        fn = compile_jaxpr_to_callable(trace_jax_kernel(sum_fn))
        self.assertEqual(fn(x), int(jnp.sum(jnp.array(x))))

    def test_relu_maximum(self):
        @jax_kernel(shapes={"x": (6,)}, dtypes={"x": "int32"})
        def relu_fn(x):
            return jnp.maximum(0, x)

        x = [-10, -1, 0, 1, 5, 20]
        fn = compile_jaxpr_to_callable(trace_jax_kernel(relu_fn))
        ref = jnp.maximum(0, jnp.array(x)).tolist()
        self.assertEqual(fn(x), ref)

    def test_clamp(self):
        @jax_kernel(shapes={"x": (5,)}, dtypes={"x": "int32"})
        def clamp_fn(x):
            return lax.clamp(-5, x, 10)

        @jax_kernel(shapes={"x": (5,)}, dtypes={"x": "int32"})
        def clip_fn(x):
            return jnp.clip(x, -5, 10)

        x = [-12, -5, 0, 8, 15]
        fn_clamp = compile_jaxpr_to_callable(trace_jax_kernel(clamp_fn))
        fn_clip = compile_jaxpr_to_callable(trace_jax_kernel(clip_fn))
        ref_clamp = lax.clamp(-5, jnp.array(x), 10).tolist()
        ref_clip = jnp.clip(jnp.array(x), -5, 10).tolist()
        self.assertEqual(fn_clamp(x), ref_clamp)
        self.assertEqual(fn_clip(x), ref_clip)

    def test_transpose_2d(self):
        @jax_kernel(shapes={"x": (2, 3)}, dtypes={"x": "int32"})
        def trans_fn(x):
            return jnp.transpose(x)

        x = [[1, 2, 3], [4, 5, 6]]
        fn = compile_jaxpr_to_callable(trace_jax_kernel(trans_fn))
        ref = jnp.transpose(jnp.array(x)).tolist()
        self.assertEqual(fn(x), ref)


class TestJAXHLSIntegration(unittest.TestCase):
    """Test end-to-end HLS compilation from JAX kernels to synthesizable Verilog."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compile_jax_callable(self):
        @jax_kernel(
            shapes={"a": (8,), "b": (8,)},
            dtypes={"a": "int32", "b": "int32"}
        )
        def vector_add_8(a, b):
            return a + b

        hls = HLS(optimization_level=1, tech_node=45)
        out_v = os.path.join(self.temp_dir, "vector_add_8.v")
        netlist, logs = hls.compile_jax(vector_add_8, output_file=out_v)

        self.assertIsNotNone(netlist)
        self.assertTrue(os.path.exists(out_v))
        with open(out_v, "r") as f:
            v_code = f.read()
        self.assertIn("module vector_add_8", v_code)
        self.assertIn("a_data_in", v_code)
        self.assertIn("b_data_in", v_code)

    def test_compile_jax_pipeline(self):
        @jax_kernel(shapes={"x": (4,)}, dtypes={"x": "int32"})
        def relu_sum(x):
            act = jnp.maximum(0, x)
            return jnp.sum(act)

        hls = HLS(optimization_level=1, tech_node=45)
        out_v = os.path.join(self.temp_dir, "relu_sum.v")
        netlist, logs = hls.compile_jax(relu_sum, output_file=out_v)

        self.assertIsNotNone(netlist)
        self.assertTrue(os.path.exists(out_v))
        with open(out_v, "r") as f:
            v_code = f.read()
        self.assertIn("module relu_sum", v_code)


if __name__ == "__main__":
    unittest.main()
