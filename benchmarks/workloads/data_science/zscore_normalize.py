"""
Feature Standardization (Z-Score Normalization).
Computes: z = ((x - mean) * 1000) / std_dev using integer square root.
"""


def zscore_normalize(x, out):
    """
    Z-Score Standardization of an 8-element feature vector.
    x: 8-element input feature vector
    out: 8-element standardized output vector
    """
    # Phase 1: Compute mean
    s = 0
    for i in range(8):
        s += x[i]
    mean = s // 8

    # Phase 2: Compute variance
    var_sum = 0
    for i in range(8):
        diff = x[i] - mean
        var_sum += diff * diff
    variance = var_sum // 8

    # Phase 3: Integer square root for standard deviation
    std = variance
    if std > 0:
        for _ in range(6):
            std = (std + variance // std) // 2
    if std == 0:
        std = 1

    # Phase 4: Standardize features scaled by 1000
    for i in range(8):
        out[i] = ((x[i] - mean) * 1000) // std
