import os
import sys
import time
import logging
import tempfile
import shutil
import traceback

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aes_large_size_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aes_large_size_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS

def create_aes_large_size_code(block_size=128):
    """Create AES implementation for a larger size with proper loop_count pragmas
    
    Args:
        block_size: Size of the blocks to process (must be multiple of 16)
    """
    return f"""
def aes_encrypt_large_size(plaintext, key):
    # This is a larger AES implementation that processes a larger block size
    # Block size: {block_size} bytes (multiple of 16-byte AES blocks)
    # Number of AES blocks: {block_size // 16}
    
    # Memory size annotations for the HLS scheduler
    plaintext_memory_size = {block_size}  # {block_size} bytes
    key_memory_size = 16  # 16 bytes
    
    # S-box lookup table
    # pragma hls memory_type ROM
    s_box = [
        0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
        0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
        0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
        0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
        0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
        0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
        0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
        0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
        0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
        0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
        0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
        0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
        0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
        0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
        0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
        0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
    ]
    s_box_memory_size = 256  # 256 bytes
    
    # Rcon lookup table
    # pragma hls memory_type ROM
    rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]
    rcon_memory_size = 10  # 10 bytes
    
    # Output ciphertext
    # pragma hls memory_type RAM
    ciphertext = [0] * {block_size}
    ciphertext_memory_size = {block_size}  # {block_size} bytes
    
    # Round keys (for all rounds)
    # pragma hls memory_type RAM
    expanded_key = [0] * 176  # 11 round keys * 16 bytes
    expanded_key_memory_size = 176  # 176 bytes
    
    # Temporary state array for each block
    # pragma hls memory_type RAM
    state = [0] * 16
    state_memory_size = 16  # 16 bytes
    
    def sub_bytes(state):
        # Substitute each byte in the state with its corresponding value in the S-box
        # pragma hls pipeline enable
        # pragma loop_count 16
        for i in range(16):
            state[i] = s_box[state[i]]
        return state
    
    def shift_rows(state):
        # Shift rows of the state matrix
        # Extract state into a 4x4 matrix
        matrix = [[0 for _ in range(4)] for _ in range(4)]
        # pragma loop_count 4
        for i in range(4):
            # pragma loop_count 4
            for j in range(4):
                matrix[i][j] = state[i + 4*j]
        
        # Perform the row shifts
        # pragma hls pipeline enable
        # pragma loop_count 4
        for i in range(4):
            # Shift row i by i positions
            row = [matrix[i][j] for j in range(4)]
            # pragma loop_count 4
            for j in range(4):
                matrix[i][j] = row[(j + i) % 4]
        
        # Convert back to 1D array
        # pragma loop_count 4
        for i in range(4):
            # pragma loop_count 4
            for j in range(4):
                state[i + 4*j] = matrix[i][j]
        
        return state
    
    def mix_columns(state):
        # Mix the columns of the state matrix
        
        # Extract state into a 4x4 matrix
        matrix = [[0 for _ in range(4)] for _ in range(4)]
        # pragma loop_count 4
        for i in range(4):
            # pragma loop_count 4
            for j in range(4):
                matrix[i][j] = state[i + 4*j]
        
        # Temporary array to hold the mixed columns
        mixed = [[0 for _ in range(4)] for _ in range(4)]
        
        # Mix each column
        # pragma hls pipeline enable
        # pragma loop_count 4
        for j in range(4):
            # Mix column operations - simplified version
            # Just capturing the pattern of operations
            mixed[0][j] = ((matrix[0][j] << 1) ^ matrix[1][j] ^ matrix[2][j] ^ matrix[3][j]) & 0xFF
            mixed[1][j] = (matrix[0][j] ^ (matrix[1][j] << 1) ^ matrix[2][j] ^ matrix[3][j]) & 0xFF
            mixed[2][j] = (matrix[0][j] ^ matrix[1][j] ^ (matrix[2][j] << 1) ^ matrix[3][j]) & 0xFF
            mixed[3][j] = (matrix[0][j] ^ matrix[1][j] ^ matrix[2][j] ^ (matrix[3][j] << 1)) & 0xFF
        
        # Convert back to 1D array
        # pragma loop_count 4
        for i in range(4):
            # pragma loop_count 4
            for j in range(4):
                state[i + 4*j] = mixed[i][j]
        
        return state
    
    def add_round_key(state, round_key, round_num):
        # XOR the state with the round key
        # pragma hls pipeline enable
        # pragma loop_count 16
        for i in range(16):
            state[i] ^= round_key[round_num * 16 + i]
        return state
    
    def expand_key(key):
        # Key expansion
        # Copy the initial key
        # pragma hls unroll factor=4
        # pragma loop_count 16
        for i in range(16):
            expanded_key[i] = key[i]
        
        # Generate the rest of the round keys
        # pragma hls pipeline enable
        # pragma loop_count 10
        for i in range(10):  # 10 rounds for AES-128
            # Take the last 4 bytes of the previous round key
            temp = [expanded_key[i*16 + 12 + j] for j in range(4)]
            
            # Rotate left
            temp = [temp[1], temp[2], temp[3], temp[0]]
            
            # Apply S-box
            # pragma loop_count 4
            for j in range(4):
                temp[j] = s_box[temp[j]]
            
            # XOR with Rcon
            temp[0] ^= rcon[i]
            
            # Generate the next round key
            # pragma loop_count 4
            for j in range(4):
                # pragma loop_count 4
                for k in range(4):
                    idx = (i+1)*16 + j*4 + k
                    expanded_key[idx] = expanded_key[i*16 + j*4 + k] ^ (temp[k] if j == 0 else expanded_key[(i+1)*16 + (j-1)*4 + k])
        
        return expanded_key
    
    def encrypt_block(block_start_idx):
        # Load block data into state
        # pragma hls unroll factor=4
        # pragma loop_count 16
        for i in range(16):
            state[i] = plaintext[block_start_idx + i]
        
        # Initial round
        add_round_key(state, expanded_key, 0)
        
        # Main rounds
        # pragma hls pipeline enable
        # pragma loop_count 9
        for round_num in range(1, 10):
            sub_bytes(state)
            shift_rows(state)
            mix_columns(state)
            add_round_key(state, expanded_key, round_num)
        
        # Final round (no mix_columns)
        sub_bytes(state)
        shift_rows(state)
        add_round_key(state, expanded_key, 10)
        
        # Store the result in ciphertext
        # pragma hls unroll factor=4
        # pragma loop_count 16
        for i in range(16):
            ciphertext[block_start_idx + i] = state[i]
    
    # Pragma: Matrix operation hint
    # pragma hls matrix_operation aes
    
    # Pragma: Enable pipeline optimization for this function
    # pragma hls pipeline enable
    
    # First, expand the key (only need to do this once)
    expand_key(key)
    
    # Calculate the number of 16-byte blocks to process
    num_blocks = {block_size} // 16
    
    # Process each 16-byte block
    # pragma loop_count {block_size // 16}
    for block_idx in range(num_blocks):
        block_start = block_idx * 16
        encrypt_block(block_start)
    
    return ciphertext
"""

