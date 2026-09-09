"""
Covariance - Portfolio risk, factor models.
Simplified: fixed-size (N=8) covariance between two return series.
cov(a,b) = sum((a[i]-mean_a)*(b[i]-mean_b)) / (n-1). Integer arithmetic.
"""


def covariance_8(a, b):
    """Compute sample covariance between two length-8 arrays. Fixed-point friendly."""
    n = 8
    sum_a = 0
    sum_b = 0
    for i in range(n):
        sum_a = sum_a + a[i]
        sum_b = sum_b + b[i]
    mean_a = sum_a // n
    mean_b = sum_b // n
    cov_sum = 0
    for i in range(n):
        cov_sum = cov_sum + (a[i] - mean_a) * (b[i] - mean_b)
    return cov_sum // (n - 1)
