"""
Comprehensive tests for PyTorch FX graph tracing, diagnostics, and qualified lowering.
"""

import pytest
import numpy as np

torch = pytest.importorskip("torch")
import torch.nn as nn
import torch.nn.functional as F

from python_hls.frontend.torch_fx import (
    trace_torch_model,
    lower_torch_model,
    compile_torch_model,
    TorchFXGraph,
    TorchFXLowering,
    PyTorchShapeError,
    PyTorchDTypeError,
    PyTorchUnsupportedOperationError,
)
from python_hls.hls import HLS


# =========================================================================
# Model Fixtures
# =========================================================================

class LinearReLUModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(4, 2)
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.fc(x))


class ElementwiseModel(nn.Module):
    def forward(self, a, b):
        c = a + b
        d = c * 2
        return torch.clamp(d, min=0, max=50)


class MLPModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(4, 4)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(4, 2)

    def forward(self, x):
        return self.fc2(self.relu(self.fc1(x)))


class ReductionsModel(nn.Module):
    def forward(self, x):
        s = torch.sum(x)
        return s


class HardtanhModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.ht = nn.Hardtanh(min_val=-2.0, max_val=2.0)

    def forward(self, x):
        return self.ht(x)


class UnsupportedOpModel(nn.Module):
    def forward(self, x):
        return torch.sin(x)


class MatmulModel(nn.Module):
    def forward(self, a, b):
        return torch.matmul(a, b)


class BroadcastModel(nn.Module):
    def forward(self, a, b):
        return a + b


class DivModel(nn.Module):
    def forward(self, a, b):
        return a // b



# =========================================================================
# Tracing Tests
# =========================================================================

def test_traces_linear_relu_model_with_shapes():
    model = LinearReLUModel().eval()
    graph = trace_torch_model(model, [torch.zeros(4)])

    assert graph.inputs == ("x",)
    assert graph.outputs
    assert any("linear" in node.operation.lower() for node in graph.nodes)
    assert any("relu" in node.operation.lower() for node in graph.nodes)
    assert "fc_weight" in graph.parameters
    assert "fc_bias" in graph.parameters
    assert graph.to_dict()["nodes"]


# =========================================================================
# Diagnostic & Guardrail Tests
# =========================================================================

def test_rejects_rank_greater_than_2():
    model = nn.Sequential(nn.Identity())
    # 3D tensor should fail shape validation
    with pytest.raises(PyTorchShapeError, match="Unsupported tensor rank 3"):
        lower_torch_model(model, [torch.zeros(2, 3, 4)])


def test_rejects_unsupported_dtype():
    class ComplexModel(nn.Module):
        def forward(self, x):
            return x

    with pytest.raises(PyTorchDTypeError, match="Unsupported dtype 'torch.complex64'"):
        lower_torch_model(ComplexModel(), [torch.zeros(4, dtype=torch.complex64)])


def test_rejects_unsupported_operation():
    model = UnsupportedOpModel().eval()
    with pytest.raises(PyTorchUnsupportedOperationError, match="Unsupported PyTorch operation 'sin'"):
        lower_torch_model(model, [torch.zeros(4)])


# =========================================================================
# Lowering Tests: Code Generation & Layout
# =========================================================================

def test_lower_linear_relu():
    model = LinearReLUModel().eval()
    code, graph = lower_torch_model(model, [torch.zeros(4)], embed_weights=True)

    assert "def linearrelumodel(x, out):" in code
    assert "fc_weight_memory_size = 32" in code
    assert "fc_bias_memory_size = 8" in code
    assert "out_memory_size = 8" in code
    assert "fc_bias[_i]" in code
    assert "fc_weight[_i][_j]" in code
    assert "if _val < 0:" in code


def test_lower_linear_relu_parameter_ports():
    model = LinearReLUModel().eval()
    code, graph = lower_torch_model(model, [torch.zeros(4)], embed_weights=False)

    assert "def linearrelumodel(x, fc_weight, fc_bias, out):" in code
    assert "fc_weight_memory_size = 32" in code
    assert "fc_bias_memory_size = 8" in code


def test_lower_elementwise_broadcast_and_clamp():
    model = ElementwiseModel().eval()
    a = torch.zeros(8, dtype=torch.int32)
    b = torch.zeros(8, dtype=torch.int32)
    code, graph = lower_torch_model(model, [a, b])

    assert "def elementwisemodel(a, b, out):" in code
    assert "a_memory_size = 32" in code
    assert "b_memory_size = 32" in code
    assert "a[_i] + b[_i]" in code
    assert "* 2" in code
    assert "if _val < 0:" in code
    assert "if _val > 50:" in code


def test_lower_reductions():
    model = ReductionsModel().eval()
    x = torch.zeros(4, 4, dtype=torch.int32)
    code, graph = lower_torch_model(model, [x])

    assert "def reductionsmodel(x):" in code
    assert "_acc += x[_i][_j]" in code
    assert "return _sum_1_0" in code


def test_lower_hardtanh():
    model = HardtanhModel().eval()
    x = torch.zeros(8)
    code, graph = lower_torch_model(model, [x])

    assert "if _val < -2.0:" in code
    assert "if _val > 2.0:" in code


