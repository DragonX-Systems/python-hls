"""
Example implementation of the Mentor SpMM architecture using Python HLS streaming interfaces.

This demonstrates how to use the streaming components (FIFOs, crossbars) to implement
a four-stage pipeline for sparse matrix-matrix multiplication:
1. Read stage: loads matrix elements and streaming them to multiplication units
2. Multiplication stage: performs element-wise multiplication
3. Accumulation stage: accumulates results for each output element
4. Write stage: writes results back to memory

The architecture uses FIFOs between stages and crossbars for flexible routing.
"""

# Type hints via comments instead of imports for HLS compatibility
# sparse_matrix: List[float], dense_matrix: List[float], 
# batch_size: int = 16, num_units: int = 4 -> Tuple[List[float], List[float]]
def read_stage(sparse_matrix, dense_matrix, batch_size=16, num_units=4):
    """
    Read stage: loads matrix elements and streams them to multiplication units.
    
    Args:
        sparse_matrix: Sparse matrix in CSC format
        dense_matrix: Dense matrix
        batch_size: Batch size for reading elements
        num_units: Number of multiplication units
        
    Returns:
        Tuple of sparse elements and dense elements
    """
    # pragma hls fifo sparse_fifo(depth=32, width=32)
    # pragma hls fifo dense_fifo(depth=32, width=32)
    # pragma hls crossbar read_xbar(inputs=1, outputs=4)
    
    sparse_elements = [0.0] * batch_size  # pragma hls stream sparse_stream(direction=out)
    dense_elements = [0.0] * batch_size   # pragma hls stream dense_stream(direction=out)
    
    for b in range(0, len(sparse_matrix), batch_size):
        batch_end = min(b + batch_size, len(sparse_matrix))
        batch_sparse = sparse_matrix[b:batch_end]
        batch_dense = dense_matrix[b:batch_end]
        
        # Perform the actual read operation
        for i in range(len(batch_sparse)):
            sparse_elements[i] = batch_sparse[i]  # pragma hls fifo_write sparse_fifo
            dense_elements[i] = batch_dense[i]    # pragma hls fifo_write dense_fifo
    
    return sparse_elements, dense_elements

# sparse_elements: List[float], dense_elements: List[float], num_units: int = 4 -> List[float]
def multiply_stage(sparse_elements, dense_elements, num_units=4):
    """
    Multiplication stage: performs element-wise multiplication of matrix elements.
    
    Args:
        sparse_elements: Elements from sparse matrix
        dense_elements: Elements from dense matrix
        num_units: Number of multiplication units
        
    Returns:
        Multiplication results
    """
    # pragma hls fifo mult_fifo(depth=16, width=32)
    # pragma hls crossbar mult_xbar(inputs=4, outputs=4)
    
    sparse_inputs = [0.0] * len(sparse_elements)  # pragma hls stream sparse_in(direction=in)
    dense_inputs = [0.0] * len(dense_elements)    # pragma hls stream dense_in(direction=in)
    
    # Output multiplication results
    mult_results = [0.0] * len(sparse_elements)  # pragma hls stream mult_out(direction=out)
    
    # Read from input FIFOs
    for i in range(len(sparse_elements)):
        sparse_inputs[i] = sparse_elements[i]  # pragma hls fifo_read sparse_fifo
        dense_inputs[i] = dense_elements[i]    # pragma hls fifo_read dense_fifo
    
    # Perform multiplication in parallel units
    for i in range(0, len(sparse_inputs), num_units):
        end = min(i + num_units, len(sparse_inputs))
        for j in range(i, end):
            # Multiply the elements
            result = sparse_inputs[j] * dense_inputs[j]
            mult_results[j] = result  # pragma hls fifo_write mult_fifo
    
    return mult_results

