"""
FIR filter example for Python-HLS.
"""

def fir_filter(x, h, y, N, M):
    """
    Apply a FIR filter to an input signal.
    
    Args:
        x: Input signal array
        h: Filter coefficients array
        y: Output signal array
        N: Length of input signal
        M: Length of filter (number of taps)
    """
    for n in range(N):
        y[n] = 0
        for k in range(M):
            if n - k >= 0:
                y[n] += h[k] * x[n - k] 