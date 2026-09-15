"""
Multi-Feature Sample Covariance Matrix.
Computes a 4x4 covariance matrix from 4 features across 8 observations.
"""


def covariance_matrix(data, cov):
    """
    Compute 4x4 Sample Covariance Matrix from 4 features and 8 observations.
    data: 4 features x 8 observations
    cov: 4x4 sample covariance matrix
    """
    # Step 1: Compute mean per feature
    means = [0] * 4
    for f in range(4):
        s = 0
        for t in range(8):
            s += data[f][t]
        means[f] = s // 8

    # Step 2: Compute pairwise sample covariances
    for f1 in range(4):
        for f2 in range(4):
            c_sum = 0
            for t in range(8):
                c_sum += (data[f1][t] - means[f1]) * (data[f2][t] - means[f2])
            cov[f1][f2] = c_sum // 7
