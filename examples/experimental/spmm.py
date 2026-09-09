M = 256
N = 256
K = 256
A = [[2.2] * M] * K
C = [[0 for _ in range(N)] for _ in range(M)]

values = [1, 5, 3, 0, 2, 6, 4]
row_num = [1, 3, 2, 0, 1, 3, 2]
row_ptr = [0, 2, 3, 6, 7]

# Block size for tiled computation
BLOCK_SIZE = 32

# Process computation in 32x32 blocks
for i_block in range(0, M, BLOCK_SIZE):
    for j_block in range(0, N, BLOCK_SIZE):
        # Process each element within the block
        for i_local in range(BLOCK_SIZE):
            i = i_block + i_local
            if i >= M:
                continue
                
            for j_local in range(BLOCK_SIZE):
                j = j_block + j_local
                if j >= N:
                    continue
                    
                k_start = row_ptr[j]
                k_end = row_ptr[j+1]
                for k_ptr in range(k_start, k_end):
                    k = row_num[k_ptr]
                    x = A[i][k]
                    wt = values[k_ptr]
                    C[i][j] += x * wt