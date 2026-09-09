import numpy as np

def streaming_construction(ptr, idx, val, K, NNZ, D, B):
    """
    Streaming Construction for Sparse Matrices
    
    Args:
        ptr: Column pointers array (CSC format)
        idx: Row indices array (CSC format)
        val: Non-zero values array (CSC format)
        K: Number of columns
        NNZ: Number of non-zero elements
        D: Distance parameter for padding
        B: Block size parameter
    
    Returns:
        pidx: Processed row indices
        pval: Processed values
    """
    # Initialize processed arrays
    pidx = idx.copy()
    pval = val.copy()
    
    # Make sure arrays are large enough to handle insertions
    # Extend arrays with padding to accommodate insertions
    extension = NNZ + K + D + 1  # Add extra space
    pidx = np.pad(pidx, (0, extension), 'constant', constant_values=-4)
    pval = np.pad(pval, (0, extension), 'constant', constant_values=0)
    
    # Insert the Rest elements
    for i in range(1, K + 2):  # 1 to K+1 inclusive
        if i-1 < len(ptr):
            insert_rest(pidx, pval, ptr[i-1] + i - 1, 1)
    
    # Mark the end of the array
    pidx[NNZ + K] = -4
    
    # Insert the Block elements
    r = 0
    while r < len(pidx) and pidx[r] != -4:
        if not is_control_element(pidx[r]) and r+1 < len(pidx) and not is_control_element(pidx[r + 1]):
            block_count = int(pval[r + 1] / B) - int(pval[r] / B)
            if block_count > 0:
                insert_block(pidx, pval, r, block_count)
        r += 1
    
    # Insert the Padding elements
    r = 0
    while r < len(pidx) and pidx[r] != -4:
        if not is_control_element(pidx[r]):
            for i in range(r + 1, min(r + D + 2, len(pidx))):  # r+1 to r+D+1 inclusive
                if pval[r] == pval[i]:
                    padding_count = D - (i - r)
                    if padding_count > 0:
                        insert_padding(pidx, pval, i, padding_count)
        r += 1
    
    # Trim arrays to remove unused padding at the end
    end_idx = np.where(pidx == -4)[0][0] + 1
    return pidx[:end_idx], pval[:end_idx]

def is_control_element(value):
    """
    Check if the given value represents a control element.
    
    Args:
        value: Value to check
    
    Returns:
        bool: True if it's a control element, False otherwise
    """
    # Control elements are marked with negative values
    # -1: Rest element
    # -2: Block element
    # -3: Padding element
    # -4: End marker
    return value < 0

def insert_rest(pidx, pval, position, value):
    """
    Insert a Rest element at the specified position.
    
    Args:
        pidx: Processed row indices array
        pval: Processed values array
        position: Position to insert the element
        value: Value to insert
    """
    # Shift elements right to make space
    if position < len(pidx):
        # Move all elements from position onwards one step to the right
        for i in range(len(pidx)-2, position-1, -1):
            pidx[i+1] = pidx[i]
            pval[i+1] = pval[i]
        
        # Insert the Rest element
        pidx[position] = -1  # Using -1 to mark Rest elements
        pval[position] = value

def insert_block(pidx, pval, position, count):
    """
    Insert Block elements after the specified position.
    
    Args:
        pidx: Processed row indices array
        pval: Processed values array
        position: Position after which to insert the elements
        count: Number of elements to insert
    """
    # Shift elements right to make space for 'count' elements
    for c in range(count):
        pos = position + 1 + c
        # Move all elements from pos onwards one step to the right
        for i in range(len(pidx)-2, pos-1, -1):
            pidx[i+1] = pidx[i]
            pval[i+1] = pval[i]
        
        # Insert the Block element
        pidx[pos] = -2  # Using -2 to mark Block elements
        pval[pos] = pval[position]

def insert_padding(pidx, pval, position, count):
    """
    Insert Padding elements after the specified position.
    
    Args:
        pidx: Processed row indices array
        pval: Processed values array
        position: Position after which to insert the elements
        count: Number of elements to insert
    """
    # Shift elements right to make space for 'count' elements
    for c in range(count):
        pos = position + 1 + c
        # Move all elements from pos onwards one step to the right
        for i in range(len(pidx)-2, pos-1, -1):
            pidx[i+1] = pidx[i]
            pval[i+1] = pval[i]
        
        # Insert the Padding element
        pidx[pos] = -3  # Using -3 to mark Padding elements
        pval[pos] = pval[position]

# Example usage
if __name__ == "__main__":
    # Example sparse matrix in CSC format
    ptr = np.array([0, 2, 4, 6, 8])  # Column pointers
    idx = np.array([0, 2, 1, 3, 0, 2, 1, 3])  # Row indices
    val = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])  # Values
    
    K = 4  # Number of columns
    NNZ = 8  # Number of non-zero elements
    D = 2  # Distance parameter
    B = 2  # Block size parameter
    
    pidx, pval = streaming_construction(ptr, idx, val, K, NNZ, D, B)
    
    print("Processed row indices (pidx):", pidx)
    print("Processed values (pval):", pval) 