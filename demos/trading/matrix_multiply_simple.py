"""
Matrix multiply (fixed 4x4) - Factor models, covariance building block.
No list comprehensions; explicit loops for HLS.
"""

def matrix_multiply_simple(a, b, c, size):
    """C[i][j] = sum over k of A[i][k]*B[k][j]. size=4 for demo."""
    for i in range(size):
        for j in range(size):
            c[i][j] = 0
            for k in range(size):
                c[i][j] += a[i][k] * b[k][j]
