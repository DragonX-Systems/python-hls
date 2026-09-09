# Supported Python Subset

A concise reference for writing HLS-compilable Python. See [PYTHON_HLS_SPECIFICATION.md](../PYTHON_HLS_SPECIFICATION.md) for full details.

## What Works

| Construct | Example |
|-----------|---------|
| Functions | `def f(a, b): return a + b` |
| `if` / `elif` / `else` | `if x > 0: y = 1` |
| `for` over `range()` | `for i in range(n): sum += a[i]` |
| `while` | `while b: a, b = b, a % b` |
| Tuple unpacking | `a, b = b, a % b` |
| Arithmetic | `+`, `-`, `*`, `//`, `%`, `**` |
| Fixed-size arrays | `a = [0] * 8` |
| Array indexing | `a[i]`, `m[i][j]` |
| Comparisons | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Bitwise | `&`, `|`, `^`, `<<`, `>>` |

## What Does Not Work

- `*args`, `**kwargs`, default parameters
- `lambda`, classes, `import` (except `math`)
- Dynamic memory (`malloc`, `list.append` at runtime)
- Recursion
- `try`/`except`, `async`, generators
- Float division with dynamic operands (prefer `//` for integers)

## Trading Kernel Patterns

- **Technical indicators**: EMA, MACD, RSI – single-step updates with recursive equations
- **Signal processing**: FIR filters, dot product, FFT – fixed loops over arrays
- **Linear algebra**: Matrix multiply, covariance – nested loops with fixed bounds
- **Control flow**: GCD, Bellman-Ford – `while` and conditionals

## RTL Verification

When [Verilator](https://verilator.org) is installed, run `hls.verify_rtl()` to compare Python output with Verilog simulation. Kernels marked **RTL Verified** in the demo table pass this check.
