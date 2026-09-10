"""
Catalog and reference implementations for representative HLS benchmarks.
Contains pure Python reference models, test vectors, and workload configurations.
"""

import os
from typing import Dict, List, Any
from benchmarks.models import WorkloadConfig

WORKLOADS_DIR = os.path.dirname(__file__)


# ==============================================================================
# 1. Machine Learning Workloads
# ==============================================================================

def ref_mlp_layer(x: List[int], w: List[List[int]], b: List[int], y: List[int] = None) -> List[int]:
    """Reference implementation for mlp_layer."""
    out = [0] * 4
    for i in range(4):
        acc = b[i]
        for j in range(4):
            acc += w[i][j] * x[j]
        out[i] = max(0, acc)
    if y is not None:
        for i in range(4):
            y[i] = out[i]
    return out


def ref_attention_slice(q: List[int], k: List[List[int]], v: List[List[int]], out: List[int] = None) -> List[int]:
    """Reference implementation for attention_slice."""
    scores = [0] * 4
    for i in range(4):
        s = sum(q[d] * k[i][d] for d in range(4))
        scores[i] = max(0, s) // 2

    total = sum(scores)
    if total == 0:
        total = 1

    result = [0] * 4
    for d in range(4):
        ctx = sum(scores[i] * v[i][d] for i in range(4))
        result[d] = ctx // total

    if out is not None:
        for d in range(4):
            out[d] = result[d]
    return result


def ref_conv1d_quant(x: List[int], weights: List[int], bias: int, out: List[int] = None) -> List[int]:
    """Reference implementation for conv1d_quant."""
    result = [0] * 13
    for i in range(13):
        acc = bias + sum(x[i + k] * weights[k] for k in range(4))
        res = acc + x[i + 1]
        result[i] = max(0, res)
    if out is not None:
        for i in range(13):
            out[i] = result[i]
    return result


# ==============================================================================
# 2. Data Science & Scientific Computing Workloads
# ==============================================================================

