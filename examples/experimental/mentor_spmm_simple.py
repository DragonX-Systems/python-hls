"""
Enhanced implementation of the Mentor SpMM architecture using Python HLS.

This demonstrates a four-stage pipeline for sparse matrix-matrix multiplication
with explicit FIFOs for inter-stage communication and crossbars for data routing.
"""

def spmm(sparse_matrix, dense_matrix, row_indices, output_size):
    """
    A Mentor SpMM accelerator implementation with explicit FIFOs and crossbars.
    
    Args:
        sparse_matrix: Sparse matrix elements
        dense_matrix: Dense matrix elements 
        row_indices: Row indices for sparse matrix elements
        output_size: Size of output matrix
        
    Returns:
        Output matrix
    """
    # Initialize output matrix
    output = [0.0] * output_size
    
    #pragma hls pipeline enable
    
    # Define FIFOs with proper syntax according to the parser
    #pragma hls fifo sparse_fifo(depth=32, width=32)
    #pragma hls fifo dense_fifo(depth=32, width=32)
    #pragma hls fifo indices_fifo(depth=32, width=32)
    #pragma hls fifo mult_fifo(depth=32, width=32)
    #pragma hls fifo output_fifo(depth=32, width=32)
    
    # Define crossbars with proper syntax according to the parser
    #pragma hls crossbar read_crossbar(inputs=1, outputs=3)
    #pragma hls crossbar mult_crossbar(inputs=3, outputs=1)
    #pragma hls crossbar accumulate_crossbar(inputs=2, outputs=4)
    #pragma hls crossbar write_crossbar(inputs=4, outputs=4)
    
    # Allocate storage for FIFOs
    sparse_fifo = [0.0] * len(sparse_matrix)
    dense_fifo = [0.0] * len(dense_matrix)
    indices_fifo = [0] * len(row_indices)
    mult_fifo = [0.0] * len(sparse_matrix)
    output_fifo = [0.0] * output_size
    
    # Stage 1: Load elements
    #pragma hls stage read_stage
    for i in range(len(sparse_matrix)):
        # Load data
        sparse_val = sparse_matrix[i]
        dense_val = dense_matrix[i]
        row_idx = row_indices[i] if i < len(row_indices) else 0
        
        # Push to FIFOs with correct pragma syntax
        sparse_fifo[i] = sparse_val
        #pragma hls fifo_write sparse_fifo
        
        dense_fifo[i] = dense_val
        #pragma hls fifo_write dense_fifo
        
        indices_fifo[i] = row_idx
        #pragma hls fifo_write indices_fifo
    
    # Stage 2: Multiply elements
    #pragma hls stage multiply_stage
    for i in range(len(sparse_fifo)):
        # Pop from input FIFOs
        sparse_val = sparse_fifo[i]
        #pragma hls fifo_read sparse_fifo
        
        dense_val = dense_fifo[i]
        #pragma hls fifo_read dense_fifo
        
        # Perform multiplication
        result = sparse_val * dense_val
        
        # Push to output FIFO
        mult_fifo[i] = result
        #pragma hls fifo_write mult_fifo
    
    # Stage 3: Accumulate results
    #pragma hls stage accumulate_stage
    for i in range(len(mult_fifo)):
        # Pop from input FIFOs
        mult_val = mult_fifo[i]
        #pragma hls fifo_read mult_fifo
        
        row = indices_fifo[i] % output_size if i < len(indices_fifo) else 0
        #pragma hls fifo_read indices_fifo
        
        # Use crossbar to route multiplication result to correct output
        dest = row
        #pragma hls crossbar_route accumulate_crossbar(input=0, output=dest)
        output[row] += mult_val
    
    # Stage 4: Finalize results
    #pragma hls stage write_stage
    # Initialize result buffer
    result = [0.0] * output_size
    
    # Copy output through final crossbar to result buffer
    for i in range(output_size):
        #pragma hls crossbar_route write_crossbar(input=i, output=i)
        result[i] = output[i]
    
    return result

if __name__ == "__main__":
    # Example sparse matrix in CSC format
    sparse_matrix = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    dense_matrix = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    row_indices = [0, 2, 1, 3, 0, 2, 1, 3]
    output_size = 4
    
    # Run the SpMM
    result = spmm(sparse_matrix, dense_matrix, row_indices, output_size)
    print("SpMM result:", result) 