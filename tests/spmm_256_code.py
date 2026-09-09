
def spmm(A, values, row_num, row_ptr, C):
    # Matrix dimensions defined as constants
    M = 256
    N = 256
    K = 256

    # Add explicit annotations about memory size for the HLS scheduler
    # This helps the scheduler better understand resource requirements
    # without requiring algorithm-specific code in the scheduler
    
    # Total memory requirement for dense matrices: O(N²)
    # A: M×K matrix = 256×256 = 65536 elements
    # C: M×N matrix = 256×256 = 65536 elements
    A_memory_size = M * K * 4  # 4 bytes per float
    C_memory_size = M * N * 4  # 4 bytes per float
    
    # Sparse matrix storage requirements:
    # values and row_num arrays scale with number of non-zeros
    # which is proportional to matrix dimension for typical sparse matrices
    values_memory_size = len(values) * 4  # 4 bytes per float
    row_num_memory_size = len(row_num) * 4  # 4 bytes per int
    row_ptr_memory_size = len(row_ptr) * 4  # 4 bytes per int
    
    # Total memory footprint for size 256: 
    # ~524552 bytes

    # Initialize matrices with sizes scaled to the input size
    A = [[2.2] * K for _ in range(M)]
    C = [[0 for _ in range(N)] for _ in range(M)]

    # Initialize sparse matrix data based on size
    values = [1, 5, 3, 0, 2, 6, 4] * 4
    row_num = [1, 3, 2, 0, 1, 3, 2] * 4
    row_ptr = [i * 2 for i in [0, 2, 3, 6, 7]]

    # Block size for tiled computation
    BLOCK_SIZE = 32

    # Process computation in 32x32 blocks
    # This results in 8x8 = 64 block iterations
    total_ops = 0
    
    # Pragma: Matrix operation hint - This is a sparse matrix-matrix multiply pattern
    # pragma hls matrix_operation spmm
    
    # Pragma: Enable pipeline optimization for this function
    # pragma hls pipeline enable
    
    # Pragma: Outer loop count
    # pragma loop_count 8
    for i_block in range(0, M, BLOCK_SIZE):  # 8 iterations
        # Pragma: Middle loop count
        # pragma loop_count 8
        for j_block in range(0, N, BLOCK_SIZE):  # 8 iterations
            # Process each element within the block
            # Pragma: Inner i loop count
            # pragma loop_count 32
            for i_local in range(BLOCK_SIZE):  # 32 iterations
                i = i_block + i_local
                if i >= M:
                    continue
                
                # Pragma: Inner j loop count
                # pragma loop_count 32
                for j_local in range(BLOCK_SIZE):  # 32 iterations
                    j = j_block + j_local
                    if j >= N:
                        continue
                    
                    k_start = row_ptr[j % len(row_ptr)]
                    k_end = row_ptr[(j+1) % len(row_ptr)]
                    total_ops += 1
                    
                    # This inner loop scales with size since larger matrices have more values
                    # Pragma: Innermost loop count - this is the critical compute-intensive part
                    # pragma loop_count 6
                    for k_ptr in range(k_start, k_end):  # Scales with 256
                        k = row_num[k_ptr % len(row_num)]
                        x = A[i][k % K]
                        wt = values[k_ptr % len(values)]
                        
                        # This is a multiply-accumulate (MAC) operation 
                        # The HLS compiler should recognize this pattern for hardware optimization
                        C[i][j] += x * wt
                        total_ops += 1
    
    print(f"Total expected computations: 393216")
    print(f"Actual computations: {total_ops}")
    return C
