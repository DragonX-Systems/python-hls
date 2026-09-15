# Python-HLS Representative Workload Benchmarks

> [!NOTE]
> This benchmark suite evaluates realistic, representative slices from quantized ML inference,
> data science, and quantitative finance. Compilation success, simulation equivalence,
> and physical PPA are reported distinctly below.

## 1. Workload Specifications & Hardware Assumptions

| Domain | Workload | Entry Function | Shapes & Dtypes | Quantization | Hardware Assumptions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FINANCE** | `vwap_orderbook` | `vwap_orderbook` | `bid_prices`: [5]<br>`bid_sizes`: [5]<br>`ask_prices`: [5]<br>`ask_sizes`: [5] | Integer price-time tick representation with basis-point precision | • Fixed 5-level market depth snapshot directly streamable<br>• Parallel multiply-accumulate trees for notional calculations<br>• Deterministic divider units for VWAP ratios |

## 2. Compilation & Simulation Equivalence

| Domain | Workload | Compilation Status | Op Count | Latency (Cycles) | Equivalence Status | Test Vectors | RTL Output |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **FINANCE** | `vwap_orderbook` | ✅ PASS | 27 | 176 | ✅ PASS | 2/2 | — |

## 3. Implementation / Physical PPA Results (DSE Across Nodes)

| Domain | Workload | Node | Area ($\mu\text{m}^2$) | Power (mW) | Latency (ns) | Clock (MHz) | Critical Path (ns) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |

## 4. Hardware Limitations & Unsupported Operations

### `vwap_orderbook` (5-Level LOB Micro-Price and VWAP Signal)
- **Unsupported**: Dynamic order book level insertion trees
- **Unsupported**: String parsing of FIX/ITCH network packets
