# Bounded NumPy Frontend and Lowering Path

Python-HLS provides a bounded NumPy frontend that enables fixed-shape, hardware-friendly NumPy kernels to directly enter the High-Level Synthesis compilation flow without rewriting them into manual loop nests or C++ models.

---

## 1. Motivation

NumPy is the standard language for specifying array computations, linear algebra, digital signal processing (DSP), and quantitative pipelines in Python.

Traditionally, compiling NumPy algorithms to FPGA/ASIC hardware required:
1. Translating the Python/NumPy code by hand into C/C++ or SystemC.
2. Managing memory pointers and loops manually.
3. Keeping the reference NumPy algorithm and the C++ HLS model synchronized.

The Python-HLS bounded NumPy frontend allows you to write natural NumPy array expressions, validate them in Python, and lower them deterministically into synthesizable hardware loops and memory interfaces.

---

## 2. Specification & Contracts

Hardware synthesis requires deterministic memory bounds, predictable bit widths, and static scheduling. The bounded NumPy frontend enforces these contracts via the `@numpy_kernel` decorator or explicit `ArraySpec` contracts.

### Hardware-Bounded Array Contract (`ArraySpec`)

Every array operand in a hardware kernel must have:
- **Fixed Shape**: Tuple of positive integers (e.g., `(16,)`, `(4, 4)`). Dynamic dimensions (e.g., `None` or `-1`) are prohibited.
- **Hardware Dtype**: Statically typed data format mapped to discrete hardware bit widths:
  - `int8`, `int16`, `int32`, `int64` (signed integers)
  - `uint8`, `uint16`, `uint32`, `uint64` (unsigned integers)
  - `float32`, `float64` (IEEE floating point)
  - `bool` (1-bit boolean)
- **Contiguous Layout**: C-order row-major memory buffers (`layout="C"`).

```python
from python_hls import numpy_kernel

@numpy_kernel(
    shapes={"a": (16,), "b": (16,)},
    dtypes={"a": "int32", "b": "int32"},
)
def vector_add(a, b):
    return a + b
```

---

## 3. Supported Operation Subset

The frontend lowers the following qualified NumPy operations into hardware-synthesizable IR and Verilog:

| Category | Operators / Functions | Hardware Mapping |
|---|---|---|
| **Elementwise Arithmetic** | `+`, `-`, `*`, `//`, `np.add`, `np.subtract`, `np.multiply`, `np.floor_divide` | Pipelined arithmetic functional units (`ADD`, `SUB`, `MUL`, `DIV`) |
| **Bitwise Operations** | `&`, `\|`, `^` | Hardware logic bitwise gates (`BIT_AND`, `BIT_OR`, `BIT_XOR`) |
| **Unary Operations** | `-x`, `np.abs(x)` | Two's complement negation, absolute value comparison |
| **Linear Algebra** | `A @ B`, `np.matmul(A, B)` | Multi-level nested loops with MAC (multiply-accumulate) datapaths |
| **Dot Product** | `np.dot(a, b)` | 1D vector contraction with hardware accumulator |
| **Reductions** | `np.sum(a)`, `np.mean(a)` | Tree or loop accumulator with divider for mean |
| **Activations & Non-linearities** | `np.maximum(0, x)` (ReLU), `np.minimum(a, b)`, `np.clip(x, min, max)` | Hardware comparators and multiplexers |
| **Simple Transforms** | `A.T`, `np.transpose(A)`, `np.reshape(A, newshape)` | Static memory address generation and index remapping |
| **Constant Buffers** | `np.zeros(shape)`, `np.ones(shape)` | Hardware ROM / scratchpad constant initializations |

---

## 4. Bounded Broadcasting Rules

The frontend implements standard NumPy broadcasting rules evaluated statically at compile time:
- **Scalars with Arrays**: Scalars broadcast across 1D and 2D arrays (e.g., `x + 10` or `np.maximum(0, x)`).
- **Matching Shapes**: Compatible dimensions operate element-by-element.
- **Row/Column Broadcasting**: Dimensions of size `1` broadcast across matching dimensions (e.g., `(3, 1)` and `(1, 4)` yield `(3, 4)`).
- **Static Diagnostics**: Any incompatible dimension pairing immediately raises a deterministic `NumPyShapeError` before scheduling.

---

## 5. Compilation Usage

### Method A: Compile Python Callable Directly

```python
import numpy as np
from python_hls import HLS, numpy_kernel

@numpy_kernel(
    shapes={"a": (4, 4), "b": (4, 4)},
    dtypes={"a": "int32", "b": "int32"}
)
def matmul_kernel(a, b):
    return a @ b

hls = HLS(optimization_level=1, tech_node=45)
netlist, logs = hls.compile_numpy(matmul_kernel, output_file="matmul_4x4.v")
```

### Method B: Compile Python Source File

Files containing `import numpy as np` and kernels decorated with `@numpy_kernel` can be compiled using standard `HLS.compile()`:

```python
from python_hls import HLS

hls = HLS(optimization_level=1, tech_node=45)
netlist, logs = hls.compile("examples/numpy_vector_add.py", target="verilog")
```

### Method C: Software Emulation & Bit-Accurate Verification

You can verify lowered kernels directly against reference NumPy in pure software:

```python
from python_hls import NumPyFrontend

frontend = NumPyFrontend()
exec_fn = frontend.compile_to_callable(matmul_kernel)

# Run bit-accurate verification
a = np.ones((4, 4), dtype=np.int32)
b = np.eye(4, dtype=np.int32)
assert exec_fn(a.tolist(), b.tolist()) == (a @ b).tolist()
```

---

## 6. Deterministic Diagnostics

When a kernel violates hardware constraints, the frontend produces explicit, deterministic errors:

- **`NumPyShapeError`**: Dimension mismatch in matmul, dot product, or broadcasting.
  ```text
  NumPyShapeError: Cannot perform matmul between shapes (2, 3) and (4, 2): inner dimensions (3 and 4) must match.
  ```
- **`NumPyDTypeError`**: Non-synthesizable dtype (e.g., `complex128`, `object`).
  ```text
  NumPyDTypeError: Unsupported dtype 'complex128'. Supported dtypes for hardware synthesis are: bool, float32, float64, int16, int32, int64, int8, uint16, uint32, uint64, uint8.
  ```
- **`NumPyUnsupportedOperationError`**: Operation outside the bounded subset (e.g., `np.fft`, arbitrary C-extensions).
  ```text
  NumPyUnsupportedOperationError: Unsupported NumPy function 'np.fft'.
  ```

---

## 7. Examples

Three complete examples are available in the [`examples/`](../examples/) directory:
- [`examples/numpy_vector_add.py`](../examples/numpy_vector_add.py): 16-element vector addition.
- [`examples/numpy_matmul.py`](../examples/numpy_matmul.py): 4x4 matrix multiplication with nested loops and hardware memory ports.
- [`examples/numpy_relu_reduction.py`](../examples/numpy_relu_reduction.py): ReLU activation pipeline with sum reduction.
