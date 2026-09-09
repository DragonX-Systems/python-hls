# def matrix_multiply(matrix_a, matrix_b):
#     """
#     Multiply two 32x32 matrices together.
#     Designed to be suitable for HLS synthesis.
    
#     Args:
#         matrix_a: First 32x32 matrix represented as a flat list [1024 elements]
#         matrix_b: Second 32x32 matrix represented as a flat list [1024 elements]
        
#     Returns:
#         Resulting 32x32 matrix as a flat list [1024 elements]
#     """
#     # Memory size annotations for the HLS scheduler
#     MATRIX_SIZE = 32
#     TOTAL_ELEMENTS = MATRIX_SIZE * MATRIX_SIZE  # 1024 elements
    
#     matrix_a_memory_size = TOTAL_ELEMENTS * 4  # 4 bytes per float
#     matrix_b_memory_size = TOTAL_ELEMENTS * 4  # 4 bytes per float
    
#     # Output matrix
#     # pragma hls memory_type RAM
#     result = [0.0] * TOTAL_ELEMENTS
#     result_memory_size = TOTAL_ELEMENTS * 4  # 4 bytes per float
    
#     # Pragma: Enable pipeline optimization for this function
#     # pragma hls pipeline enable
    
#     # Pragma: Matrix operation hint
#     # pragma hls matrix_operation matmul
    
#     # Tiled matrix multiplication for better cache performance
#     TILE_SIZE = 8
    
#     # pragma loop_count 4
#     for i_tile in range(0, MATRIX_SIZE, TILE_SIZE):
#         # pragma loop_count 4
#         for j_tile in range(0, MATRIX_SIZE, TILE_SIZE):
#             # pragma loop_count 4
#             for k_tile in range(0, MATRIX_SIZE, TILE_SIZE):
                
#                 # Process tile
#                 # pragma hls pipeline enable
#                 # pragma loop_count 8
#                 for i in range(i_tile, min(i_tile + TILE_SIZE, MATRIX_SIZE)):
#                     # pragma loop_count 8
#                     for j in range(j_tile, min(j_tile + TILE_SIZE, MATRIX_SIZE)):
#                         sum_val = result[i * MATRIX_SIZE + j]
                        
#                         # pragma hls unroll factor=4
#                         # pragma loop_count 8
#                         for k in range(k_tile, min(k_tile + TILE_SIZE, MATRIX_SIZE)):
#                             sum_val += matrix_a[i * MATRIX_SIZE + k] * matrix_b[k * MATRIX_SIZE + j]
                        
#                         result[i * MATRIX_SIZE + j] = sum_val
    
#     return result


def matrix_multiply_looped(matrix_a, matrix_b):
    """
    Multiply two 32x32 matrices using simple loops.
    This version demonstrates how loops would be implemented,
    which provides a different synthesis structure for HLS.
    
    Args:
        matrix_a: First 32x32 matrix represented as a flat list [1024 elements]
        matrix_b: Second 32x32 matrix represented as a flat list [1024 elements]
        
    Returns:
        Resulting 32x32 matrix as a flat list [1024 elements]
    """
    # Memory size annotations for the HLS scheduler
    MATRIX_SIZE = 32
    TOTAL_ELEMENTS = MATRIX_SIZE * MATRIX_SIZE  # 1024 elements
    
    matrix_a_memory_size = TOTAL_ELEMENTS * 4  # 4 bytes per float
    matrix_b_memory_size = TOTAL_ELEMENTS * 4  # 4 bytes per float
    
    # Output matrix
    # pragma hls memory_type RAM
    result = [0.0] * TOTAL_ELEMENTS
    result_memory_size = TOTAL_ELEMENTS * 4  # 4 bytes per float
    
    # Compute matrix multiplication using loops
    # pragma hls pipeline enable
    # pragma loop_count 32
    for i in range(MATRIX_SIZE):
        # pragma loop_count 32
        for j in range(MATRIX_SIZE):
            sum_val = 0.0
            # pragma loop_count 32
            # pragma hls unroll factor=4
            for k in range(MATRIX_SIZE):
                sum_val += matrix_a[i * MATRIX_SIZE + k] * matrix_b[k * MATRIX_SIZE + j]
            result[i * MATRIX_SIZE + j] = sum_val
    
    return result


# # Test function
# def test_matrix_multiplication():
#     """Test the matrix multiplication functions"""
#     MATRIX_SIZE = 32
#     TOTAL_ELEMENTS = MATRIX_SIZE * MATRIX_SIZE
    
#     # Create test matrices with simple pattern
#     a = []
#     b = []
#     for i in range(TOTAL_ELEMENTS):
#         a.append(float(i % 10 + 1))  # Values 1-10 repeating
#         b.append(float((i + 5) % 10 + 1))  # Values 6-10, 1-5 repeating
    
#     # Test direct computation
#     result1 = matrix_multiply(a, b)
#     print(f"Tiled result sample: {result1[:5]} ... {result1[-5:]}")
    
#     # Test looped computation
#     result2 = matrix_multiply_looped(a, b)
#     print(f"Looped result sample: {result2[:5]} ... {result2[-5:]}")
    
#     # Verify results match
#     matches = True
#     for i in range(TOTAL_ELEMENTS):
#         if abs(result1[i] - result2[i]) > 1e-6:
#             matches = False
#             break
    
#     assert matches, "Results from both implementations should match"
#     print("Tests passed!")


# if __name__ == "__main__":
#     test_matrix_multiplication() 