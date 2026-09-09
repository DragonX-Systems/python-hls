"""
FIR filter - Signal pipelines for market data, feed handlers.
Fixed-size 8-tap filter for HLS compatibility.
"""

def fir_filter(x, h, y, N, M):
    """Apply FIR filter. N=8, M=8 for fixed-size demo."""
    for n in range(N):
        y[n] = 0
        for k in range(M):
            if n - k >= 0:
                y[n] += h[k] * x[n - k]
