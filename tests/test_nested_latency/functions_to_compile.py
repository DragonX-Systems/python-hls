"""
Python functions to compile for testing nested latency calculations.
"""

# Inner function with a simple loop
def inner_function(a, b):
    """Simple inner function with a loop."""
    result = 0
    # Loop 1 (innermost function)
    for i in range(10):
        result += a + b
    return result

# Middle function with nested loops and a call to inner_function
def middle_function(a, b):
    """Middle function with nested loops that calls inner_function."""
    result = 0
    # Loop 1 (in middle_function)
    for i in range(5):
        # Loop 2 (nested inside Loop 1)
        for j in range(3):
            result += a * b
        # Call to inner_function inside the loop
        result += inner_function(i, b)
    return result

# Outer function with deeply nested loops and a call to middle_function
def outer_function(a, b):
    """Outer function with deeply nested loops that calls middle_function."""
    result = 0
    # Loop 1 (outermost function)
    for i in range(3):
        # Loop 2 (nested inside Loop 1)
        for j in range(4):
            # Loop 3 (nested inside Loop 2)
            for k in range(2):
                result += a + b + i + j + k
            # Call to middle_function inside the nested loops
            result += middle_function(i, j)
    return result

# A main function that calls outer_function
def main():
    """Main function to test the nested loops and function calls."""
    a = 5
    b = 10
    return outer_function(a, b)

# When this module is executed directly, run the main function
if __name__ == "__main__":
    print(main()) 