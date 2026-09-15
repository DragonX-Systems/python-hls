"""
Quantized Multi-Layer Perceptron (MLP) Layer.
Computes: y = ReLU(W * x + b) for fixed-point integer inference.
"""


def mlp_layer(x, w, b, y):
    """
    Quantized 4x4 Matrix-Vector MLP layer with bias addition and ReLU activation.
    x: 4-element input vector
    w: 4x4 weight matrix
    b: 4-element bias vector
    y: 4-element activated output vector
    """
    for i in range(4):
        acc = b[i]
        for j in range(4):
            acc += w[i][j] * x[j]
        if acc < 0:
            acc = 0
        y[i] = acc
