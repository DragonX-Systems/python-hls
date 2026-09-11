#!/usr/bin/env python3
"""
Synthesizable GPT-2 Attention Example.
Demonstrates compiling a GPT-2 transformer multi-head attention slice into synthesizable
Verilog RTL and verifying Python-versus-RTL numerical equivalence using Verilator.

Usage:
    python examples/gpt2_attention_synthesizable.py
"""

import os
import sys
import tempfile

# Add repo root to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from python_hls import HLS
from python_hls.verification import RTLVerifier
from benchmarks.workloads.ml.gpt2_attention import (
    gpt2_attention_step,
    generate_gpt2_test_vectors,
    run_reference_gpt2,
)


def main():
    print("=" * 70)
    print("Python-HLS: Synthesizable GPT-2 Multi-Head Attention Kernel")
    print("=" * 70)

    # 1. Define source code
    source_code = """
def gpt2_attention_step(x0, x1, wq0, wq1, wk0, wk1, wv0, wv1):
    \"\"\"
    Synthesizable GPT-2 Attention Engine (Single-Head Step).
    Computes QKV projection, scaled dot-product, and context projection.
    \"\"\"
    q = (x0 * wq0) + (x1 * wq1)
    k = (x0 * wk0) + (x1 * wk1)
    v = (x0 * wv0) + (x1 * wv1)
    score = q * k
    ctx = score * v
    return ctx
"""

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(source_code)
        src_path = f.name

    verilog_out = os.path.join(REPO_ROOT, "benchmarks", "reports", "rtl", "gpt2_attention.v")
    os.makedirs(os.path.dirname(verilog_out), exist_ok=True)

    try:
        # 2. Compile Python to Synthesizable Verilog
        print("\n[Step 1] Compiling Python GPT-2 attention kernel to Verilog RTL...")
        hls = HLS(tech_node=45, optimization_level=1)
        netlist = hls.compile(src_path, target="verilog", output_file=verilog_out)
        print(f" -> Successfully synthesized: {verilog_out}")

        # 3. Inspect generated RTL
        with open(verilog_out, "r") as vf:
            lines = vf.readlines()
        print(f" -> Generated {len(lines)} lines of synthesizable Verilog RTL.")
        print(" -> Top module header:")
        for line in lines[:25]:
            print("    " + line.rstrip())

        # 4. Run Python Reference Execution
        print("\n[Step 2] Generating deterministic test vectors...")
        vectors = generate_gpt2_test_vectors()
        py_results = run_reference_gpt2(vectors)
        print(f" -> Generated {len(vectors)} test vectors.")
        for idx, (v, exp) in enumerate(zip(vectors[:3], py_results[:3])):
            print(f"    Vector {idx}: token inputs=({v['x0']}, {v['x1']}) -> Expected Python Output = {exp}")

        # 5. Run Verilator RTL Verification
        print("\n[Step 3] Running Verilator C++ simulation & verifying Python-vs-RTL equivalence...")
        verifier = RTLVerifier()
        if not verifier.verilator_available:
            print(" -> Verilator not found on system. Skipping C++ simulation.")
            return

        res = verifier.verify_hls_compilation(src_path, hls, test_vectors=vectors)
        comp = res["verification_results"]["gpt2_attention_step"]["comparison"]

        print(f" -> Simulation Total Tests: {comp['total_tests']}")
        print(f" -> Passed Bit-Exact:      {comp['passed']}")
        print(f" -> Failed / Mismatches:   {comp['failed']}")

        if comp["failed"] == 0:
            print("\n[SUCCESS] GPT-2 Attention Kernel verified bit-exact against Verilog RTL simulation!")
        else:
            print(f"\n[FAILURE] Mismatches detected: {comp['mismatches']}")

    finally:
        if os.path.exists(src_path):
            os.unlink(src_path)
        auto_v = src_path.replace(".py", ".v")
        if os.path.exists(auto_v):
            os.unlink(auto_v)


if __name__ == "__main__":
    main()
