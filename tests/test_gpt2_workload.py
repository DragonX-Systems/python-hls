"""
Test suite for synthesizable GPT-2 Attention Workload.
Validates HLS frontend compilation, synthesizable Verilog emission, DSE estimation,
and Verilator RTL simulation equivalence.
"""

import os
import sys
import tempfile
import pytest

from python_hls import HLS
from python_hls.verification import RTLVerifier
from benchmarks.workloads.ml.gpt2_attention import (
    gpt2_attention_step,
    gpt2_attention_slice_4d,
    generate_gpt2_test_vectors,
    run_reference_gpt2,
)


class TestGPT2Workload:
    """Test synthesizable GPT-2 transformer workload."""

    def test_gpt2_python_reference_vectors(self):
        """Verify python reference execution on deterministic test vectors."""
        vectors = generate_gpt2_test_vectors()
        assert len(vectors) == 6

        results = run_reference_gpt2(vectors)
        assert len(results) == 6
        # Check specific expected value for vector 2: x=(1,1), wq=(2,2), wk=(3,3), wv=(4,4)
        # q = 1*2 + 1*2 = 4, k = 1*3 + 1*3 = 6, v = 1*4 + 1*4 = 8
        # score = 4*6 = 24, ctx = 24 * 8 = 192
        assert results[2] == 192

    def test_gpt2_hls_compilation_to_verilog(self):
        """Verify HLS compiles GPT-2 attention step to valid synthesizable Verilog."""
        code = """
def gpt2_attention_step(x0, x1, wq0, wq1, wk0, wk1, wv0, wv1):
    q = (x0 * wq0) + (x1 * wq1)
    k = (x0 * wk0) + (x1 * wk1)
    v = (x0 * wv0) + (x1 * wv1)
    score = q * k
    ctx = score * v
    return ctx
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            src_path = f.name

        try:
            hls = HLS(tech_node=45, optimization_level=1)
            netlist = hls.compile(src_path, target="verilog")
            assert netlist is not None

            # Verify Verilog was emitted
            v_path = src_path.replace(".py", ".v")
            assert os.path.exists(v_path)
            with open(v_path, "r") as vf:
                v_content = vf.read()

            assert "module gpt2_attention_step" in v_content
            assert "input wire clk" in v_content
            assert "input wire rst_n" in v_content
            assert "output reg signed [31:0] return_val" in v_content
            assert "output reg done" in v_content
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)
            v_path = src_path.replace(".py", ".v")
            if os.path.exists(v_path):
                os.unlink(v_path)

    def test_gpt2_4d_slice_compilation(self):
        """Verify 4D attention slice compiles to Verilog."""
        code = """
def gpt2_attention_slice_4d(q0, q1, q2, q3, k0, k1, k2, k3, v0, v1, v2, v3):
    dot0 = (q0 * k0) + (q1 * k1)
    dot1 = (q2 * k2) + (q3 * k3)
    score = dot0 + dot1
    ctx0 = score * v0
    ctx1 = score * v1
    ctx2 = score * v2
    ctx3 = score * v3
    return (ctx0 + ctx1) + (ctx2 + ctx3)
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            src_path = f.name

        try:
            hls = HLS(tech_node=45, optimization_level=1)
            netlist = hls.compile(src_path, target="verilog")
            assert netlist is not None
            v_path = src_path.replace(".py", ".v")
            assert os.path.exists(v_path)
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)
            v_path = src_path.replace(".py", ".v")
            if os.path.exists(v_path):
                os.unlink(v_path)

    def test_gpt2_verilator_python_equivalence(self):
        """Verify bit-exact numerical equivalence between Python and Verilator simulation."""
        code = """
def gpt2_attention_step(x0, x1, wq0, wq1, wk0, wk1, wv0, wv1):
    q = (x0 * wq0) + (x1 * wq1)
    k = (x0 * wk0) + (x1 * wk1)
    v = (x0 * wv0) + (x1 * wv1)
    score = q * k
    ctx = score * v
    return ctx
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            src_path = f.name

        try:
            hls = HLS(tech_node=45, optimization_level=1)
            hls.compile(src_path, target="verilog")

            verifier = RTLVerifier()
            if not verifier.verilator_available:
                pytest.skip("Verilator not available")

            vectors = generate_gpt2_test_vectors()
            res = verifier.verify_hls_compilation(src_path, hls, test_vectors=vectors)

            comp = res["verification_results"]["gpt2_attention_step"]["comparison"]
            assert comp["total_tests"] == len(vectors)
            assert comp["failed"] == 0, f"Mismatches found: {comp['mismatches']}"
            assert comp["passed"] == len(vectors)
        finally:
            if os.path.exists(src_path):
                os.unlink(src_path)
            v_path = src_path.replace(".py", ".v")
            if os.path.exists(v_path):
                os.unlink(v_path)
