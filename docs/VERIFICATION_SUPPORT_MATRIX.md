# Verification Support Matrix & RTL Qualification Guide

This document defines the interface and semantic boundaries for **Python-versus-RTL Verification** in Python-HLS, distinguishing compilation capabilities from qualified cycle-accurate simulation equivalence.

---

## 1. Support Matrix Overview

| Feature / Interface | Compiler AST Support | Verilog Generation | Automated RTL Sim Qualification | Diagnostic on Unsupported |
| :--- | :---: | :---: | :---: | :---: |
| **Scalar Inputs (`int`, `float`, `bool`)** | Full | Full | Qualified | `RTLVerificationError` on mismatch |
| **Scalar Return (`int`, `float`, `bool`)** | Full | Full | Qualified | `RTLVerificationError` on mismatch |
| **1D Array Memory Inputs (`list[int]`)** | Full | Full | Qualified | Interface diagnostic |
| **1D Array Memory Outputs (`list[int]`)** | Full | Full | Qualified | Interface diagnostic |
| **Multi-Value Returns (`return a, b`)** | Partial | Scalar only | Explicit Diagnostic | `RTLVerificationInterfaceError` |
| **Sequential Arithmetic (`+`, `-`, `*`, `<<`, `>>`, `&`, `\|`, `^`)** | Full | Full | Qualified | Mismatch report table |
| **Conditional Branches (`if`/`elif`/`else`)** | Full | Full | Qualified | Mismatch report table |
| **Bounded For Loops (`for i in range(N)`)** | Full | Full | Qualified | Mismatch report table |
| **Data-Dependent While Loops (`while cond`)** | Full | Full | Qualified | Cycle timeout diagnostic |
| **Unbounded / Infinite Dynamic Loops** | Restricted | Restricted | Cycle Timeout | `RTLSimulationTimeoutError` |

---

## 2. Interface Conventions

Generated Verilog modules conform to standard synchronous handshaking interfaces:

### Clock & Reset
- **`clk`**: Clock signal, active on rising edge (`posedge clk`).
- **`rst_n`**: Active-low asynchronous reset (`negedge rst_n`). Resets all FSM states and internal registers to initial conditions.

### Control Handshake
- **`valid`**: Input control pulse indicating valid inputs are presented to start module execution.
- **`done`**: Output control flag asserted high when computation is finished and results are stable on output ports.

### Memory & Array Handshake
For array parameters (e.g. `data`), the module exposes:
- **`{name}_data_in`**: Read data input (bitwidth matches element type, e.g. `[31:0]`).
- **`{name}_data_out`**: Write data output.
- **`{name}_addr`**: Element memory address index.
- **`{name}_enable`**: Chip enable signal.
- **`{name}_read_enable` / `{name}_write_enable`**: Direction control flags.
- **`{name}_size`**: Runtime length of the array.

---

## 3. Test-Vector Generation & Determinism

Python-HLS supports deterministic, reproducible verification vector generation:

1. **Seeding (`--seed <int>`)**:
   - Setting `--seed 42` guarantees that identical pseudo-random stimuli are supplied across local runs and CI pipelines.
2. **Automated Corner Cases**:
   Every test suite automatically injects boundary conditions:
   - **Zero Case**: All scalar inputs set to `0`, arrays initialized to `0`.
   - **One Case**: All scalar inputs set to `1`.
   - **Minus One / Sign Inversion**: Signed inputs set to `-1` to exercise 2's-complement arithmetic paths.
   - **Max Boundaries**: Bitwidth limits (e.g. `(1 << (bit_width - 1)) - 1` for signed, `(1 << bit_width) - 1` for unsigned).
3. **External Test Vectors**:
   Test vectors can be loaded from external JSON or YAML files:
   ```json
   [
     {"a": 48, "b": 18},
     {"a": 100, "b": 25},
     {"a": 7, "b": 13}
   ]
   ```

---

## 4. Diagnostics & Artifact Preservation

### Verilator Compilation & Warnings
Python-HLS suppresses benign toolchain warnings (`-Wno-DECLFILENAME`, `-Wno-UNUSEDSIGNAL`, `-Wno-WIDTHEXPAND`, `-Wno-WIDTHTRUNC`) while enforcing single-driver procedural assignments (`-Wno-MULTIDRIVENPROC` verified).

### Structured Mismatch Reporting
When simulation values diverge from Python reference execution, an actionable diff table is emitted:
```
Module: example_kernel
----------------------------------------
  [FAIL] 1/10 tests failed (Timeouts: 0)

  Mismatches (up to 5 shown):
    - Test #3: inputs={'a': 0, 'b': -5}
        Expected (Python): 0
        Received (RTL):    -5
```

### Artifact Directory (`--output-dir <dir>`)
Passing `--output-dir <path>` preserves all simulation artifacts for post-mortem debugging:
- `<module>.v`: Complete synthesizable Verilog module.
- `<module>_tb.cpp`: Generated C++ simulation testbench.
- `V<module>`: Compiled native simulation binary.
- `<module>_tb.vcd`: Cycle-accurate VCD waveform trace (when `--vcd` is enabled).
- `test_vectors.json`: Exact test vectors evaluated.
- `<module>_compile.log` and `<module>_simulation.log`: Raw toolchain stdout and stderr logs.
- `verification_report.txt`: Full test result breakdown.

---

## 5. Waveform Inspection with GTKWave

To debug timing and state transitions:
```bash
# 1. Run verification with VCD trace enabled and output preserved
python -m python_hls.cli verify-rtl demos/trading/gcd.py --vcd -o debug_artifacts/

# 2. Open generated waveform
gtkwave debug_artifacts/gcd_tb.vcd
```
Signal hierarchy:
- `TOP.gcd.clk`: Clock pulse
- `TOP.gcd.rst_n`: Active-low reset
- `TOP.gcd.valid` / `TOP.gcd.done`: Handshake status
- `TOP.gcd.current_state`: FSM state transitions
- `TOP.gcd.return_val`: Output result register

---

## 6. Known Limitations

1. **Multi-Value Returns**:
   Functions returning multiple values via tuples (`return a, b`) are currently limited to scalar return ports in RTL generation. In the verification harness, this immediately raises `RTLVerificationInterfaceError` rather than silently failing.
2. **Infinite Loops / Deadlocks**:
   If an algorithm fails to assert `done` within `max_cycles` (default: 1000), a timeout diagnostic is generated and flagged in the test report. Increase `--max-cycles` for higher-latency algorithms.
