"""
RSI (Relative Strength Index) - Technical indicator.
RSI = 100 - 100/(1 + RS), where RS = avg_gain / avg_loss.
Simplified: single update given previous avg gain/loss and price change.
"""

def rsi_update(avg_gain_prev, avg_loss_prev, price_change, alpha):
    """
    Single RSI update using Wilder smoothing (alpha=1/14).
    If price_change > 0: gain = price_change, loss = 0
    Else: gain = 0, loss = -price_change
    avg_gain = alpha * gain + (1-alpha) * avg_gain_prev
    """
    if price_change > 0:
        gain = price_change
        loss = 0
    else:
        gain = 0
        loss = -price_change
    avg_gain = alpha * gain + (1 - alpha) * avg_gain_prev
    avg_loss = alpha * loss + (1 - alpha) * avg_loss_prev
    if avg_loss == 0:
        rs = 1000  # Avoid div by zero; RSI -> 100
    else:
        rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return avg_gain, avg_loss, rsi
