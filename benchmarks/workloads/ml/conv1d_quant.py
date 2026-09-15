"""
Quantized 1D Temporal Convolution with Residual Connection.
Commonly used in speech processing, audio filterbanks, and time-series feature extractors.
"""


def conv1d_quant(x, weights, bias, out):
    """
    1D Temporal Convolution with Residual Connection and ReLU.
    x: 16-sample input sequence
    weights: 4-tap filter coefficients
    bias: scalar bias
    out: 13-sample output sequence
    """
    for i in range(13):
        acc = bias
        for k in range(4):
            acc += x[i + k] * weights[k]
        # Residual addition from tap index 1 + clamp
        res = acc + x[i + 1]
        if res < 0:
            res = 0
        out[i] = res
