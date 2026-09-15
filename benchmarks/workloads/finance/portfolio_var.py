"""
Portfolio Value-at-Risk (VaR) and Volatility.
Computes parametric portfolio variance w^T * Sigma * w, integer volatility, and 99% VaR.
"""


def portfolio_var(weights, cov_matrix):
    """
    Compute 4-asset portfolio Value-at-Risk (VaR) at 99% confidence level.
    weights: asset allocations in basis points (10000 = 100%).
    cov_matrix: 4x4 covariance matrix in scaled integer form.
    """
    port_var = 0
    for i in range(4):
        row_sum = 0
        for j in range(4):
            row_sum += cov_matrix[i][j] * weights[j]
        port_var += weights[i] * (row_sum // 10000)

    x = port_var // 10000
    if x <= 0:
        return 0

    r = x
    for _ in range(8):
        if r > 0:
            r = (r + x // r) // 2

    # 99% VaR = 2.326 * r ~= (r * 233) // 100
    var_99 = (r * 233) // 100
    return var_99