def write_aes_large_size_file(filename, block_size=128):
    """Write AES large size code to a file"""
    code = create_aes_large_size_code(block_size)
    with open(filename, "w") as f:
        f.write(code)
    # Also save to a visible location for inspection
    with open(f"aes_large_size_{block_size}.py", "w") as f:
        f.write(code)
    return filename

def analyze_aes_large_size():
    """Analyze AES with different sizes using HLS"""
    logger.info("=" * 80)
    logger.info("Analyzing AES with Different Block Sizes using HLS")
    logger.info("=" * 80)
    
    # Create a temporary directory for test output
    test_dir = tempfile.mkdtemp()
    
    # Test different block sizes
    block_sizes = [128, 256, 512, 1024]  # in bytes
    results = {}
    
    try:
        for block_size in block_sizes:
            logger.info(f"Testing block size: {block_size} bytes ({block_size // 16} AES blocks)")
            
            # Generate code and save to file
            filepath = os.path.join(test_dir, f"aes_large_size_{block_size}.py")
            write_aes_large_size_file(filepath, block_size)
            logger.info(f"Generated AES code for size {block_size} in {filepath}")
            
            # Create a new HLS instance with optimization level 3
            hls = HLS(optimization_level=3, tech_node=45)
            
            try:
                # Compile the AES code
                netlist = hls.compile(filepath, target="verilog")
                
                if hasattr(hls, 'scheduled_ir') and hls.scheduled_ir:
                    # Always use performance optimization for larger designs
                    optimization_target = "performance"
                    hls.allocated_resources = hls.allocator.allocate(
                        hls.scheduled_ir, optimization_target
                    )[1]
                    hls.netlist_resources = hls.allocator.create_netlist_resources(hls.allocated_resources)
                    
                    # Update the netlist resources
                    hls._apply_resources_to_modules()
                
                # Generate visualizations if the scheduled IR is available
                if hasattr(hls, 'scheduled_ir') and hls.scheduled_ir:
                    datapath_file = hls.visualize_datapath(output_file=f"aes_size{block_size}_datapath.png")
                    scheduled_file = hls.visualize_scheduled_datapath(output_file=f"aes_size{block_size}_scheduled_datapath.png")
                    control_file = hls.visualize_control_flow(output_file=f"aes_size{block_size}_control_flow.png")
                    netlist_file = hls.visualize_netlist(output_file=f"aes_size{block_size}_netlist.png")
                    
                    # Get performance metrics
                    metrics = hls.get_performance_metrics()
                    
                    # Store metrics for this block size
                    results[block_size] = {
                        "latency_cycles": metrics.get('latency_cycles', 'N/A'),
                        "clock_frequency": metrics.get('clock_frequency_mhz', 'N/A'),
                        "area": metrics.get('total_area', 'N/A'),
                        "power": metrics.get('total_power', 'N/A'),
                        "visualization_files": {
                            "datapath": datapath_file,
                            "scheduled": scheduled_file,
                            "control": control_file,
                            "netlist": netlist_file
                        }
                    }
                    
                    # Print metrics
                    logger.info(f"Performance metrics for block size {block_size}:")
                    logger.info(f"Latency: {metrics.get('latency_cycles', 'N/A')} cycles")
                    logger.info(f"Clock frequency: {metrics.get('clock_frequency_mhz', 'N/A')} MHz")
                    logger.info(f"Area: {metrics.get('total_area', 'N/A')} μm²")
                    logger.info(f"Power: {metrics.get('total_power', 'N/A')} mW")
                
                logger.info(f"Successfully compiled AES with block size {block_size}")
                
            except Exception as e:
                logger.error(f"Error during compilation with block size {block_size}: {e}")
                logger.error(traceback.format_exc())
                # Continue with the next block size
        
        # Print final comparison
        logger.info("=" * 80)
        logger.info("AES PERFORMANCE COMPARISON ACROSS BLOCK SIZES")
        logger.info("=" * 80)
        
        if results:
            logger.info("Block Size | AES Blocks | Latency (cycles) | Clock Freq (MHz) | Area (μm²) | Power (mW)")
            logger.info("-" * 90)
            
            for block_size in sorted(block_sizes):
                if block_size in results:
                    metrics = results[block_size]
                    logger.info(f"{block_size:^10} | {block_size//16:^10} | {metrics['latency_cycles']:^16} | {metrics['clock_frequency']:^16.2f} | {metrics['area']:^10.2f} | {metrics['power']:^10.2f}")
        
        # Clean up
        shutil.rmtree(test_dir)
        
    except Exception as e:
        logger.error(f"Error during AES large size analysis: {e}")
        logger.error(traceback.format_exc())
        # Clean up
        shutil.rmtree(test_dir)
    
    return results

def main():
    """Main function to run the AES large size analysis"""
    results = analyze_aes_large_size()
    
    return results

if __name__ == "__main__":
    main() 