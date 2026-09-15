# Constraint-Driven Hardware Pipelines and Standard Interfaces

This document specifies the architecture, formal semantics, standard interface protocols, verification methodology, and architectural boundaries for constraint-driven hardware pipelines in Python-HLS.

---

## 1. Overview & Architectural Principles

Python-HLS provides a qualified, constraint-driven pipeline synthesis and verification flow designed to produce predictable, high-throughput hardware accelerator lanes from pure Python functions.

### Core Architecture
- **Single Clock Domain**: All generated pipeline lanes operate synchronously on a single clock domain (`clk`) with an active-low asynchronous reset (`rst_n`).
- **Cycle-Accounted Datapath**: Each pipeline stage corresponds to an explicit register stage. Pipelined functions have deterministically scheduled stages ($L \ge 1$) and initiation intervals ($II \ge 1$).
- **Flow Control & Handshakes**: Standard decoupled handshaking ensures zero data loss, zero dropped transactions, and zero spurious computations under backpressure stalls and sparse inputs.

```
                    +--------------------------------------------------------+
                    | Single-Clock Domain Pipeline Accelerator Lane          |
                    |                                                        |
  [Upstream Master] ===> [Stage 0] ===> [Stage 1] ... ===> [Stage L-1] ===> [Downstream Slave]
      tvalid        |   (Input Reg /     (Compute          (Output Reg)      |     tvalid
      tready        |    Bubble Det)      Step)                              |     tready
      tdata         |                                                        |     tdata
                    |   Flow Control: Backpressure Stalls / Bubble / Drain   |
                    +--------------------------------------------------------+
                               |                  |
                               v                  v
                        pipeline_busy       pipeline_empty
```

---

## 2. Cycle-Accounted Pipeline Semantics

### 2.1 Initiation Interval ($II \ge 1$)
The Initiation Interval ($II$) defines the minimum number of clock cycles between consecutive input transaction acceptances:
- **$II = 1$ (Maximum Sustained Throughput)**:
  When $II = 1$, the pipeline lane can accept a new input transaction on every clock cycle where backpressure stall is absent (`pipe_advance = 1`). Under sustained stimulus, measured throughput achieves:
  $$\text{Throughput} = 1.0 \text{ transaction/cycle}$$
- **$II > 1$ (Throttled Throughput)**:
  When $II > 1$, an internal down-counter (`ii_counter`) paces acceptance. Following an accepted input handshake (`in_valid && in_ready`), `in_ready` is deasserted for $II - 1$ cycles. During stalls, `ii_counter` holds its state.

### 2.2 Backpressure Stalls
Backpressure propagates upstream from the downstream consumer:
$$\text{pipe\_stall} = \text{stage\_valid}[L-1] \land \lnot \text{out\_ready}$$
$$\text{pipe\_advance} = \lnot \text{pipe\_stall}$$

When `pipe_stall` is asserted:
1. All stage data registers hold their current values.
2. All stage valid bits hold their current values.
3. `in_ready` is deasserted to prevent upstream overflow.
4. **Invariant**: No transactions are dropped, corrupted, or duplicated.

### 2.3 Bubble Propagation
When upstream stimulus is sparse (`in_valid = 0` on an un-stalled cycle):
1. Stage 0 marks `stage_valid[0] <= 1'b0`.
2. This invalid state ("bubble") shifts downstream cycle-by-cycle alongside valid transactions.
3. When a bubble reaches Stage $L-1$, `out_valid` is driven low.
4. **Invariant**: No spurious output transactions or side-effects occur during bubble cycles.

### 2.4 Transaction Draining & Status Flags
When upstream ceases sending transactions:
1. In-flight items step forward cycle-by-cycle until reaching the downstream interface.
2. Status outputs:
   - `pipeline_busy = |stage_valid`: High whenever at least one valid transaction is in-flight.
   - `pipeline_empty = !pipeline_busy`: High when all stages are clear.
3. Once drained, `pipeline_empty` is asserted and the pipeline rests in a clean quiescent state.

---

## 3. Standard Hardware Interfaces

Python-HLS supports three verified standard interface protocols:

### 3.1 AXI4-Stream (`axis`)
Standard AMBA AXI4-Stream slave (input) and master (output) interfaces:
| Port | Direction | Description |
|---|---|---|
| `clk` | Input | Clock |
| `rst_n` | Input | Active-low reset |
| `s_axis_tdata` | Input | Slave input data bus (packed for multi-argument functions) |
| `s_axis_tvalid`| Input | Slave input valid |
| `s_axis_tready`| Output | Slave input ready (backpressure to master) |
| `s_axis_tlast` | Input | Slave packet boundary indicator (pipelined to output) |
| `m_axis_tdata` | Output | Master output data bus |
| `m_axis_tvalid`| Output | Master output valid |
| `m_axis_tready`| Input | Master output ready (backpressure from slave) |
| `m_axis_tlast` | Output | Master packet boundary indicator |
| `pipeline_empty`| Output | High when all internal stages contain no in-flight items |
| `pipeline_busy` | Output | High when at least one transaction is in-flight |

