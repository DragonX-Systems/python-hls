"""
GCD - Control flow and equivalence/refactor demo for trading firms.
Greatest common divisor: baseline for refactor-safety verification.
"""

def gcd(a, b):
    """Calculate GCD using Euclidean algorithm."""
    while b:
        a, b = b, a % b
    return a