# mult_results: List[float], row_indices: List[int], output_size: int, num_units: int = 4 -> List[float]
def accumulate_stage(mult_results, row_indices, output_size, num_units=4):
    """
    Accumulation stage: accumulates multiplication results for each output element.
    
    Args:
        mult_results: Results from multiplication stage
        row_indices: Row indices for sparse matrix elements
        output_size: Size of output vector
        num_units: Number of accumulation units
        
    Returns:
        Accumulated results
    """
    # pragma hls fifo accum_fifo(depth=32, width=32)
    # pragma hls crossbar accum_xbar(inputs=4, outputs=4)
    
    mult_inputs = [0.0] * len(mult_results)  # pragma hls stream mult_in(direction=in)
    
    # Output accumulated results
    accum_results = [0.0] * output_size  # pragma hls stream accum_out(direction=out)
    
    # Read from multiplication FIFO
    for i in range(len(mult_results)):
        mult_inputs[i] = mult_results[i]  # pragma hls fifo_read mult_fifo
    
    # Distribute to accumulation units based on row indices
    for i in range(min(len(mult_inputs), len(row_indices))):
        row = row_indices[i] % output_size  # Ensure row index is within bounds
        # Add to the appropriate accumulation unit based on row index
        accum_results[row] += mult_inputs[i]  # pragma hls fifo_write accum_fifo
    
    return accum_results

# accum_results: List[float], output_matrix: List[float] -> List[float]
def write_stage(accum_results, output_matrix):
    """
    Write stage: writes accumulated results back to memory.
    
    Args:
        accum_results: Accumulated results from previous stage
        output_matrix: Output matrix to write results to
        
    Returns:
        Updated output matrix
    """
    # pragma hls fifo write_fifo(depth=16, width=32)
    
    accum_inputs = [0.0] * len(accum_results)  # pragma hls stream accum_in(direction=in)
    
    # Read from accumulation FIFO
    for i in range(len(accum_results)):
        accum_inputs[i] = accum_results[i]  # pragma hls fifo_read accum_fifo
    
    # Write to output matrix
    for i in range(len(accum_inputs)):
        output_matrix[i] = accum_inputs[i]  # pragma hls fifo_write write_fifo
    
    return output_matrix

# sparse_matrix: List[float], dense_matrix: List[float], row_indices: List[int], output_size: int -> List[float]
def mentor_spmm(sparse_matrix, dense_matrix, row_indices, output_size):
    """
    Mentor SpMM accelerator implementation using a four-stage pipeline.
    
    Args:
        sparse_matrix: Sparse matrix in CSC format
        dense_matrix: Dense matrix
        row_indices: Row indices for sparse matrix elements
        output_size: Size of output vector
        
    Returns:
        Output matrix
    """
    # pragma hls channel read_to_mult(source=read_stage, destination=multiply_stage)
    # pragma hls channel mult_to_accum(source=multiply_stage, destination=accumulate_stage)
    # pragma hls channel accum_to_write(source=accumulate_stage, destination=write_stage)
    
    # Initialize output matrix
    output_matrix = [0.0] * output_size
    
    # Ensure row_indices has at least as many elements as sparse_matrix
    if len(row_indices) < len(sparse_matrix):
        # Extend row_indices by repeating elements if needed
        row_indices = row_indices * ((len(sparse_matrix) + len(row_indices) - 1) // len(row_indices))
        row_indices = row_indices[:len(sparse_matrix)]
    
    # Stage 1: Read elements from matrices
    sparse_elements, dense_elements = read_stage(sparse_matrix, dense_matrix)
    
    # Stage 2: Multiply elements
    mult_results = multiply_stage(sparse_elements, dense_elements)
    
    # Stage 3: Accumulate results
    accum_results = accumulate_stage(mult_results, row_indices, output_size)
    
    # Stage 4: Write results to memory
    output_matrix = write_stage(accum_results, output_matrix)
    
    return output_matrix

if __name__ == "__main__":
    # Example sparse matrix in CSC format
    sparse_matrix = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    dense_matrix = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    row_indices = [0, 2, 1, 3, 0, 2, 1, 3]
    output_size = 4
    
    # Run the Mentor SpMM accelerator
    result = mentor_spmm(sparse_matrix, dense_matrix, row_indices, output_size)
    print("SpMM result:", result) 