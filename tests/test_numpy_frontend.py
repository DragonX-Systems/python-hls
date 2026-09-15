"""
Comprehensive test suite for the Bounded NumPy Frontend and Lowering Path (Issue #4).
"""

import os
import tempfile
import unittest
import numpy as np

from python_hls import (
    HLS,
    numpy_kernel,
    ArraySpec,
    KernelSpec,
    NumPyFrontend,
    NumPyFrontendError,
    NumPyShapeError,
    NumPyDTypeError,
    NumPyUnsupportedOperationError,
)
from python_hls.frontend.numpy.spec import (
    normalize_dtype,
    resolve_kernel_specs,
    infer_spec_from_value,
    SUPPORTED_DTYPES,
)
from python_hls.frontend.numpy.lowering import (
    BroadcastingHelper,
    NumPyLowering,
)


class TestNumPySpec(unittest.TestCase):
    """Test shape/dtype specification and contract enforcement."""

    def test_valid_array_spec(self):
        spec = ArraySpec(shape=(4,), dtype="int32")
        self.assertEqual(spec.shape, (4,))
        self.assertEqual(spec.dtype, "int32")
        self.assertEqual(spec.ndim, 1)
        self.assertEqual(spec.total_elements, 4)
        self.assertEqual(spec.bit_width, 32)
        self.assertEqual(spec.size_bytes, 16)

    def test_2d_array_spec(self):
        spec = ArraySpec(shape=(3, 8), dtype="uint16", layout="C")
        self.assertEqual(spec.shape, (3, 8))
        self.assertEqual(spec.ndim, 2)
        self.assertEqual(spec.total_elements, 24)
        self.assertEqual(spec.bit_width, 16)
        self.assertEqual(spec.size_bytes, 48)

    def test_empty_shape_rejected(self):
        with self.assertRaises(NumPyShapeError):
            ArraySpec(shape=(), dtype="int32")

    def test_non_positive_dim_rejected(self):
        with self.assertRaises(NumPyShapeError):
            ArraySpec(shape=(4, 0), dtype="int32")
        with self.assertRaises(NumPyShapeError):
            ArraySpec(shape=(-1, 4), dtype="int32")

    def test_dtype_normalization(self):
        self.assertEqual(normalize_dtype("int"), "int32")
        self.assertEqual(normalize_dtype("float"), "float32")
        self.assertEqual(normalize_dtype("np.int16"), "int16")
        self.assertEqual(normalize_dtype(np.int64), "int64")
        self.assertEqual(normalize_dtype("uint8"), "uint8")
        self.assertEqual(normalize_dtype("bool"), "bool")

    def test_unsupported_dtype_rejected(self):
        with self.assertRaises(NumPyDTypeError):
            normalize_dtype("complex128")
        with self.assertRaises(NumPyDTypeError):
            normalize_dtype("object")
        with self.assertRaises(NumPyDTypeError):
            ArraySpec(shape=(4,), dtype="float128")

    def test_unsupported_layout_rejected(self):
        with self.assertRaises(NumPyShapeError):
            ArraySpec(shape=(4, 4), dtype="int32", layout="Fortran")

    def test_spec_inference_from_ndarray(self):
        arr = np.zeros((2, 5), dtype=np.int32)
        spec = infer_spec_from_value(arr)
        self.assertEqual(spec.shape, (2, 5))
        self.assertEqual(spec.dtype, "int32")

    def test_spec_inference_from_nested_list(self):
        lst = [[1, 2, 3], [4, 5, 6]]
        spec = infer_spec_from_value(lst)
        self.assertEqual(spec.shape, (2, 3))
        self.assertEqual(spec.dtype, "int32")

    def test_resolve_kernel_specs_from_decorator(self):
        @numpy_kernel(
            shapes={"x": (8,), "y": (8,)},
            dtypes={"x": "int32", "y": "int32"}
        )
        def kernel(x, y):
            return x + y

        specs = resolve_kernel_specs(kernel)
        self.assertIn("x", specs)
        self.assertIn("y", specs)
        self.assertEqual(specs["x"].shape, (8,))
        self.assertEqual(specs["y"].shape, (8,))

    def test_resolve_kernel_specs_missing_param_error(self):
        def unannotated(a, b):
            return a + b

        with self.assertRaises(NumPyShapeError):
            resolve_kernel_specs(unannotated, shapes={"a": (4,)})


