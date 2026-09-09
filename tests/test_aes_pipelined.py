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
        logging.FileHandler("aes_pipelined_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aes_pipelined_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS

def create_aes_pipelined_code(num_blocks=16):
    """Create AES implementation with proper pipelining and explicit block processing
    
    Args:
        num_blocks: Number of AES blocks to process
    """
    return f"""
def aes_encrypt_pipelined(plaintext, key):
    # This implementation processes {num_blocks} blocks of data using AES
    # Each block is 16 bytes (128 bits)
    # With explicit serialized processing to demonstrate latency changes
    
    # Memory size annotations for the HLS scheduler
    plaintext_memory_size = {num_blocks * 16}  # {num_blocks * 16} bytes
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
    ciphertext = [0] * {num_blocks * 16}
    ciphertext_memory_size = {num_blocks * 16}  # {num_blocks * 16} bytes
    
    # Round keys (for all rounds)
    # pragma hls memory_type RAM
    expanded_key = [0] * 176  # 11 round keys * 16 bytes
    expanded_key_memory_size = 176  # 176 bytes
    
    # State array for block being processed
    # pragma hls memory_type RAM
    state = [0] * 16
    state_memory_size = 16  # 16 bytes
    
    def sub_bytes(state):
        # Substitute each byte in the state with its S-box value
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
    
    def encrypt_block(block_data, expanded_key, block_index):
        # Create a state array for this block
        current_state = [0] * 16
        
        # Load plaintext for this block
        # pragma hls unroll factor=4
        # pragma loop_count 16
        for i in range(16):
            current_state[i] = block_data[block_index * 16 + i]
        
        # Initial round
        current_state = add_round_key(current_state, expanded_key, 0)
        
        # Main rounds
        # pragma loop_count 9
        for round_num in range(1, 10):
            current_state = sub_bytes(current_state)
            current_state = shift_rows(current_state)
            current_state = mix_columns(current_state)
            current_state = add_round_key(current_state, expanded_key, round_num)
        
        # Final round (no mix_columns)
        current_state = sub_bytes(current_state)
        current_state = shift_rows(current_state)
        current_state = add_round_key(current_state, expanded_key, 10)
        
        # Store the encrypted block
        # pragma hls unroll factor=4
        # pragma loop_count 16
        for i in range(16):
            ciphertext[block_index * 16 + i] = current_state[i]
        
        return current_state
    
    # Pragma: Matrix operation hint
    # pragma hls matrix_operation aes
    
    # Pragma: Enable pipeline optimization for this function
    # pragma hls pipeline enable
    
    # First, expand the key (only need to do this once)
    expanded_key = expand_key(key)
    
    # Process each block EXPLICITLY in sequence to demonstrate latency changes
    # pragma loop_count {num_blocks}
    for block_idx in range({num_blocks}):
        # Process the current block
        encrypt_block(plaintext, expanded_key, block_idx)
    
    return ciphertext
"""

def write_aes_pipelined_file(filename, num_blocks=16):
    """Write AES pipelined code to a file"""
    code = create_aes_pipelined_code(num_blocks)
    with open(filename, "w") as f:
        f.write(code)
    # Also save to a visible location for inspection
    with open(f"aes_pipelined_{num_blocks}.py", "w") as f:
        f.write(code)
    return filename

def analyze_aes_pipelined():
    """Analyze AES with different block counts using HLS"""
    logger.info("=" * 80)
    logger.info("Analyzing AES with Different Block Counts using HLS")
    logger.info("=" * 80)
    
    # Create a temporary directory for test output
    test_dir = tempfile.mkdtemp()
    
    # Test different block counts
    block_counts = [1, 4, 16, 64]  # number of blocks
    results = {}
    
    try:
        for num_blocks in block_counts:
            logger.info(f"Testing with {num_blocks} blocks ({num_blocks * 16} bytes)")
            
            # Generate code and save to file
            filepath = os.path.join(test_dir, f"aes_pipelined_{num_blocks}.py")
            write_aes_pipelined_file(filepath, num_blocks)
            logger.info(f"Generated AES code for {num_blocks} blocks in {filepath}")
            
            # Create a new HLS instance with optimization level 3
            hls = HLS(optimization_level=3, tech_node=45)
            
            try:
                # Set the target function name and force serialized execution
                hls.enable_loop_pipelining = False  # Ensure we see the latency differences
                
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
                    datapath_file = hls.visualize_datapath(output_file=f"aes_blocks{num_blocks}_datapath.png")
                    scheduled_file = hls.visualize_scheduled_datapath(output_file=f"aes_blocks{num_blocks}_scheduled_datapath.png")
                    control_file = hls.visualize_control_flow(output_file=f"aes_blocks{num_blocks}_control_flow.png")
                    netlist_file = hls.visualize_netlist(output_file=f"aes_blocks{num_blocks}_netlist.png")
                    
                    # Get performance metrics
                    metrics = hls.get_performance_metrics()
                    
                    # Store metrics for this block count
                    results[num_blocks] = {
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
                    logger.info(f"Performance metrics for {num_blocks} blocks:")
                    logger.info(f"Latency: {metrics.get('latency_cycles', 'N/A')} cycles")
                    logger.info(f"Clock frequency: {metrics.get('clock_frequency_mhz', 'N/A')} MHz")
                    logger.info(f"Area: {metrics.get('total_area', 'N/A')} μm²")
                    logger.info(f"Power: {metrics.get('total_power', 'N/A')} mW")
                
                logger.info(f"Successfully compiled AES with {num_blocks} blocks")
                
            except Exception as e:
                logger.error(f"Error during compilation with {num_blocks} blocks: {e}")
                logger.error(traceback.format_exc())
                # Continue with the next block count
        
        # Print final comparison
        logger.info("=" * 80)
        logger.info("AES PERFORMANCE COMPARISON ACROSS BLOCK COUNTS")
        logger.info("=" * 80)
        
        if results:
            logger.info("Blocks | Size (bytes) | Latency (cycles) | Clock Freq (MHz) | Area (μm²) | Power (mW)")
            logger.info("-" * 90)
            
            for num_blocks in sorted(block_counts):
                if num_blocks in results:
                    metrics = results[num_blocks]
                    logger.info(f"{num_blocks:^6} | {num_blocks*16:^12} | {metrics['latency_cycles']:^16} | {metrics['clock_frequency']:^16.2f} | {metrics['area']:^10.2f} | {metrics['power']:^10.2f}")
        
        # Clean up
        shutil.rmtree(test_dir)
        
    except Exception as e:
        logger.error(f"Error during AES pipelined analysis: {e}")
        logger.error(traceback.format_exc())
        # Clean up
        shutil.rmtree(test_dir)
    
    return results

def main():
    """Main function to run the AES pipelined analysis"""
    results = analyze_aes_pipelined()
    
    return results

if __name__ == "__main__":
    main() 