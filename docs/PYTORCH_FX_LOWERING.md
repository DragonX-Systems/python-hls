# PyTorch FX Qualified Kernel Lowering in Python-HLS

## Overview

Python-HLS provides a qualified frontend and lowering path from **PyTorch FX** computational graphs directly into synthesizable Python AST and hardware RTL netlists (Verilog and VHDL).

Rather than attempting arbitrary, unconstrained PyTorch model synthesis (which often involves dynamic shapes, unquantized complex operations, or non-deterministic control flow), Python-HLS establishes a **deliberately bounded and qualified operator subset**. Models within this subset are statically analyzed, mapped to bounded loop nests with deterministic buffer footprints, scheduled, and compiled to hardware RTL.

---

## Qualified Operator Subset

The following PyTorch modules, functions, and operations are supported for direct hardware lowering:

| Category | Supported Operations | Generated Hardware Realization |
| :--- | :--- | :--- |
| **Linear / Dense** | `nn.Linear`, `torch.matmul`, `torch.bmm`, `torch.mm`, `F.linear` | Multiply-accumulate nested loops, MAC pipeline, or parallel DSP blocks |
| **Elementwise Binary** | `+` (`add`), `-` (`sub`), `*` (`mul`), `/` or `//` (`div`, `truediv`, `floordiv`) | ALU / Adder / Multiplier / Divider functional units |
| **Elementwise Unary** | `-x` (`neg`), `abs(x)` | Complement / Negator / Absolute value hardware |
| **Activations** | `nn.ReLU`, `torch.relu`, `torch.clamp`, `nn.Hardtanh` | Threshold comparators and multiplexers |
| **Reductions** | `torch.sum`, `torch.mean` | Serial accumulator loop or reduction tree |

> [!NOTE]
> Unsupported operations (such as dynamic recurrent loops, non-deterministic operations, transcendental functions like `sin`, `exp` without approximation ROMs, or unsupported library calls) immediately raise deterministic diagnostics during graph validation.

---

## Static Shape & Dimension Requirements

1. **Compile-Time Constant Dimensions**:
   - All tensor dimensions must be strictly positive integers known at compile time.
   - Dynamic batch sizes or variable sequence lengths (e.g. `None` or `-1`) are rejected with `PyTorchShapeError`.
2. **Supported Tensor Ranks**:
   - **Rank 0**: Scalar registers / wires.
   - **Rank 1**: 1D vectors (`(N,)`), mapped to 1D addressable BRAM or registers.
   - **Rank 2**: 2D matrices (`(R, C)`), mapped to 2D array row-major memories.
   - **Rank > 2**: Rejected with `PyTorchShapeError`.
3. **Broadcasting Conventions**:
   - Scalar-to-vector (`() + (N,)`) and scalar-to-matrix (`() + (R, C)`).
   - Vector-to-matrix (`(C,)` broadcasted across rows of `(R, C)`).
   - Outer dimension matching (`(R, 1)` broadcasted across columns of `(R, C)`).

---

## Data Types & Quantization

The following canonical dtypes are supported and normalized:

- **Signed Integers**: `int8`, `int16`, `int32`, `int64`
- **Unsigned Integers**: `uint8`
- **Floating Point**: `float32`, `float64`
- **Quantized Types**: `qint8`, `quint8`
- **Booleans**: `bool`

Unsupported types (e.g. `complex64`, `bfloat16` without target support) raise `PyTorchDTypeError`.

---

## Memory Interface & Weight Conventions

1. **Buffer Sizing Annotations**:
   The lowering engine generates explicit `{buffer}_memory_size = <bytes>` annotations directly in the lowered Python code. Python-HLS's `AGU_32bit` (Address Generation Unit) and `MemoryController` use these byte sizes to allocate hardware BRAM/URAM blocks and registers.
2. **Weights & Parameters**:
   - **Embedded Constants (`embed_weights=True`)**:
     Model parameters (`nn.Linear.weight`, `nn.Linear.bias`) are embedded as constant lookup arrays in the generated synthesizable Python function. In synthesized RTL, these are mapped to internal ROM or initialization registers.
   - **Parameter Interface Ports (`embed_weights=False`)**:
     Weights and biases are declared as top-level interface array ports. This allows external host memories or AXI master controllers to update weights without re-synthesizing the hardware netlist.
3. **Destination Memory**:
   Functions producing non-scalar outputs write directly into a destination buffer (`out`), following standard C/HLS memory calling conventions.

---

## Deterministic Diagnostics

When a model violates synthesizability constraints, Python-HLS raises actionable, deterministic exceptions:

- `PyTorchShapeError`: Raised when shapes are dynamic, have rank > 2, or when tensor dimensions do not align for matrix multiplication / broadcasting.
- `PyTorchDTypeError`: Raised when an unsupported data type is encountered.
- `PyTorchUnsupportedOperationError`: Raised when a PyTorch FX node uses an operator outside the qualified subset.

---

## Python API Usage

### 1. Lowering to Synthesizable Python AST

```python
import torch
import torch.nn as nn
from python_hls.frontend.torch_fx import lower_torch_model

class TinyMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(4, 2)
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.fc(x))

model = TinyMLP().eval()
example_input = torch.randn(4)

# Lower model into synthesizable Python source code
lowered_code, fx_graph = lower_torch_model(model, [example_input], embed_weights=True)
print(lowered_code)
```

Generated synthesizable Python:
```python
def tinymlp(x, out):
    """Synthesized from PyTorch model: TinyMLP"""
    x_memory_size = 16
    fc_weight = [[-0.3949, -0.1499, -0.0144, -0.1214], [-0.4167, -0.4926, -0.3032, 0.4849]]
    fc_weight_memory_size = 32
    fc_bias = [-0.1785, -0.2714]
    fc_bias_memory_size = 8
    out_memory_size = 8

    _fc_0 = [0] * 2
    for _i in range(2):
        _acc = fc_bias[_i]
        for _j in range(4):
            _acc += fc_weight[_i][_j] * x[_j]
        _fc_0[_i] = _acc

    for _i in range(2):
        _val = _fc_0[_i]
        if _val < 0:
            _val = 0
        out[_i] = _val

    return out
```

### 2. End-to-End Hardware Compilation

```python
from python_hls.frontend.torch_fx import compile_torch_model
# Or using the top-level HLS object:
# from python_hls import HLS; hls = HLS(); netlist, graph = hls.compile_torch(...)

netlist, graph = compile_torch_model(
    model,
    example_inputs=[example_input],
    target="verilog",
    output_file="tinymlp.v",
    opt_level=2,
    tech_node=45,
)

print(f"Generated RTL modules: {list(netlist.modules.keys())}")
```

---

## CLI Usage

Python-HLS provides a dedicated `compile-torch` command:

```bash
# Compile a PyTorch model with static shape 4 to Verilog RTL
python -m python_hls.cli compile-torch examples/pytorch_linear_relu.py --input-shapes "4" -o linear_relu.v

# Multi-input model with 8-element vectors
python -m python_hls.cli compile-torch examples/pytorch_elementwise.py --input-shapes "8;8" -o elem.v

# Pass parameter ports instead of embedding weights as constants
python -m python_hls.cli compile-torch examples/pytorch_mlp.py --input-shapes "4" --no-embed-weights -o mlp.v
```

---

## Regression Testing & Verification

Run the test suite covering shape diagnostics, dtype validation, unsupported operator detection, numerical equivalence, and RTL synthesis:

```bash
pytest tests/test_torch_fx.py -v
```
