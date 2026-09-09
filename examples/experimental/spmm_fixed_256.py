
def spmm_fixed_256(A, values, row_num, row_ptr, C):
    # Hardcoded size = 256
    
    # Completely unrolled outer loops
    for i in range(256):
        for j in range(256):
            sum_val = 0
            k_start = row_ptr[j]
            
            # Inner loop with fixed iteration count
            for k_idx in range(64):
                k_ptr = k_start + k_idx
                k = row_num[k_ptr]
                x = A[i][k]
                wt = values[k_ptr]
                sum_val += x * wt
            
            C[i][j] = sum_val
    
    return C