class TestNumPyBroadcasting(unittest.TestCase):
    """Test broadcasting helper rules and diagnostics."""

    def test_identical_shapes(self):
        self.assertEqual(BroadcastingHelper.broadcast_shapes((4,), (4,)), (4,))
        self.assertEqual(BroadcastingHelper.broadcast_shapes((3, 5), (3, 5)), (3, 5))

    def test_scalar_broadcasting(self):
        self.assertEqual(BroadcastingHelper.broadcast_shapes((), (4,)), (4,))
        self.assertEqual(BroadcastingHelper.broadcast_shapes((2, 3), ()), (2, 3))

    def test_1d_with_2d_broadcasting(self):
        self.assertEqual(BroadcastingHelper.broadcast_shapes((3, 4), (4,)), (3, 4))
        self.assertEqual(BroadcastingHelper.broadcast_shapes((4,), (3, 4)), (3, 4))

    def test_1d_row_col_broadcasting(self):
        self.assertEqual(BroadcastingHelper.broadcast_shapes((3, 1), (1, 4)), (3, 4))

    def test_incompatible_broadcasting_raises(self):
        with self.assertRaises(NumPyShapeError):
            BroadcastingHelper.broadcast_shapes((4,), (5,))
        with self.assertRaises(NumPyShapeError):
            BroadcastingHelper.broadcast_shapes((3, 4), (3, 5))


class TestNumPyDiagnostics(unittest.TestCase):
    """Test deterministic shape, dtype, and unsupported-operation error diagnostics."""

    def setUp(self):
        self.frontend = NumPyFrontend()

    def test_shape_mismatch_elementwise(self):
        @numpy_kernel(shapes={"a": (4,), "b": (5,)})
        def bad_add(a, b):
            return a + b

        with self.assertRaises(NumPyShapeError) as cm:
            self.frontend.lower_callable(bad_add)
        self.assertIn("Cannot broadcast shapes (4,) and (5,)", str(cm.exception))

    def test_shape_mismatch_matmul(self):
        @numpy_kernel(shapes={"a": (2, 3), "b": (4, 2)})
        def bad_matmul(a, b):
            return a @ b

        with self.assertRaises(NumPyShapeError) as cm:
            self.frontend.lower_callable(bad_matmul)
        self.assertIn("inner dimensions (3 and 4) must match", str(cm.exception))

    def test_shape_mismatch_dot(self):
        @numpy_kernel(shapes={"a": (3,), "b": (4,)})
        def bad_dot(a, b):
            return np.dot(a, b)

        with self.assertRaises(NumPyShapeError) as cm:
            self.frontend.lower_callable(bad_dot)
        self.assertIn("Dimension mismatch in dot product", str(cm.exception))

    def test_unsupported_operation_error(self):
        @numpy_kernel(shapes={"a": (4,)})
        def bad_fft(a):
            return np.fft.fft(a)

        with self.assertRaises((NumPyUnsupportedOperationError, NumPyFrontendError)):
            self.frontend.lower_callable(bad_fft)