def ref_covariance_matrix(data: List[List[int]], cov: List[List[int]] = None) -> List[List[int]]:
    """Reference implementation for covariance_matrix."""
    means = [sum(data[f][t] for t in range(8)) // 8 for f in range(4)]
    result = [[0] * 4 for _ in range(4)]
    for f1 in range(4):
        for f2 in range(4):
            c_sum = sum((data[f1][t] - means[f1]) * (data[f2][t] - means[f2]) for t in range(8))
            result[f1][f2] = c_sum // 7
    if cov is not None:
        for f1 in range(4):
            for f2 in range(4):
                cov[f1][f2] = result[f1][f2]
    return result


def ref_zscore_normalize(x: List[int], out: List[int] = None) -> List[int]:
    """Reference implementation for zscore_normalize."""
    mean = sum(x) // 8
    var_sum = sum((v - mean) ** 2 for v in x)
    variance = var_sum // 8

    std = variance
    if std > 0:
        for _ in range(6):
            std = (std + variance // std) // 2
    if std == 0:
        std = 1

    result = [((v - mean) * 1000) // std for v in x]
    if out is not None:
        for i in range(8):
            out[i] = result[i]
    return result


def ref_fir_filter_2d(img: List[List[int]], kernel: List[List[int]], out: List[List[int]] = None) -> List[List[int]]:
    """Reference implementation for fir_filter_2d."""
    result = [[0] * 4 for _ in range(4)]
    for r in range(4):
        for c in range(4):
            val = 0
            for kr in range(3):
                for kc in range(3):
                    val += img[r + kr][c + kc] * kernel[kr][kc]
            result[r][c] = val // 16
    if out is not None:
        for r in range(4):
            for c in range(4):
                out[r][c] = result[r][c]
    return result


# ==============================================================================
# 3. Quantitative Finance Workloads
# ==============================================================================

def ref_black_scholes_lattice(s_nodes: List[int], strike: int, q_up: int, q_down: int, discount_denom: int) -> int:
    """Reference implementation for black_scholes_lattice."""
    values = [max(0, s - strike) for s in s_nodes]
    for step in range(4, 0, -1):
        values = [(values[i + 1] * q_up + values[i] * q_down) // discount_denom for i in range(step)]
    return values[0]


def ref_vwap_orderbook(bid_prices: List[int], bid_sizes: List[int], ask_prices: List[int], ask_sizes: List[int]) -> int:
    """Reference implementation for vwap_orderbook."""
    tot_bid_vol = sum(bid_sizes)
    tot_ask_vol = sum(ask_sizes)
    bid_notional = sum(bid_prices[i] * bid_sizes[i] for i in range(5))
    ask_notional = sum(ask_prices[i] * ask_sizes[i] for i in range(5))

    vwap_bid = bid_notional // tot_bid_vol if tot_bid_vol > 0 else 0
    vwap_ask = ask_notional // tot_ask_vol if tot_ask_vol > 0 else 0

    combined_vol = tot_bid_vol + tot_ask_vol
    vwap_mid = (bid_notional + ask_notional) // combined_vol if combined_vol > 0 else 0

    top_spread_vol = bid_sizes[0] + ask_sizes[0]
    micro_price = (bid_prices[0] * ask_sizes[0] + ask_prices[0] * bid_sizes[0]) // top_spread_vol if top_spread_vol > 0 else 0

    return micro_price + vwap_mid


def ref_portfolio_var(weights: List[int], cov_matrix: List[List[int]]) -> int:
    """Reference implementation for portfolio_var."""
    port_var = 0
    for i in range(4):
        row_sum = sum(cov_matrix[i][j] * weights[j] for j in range(4))
        port_var += weights[i] * (row_sum // 10000)

    x = port_var // 10000
    if x <= 0:
        return 0

    r = x
    for _ in range(8):
        if r > 0:
            r = (r + x // r) // 2

    return (r * 233) // 100


# ==============================================================================
# Workload Configurations
# ==============================================================================

def get_workload_catalog() -> Dict[str, WorkloadConfig]:
    """Return dictionary of all 9 pinned workload configurations."""
    catalog = {
        "mlp_layer": WorkloadConfig(
            name="mlp_layer",
            domain="ml",
            display_name="Quantized MLP Layer (GEMV + ReLU)",
            description="4x4 Quantized matrix-vector multiplication with bias accumulation and ReLU activation",
            source_file=os.path.join(WORKLOADS_DIR, "ml", "mlp_layer.py"),
            entry_function="mlp_layer",
            shapes={"x": [4], "w": [4, 4], "b": [4], "y": [4]},
            dtypes={"x": "int32 (int8 input)", "w": "int32 (int8 weights)", "b": "int32 bias", "y": "int32 output"},
            quantization="int8 symmetric weights/inputs with 32-bit accumulators",
            hardware_assumptions=[
                "Fixed static shapes: 4x4 matrix and 4-element vectors",
                "Sequential or pipelined MAC schedule",
                "Zero-latency ReLU clamp"
            ],
            unsupported_operations=["Floating point operations", "Dynamic tensor reshaping or batching"],
            reference_fn=ref_mlp_layer,
            test_vectors=[
                {"x": [1, 2, 3, 4], "w": [[1, 0, -1, 2], [0, 2, 1, -1], [-2, 1, 0, 3], [1, 1, 1, 1]], "b": [10, -5, 2, 0], "y": [0, 0, 0, 0]},
                {"x": [5, -3, 2, -1], "w": [[2, 1, 0, -2], [-1, 3, -2, 1], [0, 0, 4, -1], [3, -2, 1, 0]], "b": [0, 10, -8, 5], "y": [0, 0, 0, 0]},
                {"x": [0, 0, 0, 0], "w": [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]], "b": [-10, 20, -5, 15], "y": [0, 0, 0, 0]}
            ]
        ),
        "attention_slice": WorkloadConfig(
            name="attention_slice",
            domain="ml",
            display_name="Scaled Dot-Product Attention Slice",
            description="Transformer attention primitive with Q*K^T scoring, integer normalization, and context projection",
            source_file=os.path.join(WORKLOADS_DIR, "ml", "attention_slice.py"),
            entry_function="attention_slice",
            shapes={"q": [4], "k": [4, 4], "v": [4, 4], "out": [4]},
            dtypes={"q": "int32 query vector", "k": "int32 key matrix", "v": "int32 value matrix", "out": "int32 context vector"},
            quantization="Integer scaled fixed-point with sqrt(d_k)=2 factor",
            hardware_assumptions=[
                "Fixed 4-element head dimension and 4-token sequence slice",
                "Integer sum normalization instead of exponential softmax",
                "Sequential or pipelined inner-product dot product"
            ],
            unsupported_operations=["Transcendental exp() operations in hardware", "Dynamic sequence lengths"],
            reference_fn=ref_attention_slice,
            test_vectors=[
                {
                    "q": [2, 4, 1, 3],
                    "k": [[1, 0, 2, 1], [0, 3, 1, 0], [2, 1, 0, 4], [1, 1, 1, 1]],
                    "v": [[10, 20, 30, 40], [5, 15, 25, 35], [50, 60, 70, 80], [0, 10, 20, 30]],
                    "out": [0, 0, 0, 0]
                },
                {
                    "q": [0, 5, 0, 2],
                    "k": [[2, 2, 2, 2], [0, 4, 0, 1], [1, 0, 3, 0], [3, 1, 0, 2]],
                    "v": [[12, 24, 36, 48], [100, 200, 300, 400], [1, 2, 3, 4], [10, 20, 30, 40]],
                    "out": [0, 0, 0, 0]
                }
            ]
        ),
        "conv1d_quant": WorkloadConfig(
            name="conv1d_quant",
            domain="ml",
            display_name="Quantized 1D Temporal Convolution with Residual",
            description="16-sample sequence convolved with 4-tap kernel, residual skip connection, and ReLU activation",
            source_file=os.path.join(WORKLOADS_DIR, "ml", "conv1d_quant.py"),
            entry_function="conv1d_quant",
            shapes={"x": [16], "weights": [4], "bias": "scalar", "out": [13]},
            dtypes={"x": "int32 signal", "weights": "int32 filter", "bias": "int32 scalar", "out": "int32 output"},
            quantization="8-bit integer weights/activations with 32-bit internal accumulation",
            hardware_assumptions=[
                "Fixed length 16 input buffer, static 4-tap filter",
                "Linear sliding window shift register / memory indexing",
                "Zero-latency skip-connection addition and ReLU clamp"
            ],
            unsupported_operations=["Dynamic dilation or variable stride factors", "Dynamic padding modes"],
            reference_fn=ref_conv1d_quant,
            test_vectors=[
                {"x": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], "weights": [2, -1, 3, -2], "bias": 10, "out": [0] * 13},
                {"x": [10, -5, 20, -10, 15, -2, 8, -4, 12, -6, 18, -9, 14, -7, 16, -8], "weights": [1, 2, 1, 0], "bias": -50, "out": [0] * 13}
            ]
        ),
        "covariance_matrix": WorkloadConfig(
            name="covariance_matrix",
            domain="data_science",
            display_name="Multi-Feature Sample Covariance Matrix",
            description="4x4 covariance matrix computed from 4 features and 8 observation samples",
            source_file=os.path.join(WORKLOADS_DIR, "data_science", "covariance_matrix.py"),
            entry_function="covariance_matrix",
            shapes={"data": [4, 8], "cov": [4, 4]},
            dtypes={"data": "int32 observation matrix", "cov": "int32 sample covariance matrix"},
            quantization="Scaled integer arithmetic with integer division by (N-1)=7",
            hardware_assumptions=[
                "Fixed 4x8 observations array",
                "Two-stage reduction datapath (mean reduction followed by cross-deviation products)",
                "Direct BRAM / register bank addressing"
            ],
            unsupported_operations=["Dynamic feature or observation counts", "Floating point division"],
            reference_fn=ref_covariance_matrix,
            test_vectors=[
                {
                    "data": [
                        [10, 12, 14, 16, 18, 20, 22, 24],
                        [5, 6, 8, 9, 11, 12, 14, 15],
                        [20, 18, 16, 14, 12, 10, 8, 6],
                        [100, 105, 110, 115, 120, 125, 130, 135]
                    ],
                    "cov": [[0] * 4 for _ in range(4)]
                },
                {
                    "data": [
                        [1, -2, 3, -4, 5, -6, 7, -8],
                        [2, 4, 6, 8, 10, 12, 14, 16],
                        [0, 5, -5, 10, -10, 15, -15, 20],
                        [7, 7, 7, 7, 7, 7, 7, 7]
                    ],
                    "cov": [[0] * 4 for _ in range(4)]
                }
            ]
        ),
        "zscore_normalize": WorkloadConfig(
            name="zscore_normalize",
            domain="data_science",
            display_name="Feature Standardization (Z-Score Normalization)",
            description="Mean reduction, variance accumulation, integer square root, and standardized feature scaling",
            source_file=os.path.join(WORKLOADS_DIR, "data_science", "zscore_normalize.py"),
            entry_function="zscore_normalize",
            shapes={"x": [8], "out": [8]},
            dtypes={"x": "int32 raw features", "out": "int32 standardized values (*1000)"},
            quantization="Scaled integer arithmetic with fixed-point scale factor 1000",
            hardware_assumptions=[
                "Fixed 8-element feature vector",
                "Hardware divider sharing between variance and square root",
                "Bound loop iterations (6 cycles) for Newton-Raphson convergence"
            ],
            unsupported_operations=["Dynamic length arrays", "Float math or math.sqrt import"],
            reference_fn=ref_zscore_normalize,
            test_vectors=[
                {"x": [10, 20, 30, 40, 50, 60, 70, 80], "out": [0] * 8},
                {"x": [100, 102, 98, 105, 95, 101, 99, 100], "out": [0] * 8},
                {"x": [-50, -25, 0, 25, 50, 75, 100, 125], "out": [0] * 8}
            ]
        ),
        "fir_filter_2d": WorkloadConfig(
            name="fir_filter_2d",
            domain="data_science",
            display_name="2D Spatial FIR Filter (Sensor/Image Stencil)",
            description="6x6 sensor image filtered with a 3x3 convolution stencil kernel producing a 4x4 output grid",
            source_file=os.path.join(WORKLOADS_DIR, "data_science", "fir_filter_2d.py"),
            entry_function="fir_filter_2d",
            shapes={"img": [6, 6], "kernel": [3, 3], "out": [4, 4]},
            dtypes={"img": "int32 input image", "kernel": "int32 kernel coefficients", "out": "int32 filtered output"},
            quantization="Quantized integer filter weights with right-shift / 16 normalization",
            hardware_assumptions=[
                "Fixed 6x6 image matrix with line buffer access",
                "Static 3x3 convolution window unrollable into parallel DSP multipliers",
                "Valid boundary mode"
            ],
            unsupported_operations=["Dynamic image dimensions", "Runtime border padding modes"],
            reference_fn=ref_fir_filter_2d,
            test_vectors=[
                {
                    "img": [
                        [10, 10, 10, 20, 20, 20],
                        [10, 10, 10, 20, 20, 20],
                        [10, 10, 10, 20, 20, 20],
                        [30, 30, 30, 40, 40, 40],
                        [30, 30, 30, 40, 40, 40],
                        [30, 30, 30, 40, 40, 40]
                    ],
                    "kernel": [[1, 2, 1], [2, 4, 2], [1, 2, 1]],
                    "out": [[0] * 4 for _ in range(4)]
                },
                {
                    "img": [
                        [0, 5, 10, 15, 20, 25],
                        [5, 10, 15, 20, 25, 30],
                        [10, 15, 20, 25, 30, 35],
                        [15, 20, 25, 30, 35, 40],
                        [20, 25, 30, 35, 40, 45],
                        [25, 30, 35, 40, 45, 50]
                    ],
                    "kernel": [[0, -1, 0], [-1, 4, -1], [0, -1, 0]],
                    "out": [[0] * 4 for _ in range(4)]
                }
            ]
        ),
        "black_scholes_lattice": WorkloadConfig(
            name="black_scholes_lattice",
            domain="finance",
            display_name="Binomial Option Pricing Lattice (Cox-Ross-Rubinstein)",
            description="4-step binomial tree European option pricing lattice with backwards induction roll-back",
            source_file=os.path.join(WORKLOADS_DIR, "finance", "black_scholes_lattice.py"),
            entry_function="black_scholes_lattice",
            shapes={"s_nodes": [5], "strike": "scalar", "q_up": "scalar", "q_down": "scalar", "discount_denom": "scalar"},
            dtypes={"s_nodes": "int32 asset prices", "strike": "int32 strike price", "q_up": "int32 up prob", "q_down": "int32 down prob", "discount_denom": "int32 factor"},
            quantization="Basis-point integer fixed-point with scaled probability weights",
            hardware_assumptions=[
                "Fixed 4-step tree structure with static loop bounds",
                "Sequential or pipelined backwards induction systolic pipeline",
                "Deterministic ALU and multiplier scheduling"
            ],
            unsupported_operations=["American early-exercise dynamic boundaries", "Continuous Black-Scholes erf() integrals"],
            reference_fn=ref_black_scholes_lattice,
            test_vectors=[
                {"s_nodes": [80, 90, 100, 110, 125], "strike": 100, "q_up": 52, "q_down": 48, "discount_denom": 102},
                {"s_nodes": [70, 85, 105, 120, 140], "strike": 95, "q_up": 50, "q_down": 50, "discount_denom": 101},
                {"s_nodes": [100, 100, 100, 100, 100], "strike": 120, "q_up": 50, "q_down": 50, "discount_denom": 100}
            ]
        ),
        "vwap_orderbook": WorkloadConfig(
            name="vwap_orderbook",
            domain="finance",
            display_name="5-Level LOB Micro-Price and VWAP Signal",
            description="Limit order book depth pipeline computing volume-weighted average price and micro-price signals",
            source_file=os.path.join(WORKLOADS_DIR, "finance", "vwap_orderbook.py"),
            entry_function="vwap_orderbook",
            shapes={"bid_prices": [5], "bid_sizes": [5], "ask_prices": [5], "ask_sizes": [5]},
            dtypes={"bid_prices": "int32 prices", "bid_sizes": "int32 sizes", "ask_prices": "int32 prices", "ask_sizes": "int32 sizes"},
            quantization="Integer price-time tick representation with basis-point precision",
            hardware_assumptions=[
                "Fixed 5-level market depth snapshot directly streamable",
                "Parallel multiply-accumulate trees for notional calculations",
                "Deterministic divider units for VWAP ratios"
            ],
            unsupported_operations=["Dynamic order book level insertion trees", "String parsing of FIX/ITCH network packets"],
            reference_fn=ref_vwap_orderbook,
            test_vectors=[
                {
                    "bid_prices": [10000, 9995, 9990, 9985, 9980],
                    "bid_sizes": [50, 100, 150, 200, 250],
                    "ask_prices": [10005, 10010, 10015, 10020, 10025],
                    "ask_sizes": [40, 80, 120, 160, 200]
                },
                {
                    "bid_prices": [5000, 4990, 4980, 4970, 4960],
                    "bid_sizes": [10, 20, 30, 40, 50],
                    "ask_prices": [5010, 5020, 5030, 5040, 5050],
                    "ask_sizes": [100, 100, 100, 100, 100]
                }
            ]
        ),
        "portfolio_var": WorkloadConfig(
            name="portfolio_var",
            domain="finance",
            display_name="4-Asset Portfolio Value-at-Risk (VaR 99%)",
            description="Parametric portfolio variance quadratic form w^T*Sigma*w with integer volatility and 99% VaR scaling",
            source_file=os.path.join(WORKLOADS_DIR, "finance", "portfolio_var.py"),
            entry_function="portfolio_var",
            shapes={"weights": [4], "cov_matrix": [4, 4]},
            dtypes={"weights": "int32 asset weights in bp (10000=100%)", "cov_matrix": "int32 scaled covariance"},
            quantization="Basis-point integer scaling with 8-iteration Newton-Raphson integer square root",
            hardware_assumptions=[
                "Fixed 4-asset portfolio with statically bound double loop",
                "Hardware sharing of divider unit for integer square root",
                "Low-latency single-cycle MAC datapath"
            ],
            unsupported_operations=["Dynamic portfolio rebalancing", "Monte Carlo path simulation"],
            reference_fn=ref_portfolio_var,
            test_vectors=[
                {
                    "weights": [2500, 2500, 2500, 2500],
                    "cov_matrix": [
                        [400, 100, 50, -20],
                        [100, 600, 80, 40],
                        [50, 80, 500, 10],
                        [-20, 40, 10, 300]
                    ]
                },
                {
                    "weights": [5000, 3000, 1500, 500],
                    "cov_matrix": [
                        [1000, 200, 100, 0],
                        [200, 800, 150, 50],
                        [100, 150, 900, -100],
                        [0, 50, -100, 1200]
                    ]
                },
                {
                    "weights": [10000, 0, 0, 0],
                    "cov_matrix": [
                        [400, 100, 50, -20],
                        [100, 600, 80, 40],
                        [50, 80, 500, 10],
                        [-20, 40, 10, 300]
                    ]
                }
            ]
        )
    }
    return catalog
