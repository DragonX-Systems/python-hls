"""
Refactored GCD - same algorithm, different variable names.
Used to test verify-equivalence CLI.
"""

def gcd(x, y):
    """GCD using Euclidean algorithm (refactored variable names)."""
    while y:
        x, y = y, x % y
    return x
