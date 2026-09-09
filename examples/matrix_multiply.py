"""
Matrix multiplication example with explicit memory allocation.
This example demonstrates how to use scratchpad memory for large arrays.
"""

def matrix_multiply(a, b, c, size):
    """
    Matrix multiplication using scratchpad memory for large arrays.
    
    Args:
        a: First input matrix (size x size)
        b: Second input matrix (size x size)
        c: Output matrix (size x size)
        size: Matrix dimension
    """
    # Use tiling to improve memory access patterns
    tile_size = 16
    
    # Initialize large intermediate results in scratchpad memory
    # These arrays will be automatically allocated to scratchpad memory
    # due to their large size
    partial_sums = [[0 for _ in range(size)] for _ in range(size)]
    
    # Tiled matrix multiplication
    for i_tile in range(0, size, tile_size):
        for j_tile in range(0, size, tile_size):
            for k_tile in range(0, size, tile_size):
                # Process each tile
                for i in range(i_tile, min(i_tile + tile_size, size)):
                    for j in range(j_tile, min(j_tile + tile_size, size)):
                        sum_val = partial_sums[i][j]
                        for k in range(k_tile, min(k_tile + tile_size, size)):
                            sum_val += a[i][k] * b[k][j]
                        partial_sums[i][j] = sum_val
    
    # Copy result to output matrix
    for i in range(size):
        for j in range(size):
            c[i][j] = partial_sums[i][j]
    
    return c 