# =========================================================================
# Numerical Equivalence Tests
# =========================================================================

def test_numerical_equivalence_linear():
    torch.manual_seed(123)
    model = LinearReLUModel().eval()
    inp = torch.randn(4)
    expected_out = model(inp).detach().cpu().numpy()

    code, _ = lower_torch_model(model, [inp], embed_weights=True)

    # Execute lowered Python function
    local_env = {}
    exec(code, {}, local_env)
    fn = local_env["linearrelumodel"]

    out = [0.0] * 2
    fn(inp.numpy().tolist(), out)

    np.testing.assert_allclose(np.array(out), expected_out, rtol=1e-4, atol=1e-4)


def test_numerical_equivalence_mlp():
    torch.manual_seed(42)
    model = MLPModel().eval()
    inp = torch.randn(4)
    expected_out = model(inp).detach().cpu().numpy()

    code, graph = lower_torch_model(model, [inp], embed_weights=False)

    local_env = {}
    exec(code, {}, local_env)
    fn = local_env["mlpmodel"]

    out = [0.0] * 2
    fn(
        inp.numpy().tolist(),
        graph.parameters["fc1_weight"].tolist(),
        graph.parameters["fc1_bias"].tolist(),
        graph.parameters["fc2_weight"].tolist(),
        graph.parameters["fc2_bias"].tolist(),
        out,
    )

    np.testing.assert_allclose(np.array(out), expected_out, rtol=1e-4, atol=1e-4)


# =========================================================================
# End-to-End Verilog RTL Compilation Tests
# =========================================================================

def test_compile_torch_to_verilog(tmp_path):
    model = LinearReLUModel().eval()
    inp = torch.randn(4)
    out_verilog = tmp_path / "linear_relu.v"

    netlist, graph = compile_torch_model(
        model,
        [inp],
        target="verilog",
        output_file=str(out_verilog),
    )

    assert out_verilog.exists()
    verilog_content = out_verilog.read_text()
    assert "module linearrelumodel" in verilog_content
    assert "linearrelumodel" in netlist.modules


def test_hls_compile_torch_method(tmp_path):
    hls = HLS()
    model = ElementwiseModel().eval()
    a = torch.tensor([1, 2, 3, 4], dtype=torch.int32)
    b = torch.tensor([10, 20, 30, 40], dtype=torch.int32)
    out_v = tmp_path / "elem.v"

    netlist, graph = hls.compile_torch(
        model,
        [a, b],
        target="verilog",
        output_file=str(out_v),
    )

    assert out_v.exists()
    assert "elementwisemodel" in netlist.modules


def test_rejects_mismatched_matmul_shapes():
    model = MatmulModel().eval()
    a = torch.randn(2, 3)
    b = torch.randn(4, 2)
    with pytest.raises(PyTorchShapeError, match="Shape propagation failed"):
        lower_torch_model(model, [a, b])


def test_lower_matmul():
    model = MatmulModel().eval()
    a = torch.randn(2, 3)
    b = torch.randn(3, 2)
    code, _ = lower_torch_model(model, [a, b])

    assert "def matmulmodel(a, b, out):" in code
    assert "a_memory_size = 24" in code
    assert "b_memory_size = 24" in code
    assert "out_memory_size = 16" in code
    assert "for _k in range(3):" in code
    assert "_acc += a[_i][_k] * b[_k][_j]" in code


def test_lower_broadcasting_2d():
    model = BroadcastModel().eval()
    a = torch.randn(3, 4)
    b = torch.randn(4)
    code, _ = lower_torch_model(model, [a, b])

    assert "def broadcastmodel(a, b, out):" in code
    assert "out[_i][_j] = a[_i][_j] + b[_j]" in code


def test_lower_div():
    model = DivModel().eval()
    a = torch.tensor([10, 20, 30, 40], dtype=torch.int32)
    b = torch.tensor([2, 4, 5, 8], dtype=torch.int32)
    code, _ = lower_torch_model(model, [a, b])

    assert "def divmodel(a, b, out):" in code
    assert "out[_i] = a[_i] // b[_i]" in code


def test_numerical_equivalence_matmul():
    torch.manual_seed(99)
    model = MatmulModel().eval()
    a = torch.randn(2, 3)
    b = torch.randn(3, 2)
    expected = model(a, b).detach().numpy()

    code, _ = lower_torch_model(model, [a, b])
    local_env = {}
    exec(code, {}, local_env)
    fn = local_env["matmulmodel"]

    out = [[0.0, 0.0], [0.0, 0.0]]
    fn(a.numpy().tolist(), b.numpy().tolist(), out)
    np.testing.assert_allclose(np.array(out), expected, rtol=1e-4, atol=1e-4)


def test_cli_compile_torch(tmp_path):
    import subprocess
    import sys
    out_v = tmp_path / "cli_linear.v"
    cmd = [
        sys.executable, "-m", "python_hls.cli", "compile-torch",
        "examples/pytorch_linear_relu.py",
        "-s", "4",
        "-o", str(out_v),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert res.returncode == 0
    assert out_v.exists()
    assert "linearrelu" in out_v.read_text()
