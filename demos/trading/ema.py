"""
EMA (Exponential Moving Average) - Technical indicator building block.
y[n] = alpha * x[n] + (1 - alpha) * y[n-1]
Used in MACD, RSI. Single-sample update for low-latency.
"""

def ema_update(y_prev, x, alpha):
    """Single EMA update step. y_new = alpha*x + (1-alpha)*y_prev."""
    return alpha * x + (1 - alpha) * y_prev
