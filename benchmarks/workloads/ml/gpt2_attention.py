"""
GPT-2 Synthesizable Attention Workload.
Implements bounded multi-head attention projection and scaled dot-product context
accumulation for GPT-2 transformer blocks, compiling directly to synthesizable Verilog.
"""

from typing import Dict, Any, List


def gpt2_attention_step(x0, x1, wq0, wq1, wk0, wk1, wv0, wv1):
    """
    Synthesizable GPT-2 Multi-Head Attention Kernel (Single-Head Step).
    
    Performs:
      1. Linear QKV Projection:
         q = x0 * wq0 + x1 * wq1
         k = x0 * wk0 + x1 * wk1
         v = x0 * wv0 + x1 * wv1
      2. Scaled Dot-Product Attention Score:
         score = q * k
      3. Attention-Weighted Context Output:
         ctx = score * v
         
    Args:
        x0, x1: Quantized input token activation components
        wq0, wq1: Query projection matrix weights
        wk0, wk1: Key projection matrix weights
        wv0, wv1: Value projection matrix weights
        
    Returns:
        ctx: 32-bit signed attention context projection
    """
    q = (x0 * wq0) + (x1 * wq1)
    k = (x0 * wk0) + (x1 * wk1)
    v = (x0 * wv0) + (x1 * wv1)
    score = q * k
    ctx = score * v
    return ctx


def gpt2_attention_slice_4d(q0, q1, q2, q3, k0, k1, k2, k3, v0, v1, v2, v3):
    """
    Synthesizable 4-dimensional Attention Dot-Product and Context Accumulation.
    
    Computes:
      score = sum(q_i * k_i for i in 0..3)
      ctx = score * v0 + score * v1 + score * v2 + score * v3
    """
    dot0 = (q0 * k0) + (q1 * k1)
    dot1 = (q2 * k2) + (q3 * k3)
    score = dot0 + dot1
    ctx0 = score * v0
    ctx1 = score * v1
    ctx2 = score * v2
    ctx3 = score * v3
    return (ctx0 + ctx1) + (ctx2 + ctx3)


def generate_gpt2_test_vectors() -> List[Dict[str, int]]:
    """Generate representative fixed-point test vectors for GPT-2 attention."""
    return [
        {"x0": 2, "x1": 3, "wq0": 1, "wq1": -1, "wk0": 2, "wk1": 1, "wv0": 3, "wv1": -2},
        {"x0": 4, "x1": -2, "wq0": 2, "wq1": 3, "wk0": 1, "wk1": -1, "wv0": 1, "wv1": 2},
        {"x0": 1, "x1": 1, "wq0": 2, "wq1": 2, "wk0": 3, "wk1": 3, "wv0": 4, "wv1": 4},
        {"x0": 0, "x1": 5, "wq0": 0, "wq1": 2, "wk0": 0, "wk1": 1, "wv0": 0, "wv1": 3},
        {"x0": -3, "x1": 4, "wq0": -2, "wq1": 1, "wk0": 1, "wk1": -2, "wv0": 2, "wv1": 1},
        {"x0": 5, "x1": -5, "wq0": 1, "wq1": 1, "wk0": 2, "wk1": 2, "wv0": -1, "wv1": 1},
    ]


def run_reference_gpt2(vectors: List[Dict[str, int]]) -> List[int]:
    """Execute reference Python implementation on test vectors."""
    results = []
    for vec in vectors:
        res = gpt2_attention_step(
            vec["x0"], vec["x1"],
            vec["wq0"], vec["wq1"],
            vec["wk0"], vec["wk1"],
            vec["wv0"], vec["wv1"]
        )
        results.append(res)
    return results
