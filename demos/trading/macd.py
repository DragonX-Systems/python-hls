"""
MACD (Moving Average Convergence Divergence) - Technical indicator.
30x FPGA speedup in literature. EMA-based: MACD = EMA12 - EMA26.
Single-step update for low-latency: given previous EMAs and new price.
"""

def macd_update(ema_fast_prev, ema_slow_prev, price, alpha_fast, alpha_slow):
    """
    Single MACD update step.
    EMA_new = alpha * price + (1 - alpha) * EMA_prev
    MACD = EMA_fast - EMA_slow
    Typical: alpha_fast=2/13, alpha_slow=2/27 for 12/26 period EMAs.
    """
    ema_fast = alpha_fast * price + (1 - alpha_fast) * ema_fast_prev
    ema_slow = alpha_slow * price + (1 - alpha_slow) * ema_slow_prev
    macd_line = ema_fast - ema_slow
    return ema_fast, ema_slow, macd_line
