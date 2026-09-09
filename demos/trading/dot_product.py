"""
Dot product - Tick-to-trade latency-critical path.
# pragma hls latency 8
"""

def dot_product(a, b, n):
    """Dot product of vectors a and b, length n. Latency-critical for tick processing."""
    # pragma hls latency 8
    result = 0
    for i in range(n):
        result += a[i] * b[i]
    return result
