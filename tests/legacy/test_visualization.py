import os
import tempfile
from python_hls import HLS

def create_spmm_code(size=512):
    """Create SPMM code with the given matrix size"""
    # Scale parameters based on size
    block_size = 32 if size < 500 else 64
    num_blocks = (size + block_size - 1) // block_size  # Ceiling division
    
    # Add pragmas for loop counts
    code = f"""
def spmm(values, row_ptr, col_idx, x, C):
    # pragma loop_count 8
    for i in range(8):  # Iterate over row blocks
        # pragma loop_count 8 
        for j in range(8):  # Iterate over column blocks
            # pragma loop_count {num_blocks}
            for ii in range({num_blocks}):  # Iterate within row block
                # pragma loop_count {num_blocks}
                for jj in range({num_blocks}):  # Iterate within column block
                    # pragma loop_count 10
                    for k in range(row_ptr[i*{block_size}+ii], row_ptr[i*{block_size}+ii+1]):  # Iterate over non-zeros
                        col = col_idx[k]
                        if col >= j*{block_size} and col < (j+1)*{block_size}:
                            col_local = col - j*{block_size}
                            x_val = x[col]
                            wt = values[k]
                            C[i*{block_size}+ii][j*{block_size}+jj] += x_val * wt
    return C
"""
    return code

def main():
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create SPMM code for size 512
        code = create_spmm_code(512)
        spmm_file = os.path.join(temp_dir, "spmm_512.py")
        
        # Write the code to a file
        with open(spmm_file, "w") as f:
            f.write(code)
            
        print(f"Generated SPMM code in {spmm_file}")
        
        # Create HLS object and compile
        hls = HLS()
        hls.compile(spmm_file, target="verilog")
        
        # Generate visualizations
        netlist_image = "spmm_512_netlist_fixed.png"
        microarch_image = "spmm_512_microarch_fixed.png"
        
        hls.visualize_netlist(netlist_image)
        hls.visualize_netlist_microarch(microarch_image)
        
        print(f"Generated netlist visualization: {netlist_image}")
        print(f"Generated microarchitecture visualization: {microarch_image}")

if __name__ == "__main__":
    main() 