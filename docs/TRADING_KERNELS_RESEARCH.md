# Trading Firm Hardware Kernels: Research and Python-HLS Alignment

**Purpose:** Identify algorithms trading firms accelerate in hardware (FPGA/ASIC), assess their complexity, and map them to Python-HLS demo priorities.

**Sources:** Academic papers, AMD Vitis Quantitative Finance Library, Intel design examples, Exegy whitepapers, GitHub implementations.

---

## Executive Summary

Trading firms use hardware acceleration for two broad classes:

1. **Low-latency tick path** (HFT): Protocol parsing, technical indicators, order book operations, arbitrage detection.
2. **Batch / risk / quant** (seconds to minutes): Options pricing, Monte Carlo, covariance matrix, VaR, Greeks.

Python-HLS is best positioned for **signal processing and linear algebra kernels** that match the supported Python subset (loops, arrays, fixed-size, no recursion). More complex algorithms (Monte Carlo, tree methods, stochastic processes) require RNG and control flow beyond current scope.

---

## 1. HFT / Tick-to-Trade Kernels

### 1.1 Market Data Protocol Parsing (FAST, OPRA)

| Aspect | Detail |
|--------|--------|
| **Role** | Decode Ethernet/IP/UDP + FAST protocol at wire rate; feed order book. |
| **Complexity** | High — bit-level parsing, state machines, variable-length encoding. |
| **FPGA Reality** | 4x latency reduction vs software; 0.72 μs average latency, 1.4M msg/s on B3 exchange template. |
| **Python-HLS Fit** | Poor — inherently bit/byte manipulation, protocol-specific; not a natural Python kernel. |

### 1.2 Technical Indicators (MACD, RSI, Aroon, EMA)

| Aspect | Detail |
|--------|--------|
| **Role** | Real-time signal generation for trading decisions. |
| **Complexity** | Low–Medium — recursive filters, running sums. |
| **FPGA Reality** | MACD: 30x speedup on Zynq; hybrid MACD+RSI for parallel processing. |
| **Python-HLS Fit** | **Good** — MACD, RSI, EMA are pure arithmetic and loops. |

**MACD:** Exponential moving averages of price, then difference and signal line.  
**RSI:** Relative Strength Index = 100 - (100 / (1 + RS)), where RS = avg gain / avg loss over window.  
**EMA:** `y[n] = α·x[n] + (1-α)·y[n-1]` — recursive, one state variable.

Open-source HLS/FPGA implementations exist (GitHub: AzazHassankhan/Low_Latency_Hardware_Accelerator_For_StockMarket_Indicators).

### 1.3 FIR Filter (and Convolutions)

| Aspect | Detail |
|--------|--------|
| **Role** | Market data pipelines, feed handlers, signal smoothing. |
| **Complexity** | Low — dot product of coefficient vector with sliding window. |
| **FPGA Reality** | Standard HLS pattern; used in market data preprocessing. |
| **Python-HLS Fit** | **Strong** — Already in `examples/fir_filter.py`. |

### 1.4 Order Book Reconstruction and Matching

| Aspect | Detail |
|--------|--------|
| **Role** | Maintain local order book from market data; match orders. |
| **Complexity** | High — sorted structures, insert/cancel, memory-efficient representations. |
| **FPGA Reality** | Memory reduced 1.98–93x; real-time snapshot generation. |
| **Python-HLS Fit** | Poor — heavy use of dynamic data structures, sorting, complex control flow. |

### 1.5 Arbitrage Detection (Negative-Cycle Detection)

| Aspect | Detail |
|--------|--------|
| **Role** | Detect profitable cycles across exchanges (e.g., FX: w1×w2×w3 > 1). |
| **Complexity** | Medium–High — Bellman-Ford or Moore-Bellman-Ford; graph traversal. |
| **FPGA Reality** | Bellman-Ford on FPGA: 1.6B edges/sec; graph-based, parallelizable. |
| **Python-HLS Fit** | **Medium** — Graph algorithms need pointer/indirection; may be expressible with fixed-size arrays for small graphs. Long-term target. |

---

## 2. Quantitative Finance Kernels

### 2.1 Options Pricing

| Model | Complexity | FPGA Speedup | Python-HLS Fit |
|-------|------------|--------------|----------------|
| **Black-Scholes (closed-form)** | Low | 270–5400x | **Good** — arithmetic + normal CDF approximation. |
| **Monte Carlo European** | Medium | 380–1521x | Poor — requires RNG, stochastic paths. |
| **Monte Carlo American** | High | 176–529x | Poor — Longstaff-Schwartz, regression. |
| **Finite difference** | Medium | Yes | Medium — grid iteration; possible with fixed loops. |
| **Heston model** | High | Yes | Poor — stochastic volatility, more complex. |

**Black-Scholes:**  
`C = S*N(d1) - K*exp(-r*T)*N(d2)`  
with `d1`, `d2` as functions of S, K, r, σ, T. Needs `erf`/normal CDF (Acklam approximation exists in Vitis L1).

### 2.2 Greeks (Delta, Gamma, Vega, Rho, Theta)

| Aspect | Detail |
|--------|--------|
| **Role** | Risk hedging, sensitivity analysis. |
| **Complexity** | Medium — finite difference or analytic from pricing model. |
| **Python-HLS Fit** | **Good for analytic** — derivatives of Black-Scholes are closed-form; **poor for Monte Carlo pathwise** (complex control flow). |