### 3.2 Ready-Valid Decoupled Streaming (`ready_valid`)
Lightweight decoupled handshake for streaming accelerator lanes:
| Port | Direction | Description |
|---|---|---|
| `in_data` | Input | Input data bus |
| `in_valid` | Input | Input valid handshake |
| `in_ready` | Output | Input ready handshake |
| `out_data` | Output | Output data bus |
| `out_valid`| Output | Output valid handshake |
| `out_ready`| Input | Output ready handshake |
| `pipeline_empty`| Output | Pipeline empty indicator |
| `pipeline_busy` | Output | Pipeline busy indicator |

### 3.3 Decoupled Memory Lane (`memory`)
Decoupled request/response lane with waitstate backpressure:
| Port | Direction | Description |
|---|---|---|
| `mem_req` | Input | Request valid from upstream |
| `mem_ready` | Output | Memory lane ready to accept request |
| `mem_we` | Input | Write enable (0 = read, 1 = write) |
| `mem_addr` | Input | Memory address bus |
| `mem_wdata` | Input | Memory write data bus |
| `mem_rdata` | Output | Memory read data bus |
| `mem_rvalid`| Output | Memory read response valid |
| `mem_resp_ready`| Input | Downstream ready for read response (backpressure) |
| `pipeline_empty`| Output | Memory lane empty |
| `pipeline_busy` | Output | Memory lane busy |

---

## 4. Public Capability Matrix

| Feature / Protocol | Support Status | Verification Method | Cycle Equivalence |
|---|---|---|---|
| **Initiation Interval $II = 1$** | Supported | Verilator C++ Co-Simulation + Python Sim | Verified ($II_{meas} = 1.0$) |
| **Initiation Interval $II > 1$** | Supported | Verilator C++ Co-Simulation + Python Sim | Verified ($II_{meas} = II_{target}$) |
| **Backpressure Stalls** | Supported | Burst & Randomized Ready Deassertion | Verified (0 dropped, 0 duplicate) |
| **Bubble Propagation** | Supported | Sparse Valid Driving Patterns | Verified (0 spurious transactions) |
| **Drain to Quiescence** | Supported | Post-Stimulus Drain Monitoring | Verified (`pipeline_empty == 1`) |
| **AXI4-Stream (`axis`)** | Supported | Cycle-Accurate AMBA Protocol Check | Verified |
| **Ready-Valid Handshake** | Supported | Decoupled Streaming Protocol Check | Verified |
| **Decoupled Memory Lane** | Supported | Request-Response Waitstate Check | Verified |
| **Multi-Stage Operand Pipelining** | Supported | Multi-stage delay register analysis | Verified |

---

## 5. Explicit Architectural Boundaries & Limitations

To maintain mathematical rigor and cycle accuracy, Python-HLS establishes the following clear boundaries:

1. **Single-Clock Domain Only**:
   All accelerator lanes operate on a single synchronous clock domain (`clk`). Clock Domain Crossing (CDC), asynchronous FIFO handoffs, and dual-clock FIFOs are **not** generated within this lane. If multi-clock systems are required, CDC synchronization bridges must be wrapped externally.
2. **Deterministic Single Hierarchy**:
   Generated pipelines produce clean, flat single-module RTL structures or direct datapath blocks. Dynamic inter-module hierarchy synthesis with arbitrary cross-module stall topologies is out of scope.
3. **No Unbounded Memory Latency**:
   Pipeline stages assume cycle-accounted memory latency. Complex multi-ported memory hierarchies with non-deterministic cache miss penalties must interface via the decoupled `memory` lane protocol with waitstate stalls (`mem_resp_ready`).
4. **Integer and Fixed-Point Arithmetic**:
   Arithmetic pipelines target synthesizable integer, bitwise, and fixed-point datapaths. Floating-point units require explicit multi-cycle core bindings.

---

## 6. Usage Examples

### Using the Python Decorator
```python
from python_hls.pipeline import pipeline

@pipeline(ii=1, depth=3, interface='axis')
def mac_lane(a: int, b: int, c: int) -> int:
    return a * b + c
```

### Using Latency & Pipeline Pragmas in Source
```python
# pragma hls pipeline ii=1 depth=2 interface=ready_valid
def add_kernel(x: int, y: int) -> int:
    return x + y
```

### Programmatic Compilation and Verification
```python
from python_hls import HLS
from python_hls.pipeline import PipelineSpec

hls = HLS()

# 1. Compile pipeline to synthesizable Verilog
verilog = hls.compile_pipeline(
    source="accelerators.py",
    entry_function="mac_lane",
    ii=1,
    depth=3,
    interface="axis"
)

# 2. Co-simulate and verify with Verilator across stalls & bubbles
result = hls.verify_pipeline(
    source="accelerators.py",
    entry_function="mac_lane",
    ii=1,
    depth=3,
    interface="axis",
    test_stalls=True,
    test_bubbles=True
)

assert result.passed
print(f"Verified II={result.measured_ii:.2f}, mismatches={result.mismatches}")
```

### Command-Line Interface (CLI)
```bash
# Compile pipeline to Verilog
python -m python_hls.cli compile-pipeline my_kernel.py --ii 1 --depth 3 --interface axis -o my_kernel.v

# Co-simulate and verify with Verilator
python -m python_hls.cli verify-pipeline my_kernel.py --ii 1 --depth 3 --interface axis --test-stalls --test-bubbles
```