class TestNumPyLoweringSemantics(unittest.TestCase):
    """Validate numerical equivalence against the NumPy reference for the qualified subset."""

    def setUp(self):
        self.frontend = NumPyFrontend()

    def test_elementwise_arithmetic(self):
        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def add_kernel(a, b):
            return a + b

        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def sub_kernel(a, b):
            return a - b

        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def mul_kernel(a, b):
            return a * b

        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def div_kernel(a, b):
            return a // b

        a_np = np.array([12, 24, 36, 48], dtype=np.int32)
        b_np = np.array([2, 4, 6, 8], dtype=np.int32)

        fn_add = self.frontend.compile_to_callable(add_kernel)
        fn_sub = self.frontend.compile_to_callable(sub_kernel)
        fn_mul = self.frontend.compile_to_callable(mul_kernel)
        fn_div = self.frontend.compile_to_callable(div_kernel)

        self.assertEqual(fn_add(a_np.tolist(), b_np.tolist()), (a_np + b_np).tolist())
        self.assertEqual(fn_sub(a_np.tolist(), b_np.tolist()), (a_np - b_np).tolist())
        self.assertEqual(fn_mul(a_np.tolist(), b_np.tolist()), (a_np * b_np).tolist())
        self.assertEqual(fn_div(a_np.tolist(), b_np.tolist()), (a_np // b_np).tolist())

    def test_bitwise_operations(self):
        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def bitwise_kernel(a, b):
            return (a & b) | (a ^ b)

        a_np = np.array([0b1100, 0b1010, 0b1111, 0b0001], dtype=np.int32)
        b_np = np.array([0b1010, 0b1100, 0b0000, 0b0011], dtype=np.int32)

        fn = self.frontend.compile_to_callable(bitwise_kernel)
        ref = ((a_np & b_np) | (a_np ^ b_np)).tolist()
        self.assertEqual(fn(a_np.tolist(), b_np.tolist()), ref)

    def test_scalar_broadcasting(self):
        @numpy_kernel(shapes={"a": (4,)}, dtypes={"a": "int32"})
        def scalar_add_kernel(a):
            return a + 10

        @numpy_kernel(shapes={"a": (4,)}, dtypes={"a": "int32"})
        def scalar_mul_kernel(a):
            return 3 * a

        a_np = np.array([1, 2, 3, 4], dtype=np.int32)

        fn_add = self.frontend.compile_to_callable(scalar_add_kernel)
        fn_mul = self.frontend.compile_to_callable(scalar_mul_kernel)

        self.assertEqual(fn_add(a_np.tolist()), (a_np + 10).tolist())
        self.assertEqual(fn_mul(a_np.tolist()), (3 * a_np).tolist())

    def test_matmul_2d(self):
        @numpy_kernel(shapes={"a": (2, 3), "b": (3, 2)}, dtypes={"a": "int32", "b": "int32"})
        def matmul_kernel(a, b):
            return a @ b

        a_np = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32)
        b_np = np.array([[7, 8], [9, 1], [2, 3]], dtype=np.int32)

        fn = self.frontend.compile_to_callable(matmul_kernel)
        ref = (a_np @ b_np).tolist()
        self.assertEqual(fn(a_np.tolist(), b_np.tolist()), ref)

    def test_dot_product_1d(self):
        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def dot_kernel(a, b):
            return np.dot(a, b)

        a_np = np.array([1, 3, -5, 7], dtype=np.int32)
        b_np = np.array([4, -2, -1, 3], dtype=np.int32)

        fn = self.frontend.compile_to_callable(dot_kernel)
        ref = int(np.dot(a_np, b_np))
        self.assertEqual(fn(a_np.tolist(), b_np.tolist()), ref)

    def test_sum_reduction(self):
        @numpy_kernel(shapes={"a": (5,)}, dtypes={"a": "int32"})
        def sum_1d(a):
            return np.sum(a)

        a_np = np.array([10, 20, 30, 40, 50], dtype=np.int32)
        fn = self.frontend.compile_to_callable(sum_1d)
        self.assertEqual(fn(a_np.tolist()), int(np.sum(a_np)))

    def test_mean_reduction(self):
        @numpy_kernel(shapes={"a": (4,)}, dtypes={"a": "int32"})
        def mean_1d(a):
            return np.mean(a)

        a_np = np.array([10, 20, 30, 40], dtype=np.int32)
        fn = self.frontend.compile_to_callable(mean_1d)
        self.assertEqual(fn(a_np.tolist()), int(np.mean(a_np)))

    def test_relu_maximum(self):
        @numpy_kernel(shapes={"x": (6,)}, dtypes={"x": "int32"})
        def relu_kernel(x):
            return np.maximum(0, x)

        x_np = np.array([-10, -1, 0, 1, 5, 20], dtype=np.int32)
        fn = self.frontend.compile_to_callable(relu_kernel)
        ref = np.maximum(0, x_np).tolist()
        self.assertEqual(fn(x_np.tolist()), ref)

    def test_minimum(self):
        @numpy_kernel(shapes={"a": (4,), "b": (4,)}, dtypes={"a": "int32", "b": "int32"})
        def min_kernel(a, b):
            return np.minimum(a, b)

        a_np = np.array([10, 2, 8, 4], dtype=np.int32)
        b_np = np.array([5, 6, 7, 8], dtype=np.int32)
        fn = self.frontend.compile_to_callable(min_kernel)
        ref = np.minimum(a_np, b_np).tolist()
        self.assertEqual(fn(a_np.tolist(), b_np.tolist()), ref)

    def test_clip(self):
        @numpy_kernel(shapes={"x": (5,)}, dtypes={"x": "int32"})
        def clip_kernel(x):
            return np.clip(x, -5, 10)

        x_np = np.array([-12, -5, 0, 8, 15], dtype=np.int32)
        fn = self.frontend.compile_to_callable(clip_kernel)
        ref = np.clip(x_np, -5, 10).tolist()
        self.assertEqual(fn(x_np.tolist()), ref)

    def test_abs(self):
        @numpy_kernel(shapes={"x": (4,)}, dtypes={"x": "int32"})
        def abs_kernel(x):
            return np.abs(x)

        x_np = np.array([-10, 5, -2, 0], dtype=np.int32)
        fn = self.frontend.compile_to_callable(abs_kernel)
        ref = np.abs(x_np).tolist()
        self.assertEqual(fn(x_np.tolist()), ref)

    def test_transpose_2d(self):
        @numpy_kernel(shapes={"x": (2, 3)}, dtypes={"x": "int32"})
        def transpose_kernel(x):
            return x.T

        x_np = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32)
        fn = self.frontend.compile_to_callable(transpose_kernel)
        ref = x_np.T.tolist()
        self.assertEqual(fn(x_np.tolist()), ref)

    def test_constant_arrays(self):
        @numpy_kernel(shapes={"x": (4,)}, dtypes={"x": "int32"})
        def zeros_ones_kernel(x):
            z = np.zeros((4,))
            o = np.ones((4,))
            return x + z + o

        x_np = np.array([1, 2, 3, 4], dtype=np.int32)
        fn = self.frontend.compile_to_callable(zeros_ones_kernel)
        ref = (x_np + 1).tolist()
        self.assertEqual(fn(x_np.tolist()), ref)


