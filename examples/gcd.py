"""
Greatest Common Divisor example for Python-HLS.
"""

def gcd(a, b):
    """
    Calculate the greatest common divisor of two integers.
    
    Args:
        a: First integer
        b: Second integer
        
    Returns:
        Greatest common divisor of a and b
    """
    while b:
        a, b = b, a % b
    return a 