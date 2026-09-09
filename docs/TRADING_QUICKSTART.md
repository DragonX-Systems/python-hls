# Trading Quickstart

Get from zero to compiled Verilog in under 5 minutes.

## Install

```bash
git clone https://github.com/missionfission/hls-python.git
cd hls-python
pip install -e .
```

Optional: install [Verilator](https://verilator.org) for RTL verification (`brew install verilator` on macOS).

## Compile a Demo

```bash
python -m python_hls.cli compile demos/trading/gcd.py
```

This produces `demos/trading/gcd.v`, netlist visualizations, and a report.

## Verify RTL (Optional)

```python
from python_hls import HLS

hls = HLS(optimization_level=1, tech_node=45)
hls.compile("demos/trading/gcd.py", target="verilog")
vr = hls.verify_rtl(test_vectors=[{"a": 48, "b": 18}])
# Check vr["verification_results"]["gcd"]["comparison"]["passed"]
```

## Interpret Reports

- **Area** (μm²): Silicon area at the selected tech node
- **Power** (mW): Estimated dynamic power
- **Latency** (cycles): Execution time in clock cycles
- **Critical path**: Timing at the given frequency

## Demo Status

| Kernel | Compiles | RTL Verified |
|--------|----------|---------------|
| GCD | ✓ | ✓ |
| EMA | ✓ | ✓ |
| FIR, Dot product, Matrix mult | ✓ | - |
| MACD, RSI, FFT | ✓ | - |
| Covariance, Bellman-Ford | ✓ | - |

See [README](../README.md) for the full demo table and commands.
