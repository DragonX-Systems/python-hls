
def gcd(a, b):
    """
    Calculate the greatest common divisor of two integers.
    """
    while b:
        a, b = b, a % b
    return a
