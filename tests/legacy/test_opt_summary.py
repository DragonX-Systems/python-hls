import os
from python_hls import HLS

# Create a sample Python file with some optimizable code
sample_code = '''
def matrix_multiply(a, b, c, n, m, p):
    """
    Matrix multiplication C = A * B
    A is n x m
    B is m x p
    C is n x p
    """
    
    # pragma hls unroll=full
    for i in range(n):
        for j in range(p):
            c[i][j] = 0
            # pragma hls unroll=4
            for k in range(m):
                c[i][j] += a[i][k] * b[k][j]
                
    return c

def main():
    n = 4
    m = 4
    p = 4
    
    # Initialize matrices
    a = [[0 for _ in range(m)] for _ in range(n)]
    b = [[0 for _ in range(p)] for _ in range(m)]
    c = [[0 for _ in range(p)] for _ in range(n)]
    
    # Fill with some values
    for i in range(n):
        for j in range(m):
            a[i][j] = i + j
    
    for i in range(m):
        for j in range(p):
            b[i][j] = i * j + 1
    
    # Compute constant expressions
    x = 5 + 3  # This should be folded
    y = 10 * 2  # This should be folded
    z = x + y  # This should be folded
    
    # Dead code (not used)
    unused_var = 100
    another_unused = 200
    
    # Common subexpression
    expr1 = a[0][0] * b[0][0] + a[0][1] * b[1][0]
    expr2 = a[0][0] * b[0][0] + a[0][1] * b[1][0]  # Same as expr1
    
    # Call the matrix multiplication
    result = matrix_multiply(a, b, c, n, m, p)
    
    return result
'''

# Save the sample code to a file
with open('sample_code.py', 'w') as f:
    f.write(sample_code)

print("Created sample Python file with optimizable code.")

# Create HLS compiler with different optimization levels to compare
for opt_level in [1, 2, 3]:
    print(f"\n\n===== TESTING WITH OPTIMIZATION LEVEL {opt_level} =====")
    hls = HLS(optimization_level=opt_level)
    
    # Compile the sample code
    print(f"Compiling with optimization level {opt_level}...")
    hls.compile('sample_code.py')
    
    # Get the optimization summary
    opt_summary = hls.get_optimization_summary()
    
    # Print the summary
    print("\nOPTIMIZATION SUMMARY OUTPUT:")
    print("-" * 50)
    print(opt_summary)
    print("-" * 50)

# Clean up
os.remove('sample_code.py')
print("\nTest completed and sample file removed.") 