class TestNumPyHLSIntegration(unittest.TestCase):
    """Test end-to-end HLS synthesis to Verilog for bounded NumPy kernels."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compile_numpy_callable(self):
        @numpy_kernel(
            shapes={"a": (8,), "b": (8,)},
            dtypes={"a": "int32", "b": "int32"}
        )
        def vector_add_8(a, b):
            return a + b

        hls = HLS(optimization_level=1, tech_node=45)
        out_v = os.path.join(self.temp_dir, "vector_add_8.v")
        netlist, logs = hls.compile_numpy(vector_add_8, output_file=out_v)

        self.assertIsNotNone(netlist)
        self.assertTrue(os.path.exists(out_v))
        with open(out_v, "r") as f:
            v_code = f.read()
        self.assertIn("module vector_add_8", v_code)
        self.assertIn("a_data_in", v_code)
        self.assertIn("b_data_in", v_code)

    def test_compile_numpy_file(self):
        py_path = os.path.join(self.temp_dir, "test_file_kernel.py")
        with open(py_path, "w") as f:
            f.write("""
import numpy as np
from python_hls import numpy_kernel

@numpy_kernel(shapes={"x": (4,)}, dtypes={"x": "int32"})
def relu_sum(x):
    act = np.maximum(0, x)
    return np.sum(act)
""")

        hls = HLS(optimization_level=1, tech_node=45)
        out_v = os.path.join(self.temp_dir, "relu_sum.v")
        netlist, logs = hls.compile(py_path, target="verilog", output_file=out_v)

        self.assertIsNotNone(netlist)
        self.assertTrue(os.path.exists(out_v))
        with open(out_v, "r") as f:
            v_code = f.read()
        self.assertIn("module relu_sum", v_code)


if __name__ == "__main__":
    unittest.main()