### 2.3 Covariance Matrix and Portfolio Optimization

| Aspect | Detail |
|--------|--------|
| **Role** | Mean-variance optimization; Σ = A^T A / (M-1); solve for weights. |
| **Complexity** | Medium — matrix multiply, Cholesky/LU, back substitution. |
| **FPGA Reality** | Single-pass covariance 10^5x speedup; Cholesky-based inversion in Vitis. |
| **Python-HLS Fit** | **Good** — Matrix multiply, dot products; Cholesky if triangular solve supported. |

**Vitis L1:** `covCoreMatrix`, `covCoreStrm`, SVD, `trsvCore` (tridiagonal solver), Cholesky-based inversion.

### 2.4 Value at Risk (VaR)

| Aspect | Detail |
|--------|--------|
| **Role** | Portfolio loss at given confidence. |
| **Complexity** | High — Monte Carlo over scenarios. |
| **Python-HLS Fit** | Poor — dominated by Monte Carlo; batch job, not tick-critical. |

### 2.5 FFT / Spectral Analysis

| Aspect | Detail |
|--------|--------|
| **Role** | Decompose market time-series; filter noise; detect cycles. |
| **Complexity** | Medium — O(N log N) butterfly structure. |
| **FPGA Reality** | Standard DSP pattern. |
| **Python-HLS Fit** | **Medium** — `fft_32_code.py` exists; area/metrics issues to resolve. |

---

## 3. AMD Vitis Quantitative Finance Library Snapshot

**L1 (primitives):** RNG (MT19937, Sobol, Box-Muller), BrownianBridge, TrinomialTree, SVD, tridiagonal/pentadiagonal solvers, covariance (matrix + streaming), normal/log-normal CDF/PDF/ICDF, PCA, spline interpolation.

**L2 (pricing engines):** MCEuropean, MCAmerican, MCAsian, MCBarrier, MCDigital, cfBSMEngine (Black-Scholes + Greeks), hcfEngine (Heston closed-form), binomial tree, Hull-White, G2, HJM, LMM.

**L3 (APIs):** Pre-built Heston FD, Monte Carlo Black-Scholes; callable from Python.

**Takeaway:** Industry uses a layered stack. Python-HLS can target **L1-like arithmetic kernels** (covariance, dot product, simple closed-form pricing) and **signal filters** that trading engineers recognize.

---

## 4. Kernel Tiers for Python-HLS Demos

### Tier 1: Ship-Ready (Align with Current Capabilities)

| Kernel | Use Case | Python-HLS Notes |
|--------|----------|-------------------|
| **GCD** | Control flow, equivalence demo | Working |
| **FIR filter** | Signal pipelines | Verify compile |
| **Dot product** | Tick path, latency-critical | Simple loop, `@latency` demo |
| **Simple matrix multiply** | Linear algebra | Fixed size, no list comprehensions |
| **EMA** | Technical indicator | Single recursive equation |
| **Black-Scholes (closed-form)** | Options pricing | S, K, r, σ, T → C; needs normal CDF approx |

### Tier 2: Fix and Ship (Existing Code, Needs Repair)

| Kernel | Current State | Action |
|--------|---------------|--------|
| **FFT** | `fft_32_code.py`, area=0 | Fix area; simplify if needed |
| **MACD** | Not in repo | Add from formula (EMA-based) |
| **RSI** | Not in repo | Add from formula (avg gain/loss) |

### Tier 3: Roadmap (More Complex, Requires Language/IR Extensions)

| Kernel | Blocker |
|--------|---------|
| **Monte Carlo** | RNG, stochastic paths |
| **Covariance matrix** | Larger matrices, Cholesky |
| **Bellman-Ford / arbitrage** | Graph traversal, indirection |
| **Order book ops** | Dynamic structures, sorting |

---

## 5. Recommended Demo Set for Trading Firms

**Must-have (Tier 1):**
1. **GCD** — Control flow, refactor safety.
2. **FIR filter** — Signal pipelines, feed handlers.
3. **Dot product** — Latency-critical, `@latency(8)` demo.
4. **Matrix multiply (small, fixed)** — Factor models, covariance building block.
5. **EMA** — Ubiquitous in indicators.
6. **Black-Scholes** — Closed-form; recognizable to quants.

**Nice-to-have (Tier 2):**
7. **MACD** — 30x FPGA speedup in literature; clear trading relevance.
8. **FFT** — Spectral analysis; fix existing code.

**Landing / README narrative:** "Kernels trading engineers care about: signal filters (FIR, EMA), linear algebra (dot product, matrix mult), and closed-form options pricing (Black-Scholes)."

---

## 6. References (Summarized)

- Speed vs. efficiency: HFT algorithms on FPGA (Zynq) — MACD, RSI, Aroon.
- FPGA-based acceleration for HFT — order book, FAST decoding.
- AMD Vitis Quantitative Finance Library documentation.
- Role of FPGAs in modern option pricing (survey) — 270–5400x speedups.
- Single-pass covariance on hybrid FPGA/CPU.
- FFT in HFT signal processing (QuestDB glossary).
- Bellman-Ford on FPGA (Graph 500, 1.6B edges/sec).
