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
        logging.FileHandler("aes_hls_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aes_hls_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS

def create_aes_code():
    """Create AES encryption code"""
    return """
def aes_encrypt(plaintext, key):
    # Note: This is a simplified implementation of AES for HLS testing
    # It implements the core AES operations but is not a complete implementation
    
    # Memory size annotations for the HLS scheduler
    plaintext_memory_size = len(plaintext) * 4  # 4 bytes per int
    key_memory_size = len(key) * 4  # 4 bytes per int
    
    # S-box lookup table (simplified for demonstration)
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
    s_box_memory_size = len(s_box) * 1  # 1 byte per element
    
    # Rcon lookup table (simplified)
    # pragma hls memory_type ROM
    rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]
    rcon_memory_size = len(rcon) * 1  # 1 byte per element
    
    # AES state is 4x4 matrix of bytes (represented as a 1D array)
    # pragma hls memory_type RAM
    state = [0] * 16
    state_memory_size = len(state) * 1  # 1 byte per element
    
    # Key expansion - simplified (normally creates many round keys)
    # pragma hls memory_type RAM
    expanded_key = [0] * 176  # 11 round keys * 16 bytes
    expanded_key_memory_size = len(expanded_key) * 1  # 1 byte per element
    
    def sub_bytes(state):
        # Substitute each byte in the state with its corresponding value in the S-box
        # pragma hls pipeline enable
        for i in range(16):
            state[i] = s_box[state[i]]
        return state
    
    def shift_rows(state):
        # Shift rows of the state matrix
        # Row 0: No shift
        # Row 1: Shift left by 1
        # Row 2: Shift left by 2
        # Row 3: Shift left by 3
        
        # Extract state into a 4x4 matrix for clarity
        matrix = [[0 for _ in range(4)] for _ in range(4)]
        for i in range(4):
            for j in range(4):
                matrix[i][j] = state[i + 4*j]
        
        # Perform the row shifts
        # pragma hls pipeline enable
        for i in range(4):
            # Shift row i by i positions
            row = [matrix[i][j] for j in range(4)]
            for j in range(4):
                matrix[i][j] = row[(j + i) % 4]
        
        # Convert back to 1D array
        for i in range(4):
            for j in range(4):
                state[i + 4*j] = matrix[i][j]
        
        return state
    
    def mix_columns(state):
        # Mix the columns of the state matrix
        # This is a simplified version that captures the core operation pattern
        
        # Extract state into a 4x4 matrix
        matrix = [[0 for _ in range(4)] for _ in range(4)]
        for i in range(4):
            for j in range(4):
                matrix[i][j] = state[i + 4*j]
        
        # Temporary array to hold the mixed columns
        mixed = [[0 for _ in range(4)] for _ in range(4)]
        
        # Mix each column
        # pragma hls pipeline enable
        for j in range(4):
            # These constants are from the AES specification
            mixed[0][j] = (((matrix[0][j] << 1) & 0xFF) ^ ((matrix[1][j] << 1) & 0xFF) ^ matrix[1][j] ^ 
                           matrix[2][j] ^ matrix[3][j])
            mixed[1][j] = (matrix[0][j] ^ ((matrix[1][j] << 1) & 0xFF) ^ ((matrix[2][j] << 1) & 0xFF) ^ 
                          matrix[2][j] ^ matrix[3][j])
            mixed[2][j] = (matrix[0][j] ^ matrix[1][j] ^ ((matrix[2][j] << 1) & 0xFF) ^ 
                          ((matrix[3][j] << 1) & 0xFF) ^ matrix[3][j])
            mixed[3][j] = (((matrix[0][j] << 1) & 0xFF) ^ matrix[0][j] ^ matrix[1][j] ^ 
                          matrix[2][j] ^ ((matrix[3][j] << 1) & 0xFF))
        
        # Convert back to 1D array
        for i in range(4):
            for j in range(4):
                state[i + 4*j] = mixed[i][j]
        
        return state
    
    def add_round_key(state, round_key, round_num):
        # XOR the state with the round key
        # pragma hls pipeline enable
        for i in range(16):
            state[i] ^= round_key[round_num * 16 + i]
        return state
    
    def expand_key(key):
        # Key expansion (simplified)
        # Copy the initial key
        # pragma hls unroll factor=4
        for i in range(16):
            expanded_key[i] = key[i]
        
        # Generate the rest of the round keys
        # pragma hls pipeline enable
        for i in range(10):  # 10 rounds for AES-128
            # Take the last 4 bytes of the previous round key
            temp = [expanded_key[i*16 + 12 + j] for j in range(4)]
            
            # Rotate left
            temp = [temp[1], temp[2], temp[3], temp[0]]
            
            # Apply S-box
            for j in range(4):
                temp[j] = s_box[temp[j]]
            
            # XOR with Rcon
            temp[0] ^= rcon[i]
            
            # Generate the next round key
            for j in range(4):
                for k in range(4):
                    idx = (i+1)*16 + j*4 + k
                    expanded_key[idx] = expanded_key[i*16 + j*4 + k] ^ (temp[k] if j == 0 else expanded_key[(i+1)*16 + (j-1)*4 + k])
        
        return expanded_key
    
    # Initialize state with plaintext
    # pragma hls unroll factor=4
    for i in range(16):
        state[i] = plaintext[i]
    
    # Expand the key
    expanded_key = expand_key(key)
    
    # Initial round
    state = add_round_key(state, expanded_key, 0)
    
    # Main rounds
    # pragma hls pipeline enable
    for round_num in range(1, 10):
        state = sub_bytes(state)
        state = shift_rows(state)
        state = mix_columns(state)
        state = add_round_key(state, expanded_key, round_num)
    
    # Final round (no mix_columns)
    state = sub_bytes(state)
    state = shift_rows(state)
    state = add_round_key(state, expanded_key, 10)
    
    # Return the encrypted data
    return state
"""

def write_aes_file(filename):
    """Write AES code to a file"""
    code = create_aes_code()
    with open(filename, "w") as f:
        f.write(code)
    # Also save to a visible location for inspection
    with open("aes_code.py", "w") as f:
        f.write(code)
    return filename

def analyze_aes():
    """Analyze AES code with HLS"""
    logger.info("=" * 80)
    logger.info("Analyzing AES with HLS")
    logger.info("=" * 80)
    
    # Create a temporary directory for test output
    test_dir = tempfile.mkdtemp()
    
    try:
        # Generate code and save to file
        filepath = os.path.join(test_dir, "aes.py")
        write_aes_file(filepath)
        logger.info(f"Generated AES code in {filepath}")
        
        results = {}
        
        for opt_level in [1, 3]:
            logger.info(f"Testing optimization level {opt_level}")
            
            # Create a new HLS instance
            hls = HLS(optimization_level=opt_level, tech_node=45)
            
            try:
                # Compile the AES code
                netlist = hls.compile(filepath, target="verilog")
                if hasattr(hls, 'scheduled_ir') and hls.scheduled_ir:
                    # The bigger the matrix, the more resources needed
                    optimization_target = "performance" 
                    # if size >= 512 else "area"
                    hls.allocated_resources = hls.allocator.allocate(
                        hls.scheduled_ir, optimization_target
                    )[1]
                    hls.netlist_resources = hls.allocator.create_netlist_resources(hls.allocated_resources)
                    
                    # Update the netlist resources
                    hls._apply_resources_to_modules()
                # Generate visualizations if the scheduled IR is available
                if hasattr(hls, 'scheduled_ir') and hls.scheduled_ir:
                    datapath_file = hls.visualize_datapath(output_file=f"aes_opt{opt_level}_datapath.png")
                    scheduled_file = hls.visualize_scheduled_datapath(output_file=f"aes_opt{opt_level}_scheduled_datapath.png")
                    control_file = hls.visualize_control_flow(output_file=f"aes_opt{opt_level}_control_flow.png")
                    netlist_file = hls.visualize_netlist(output_file=f"aes_opt{opt_level}_netlist.png")
                    
                    # # Get performance metrics safely with detailed debug
                    # try:
                    #     # Debug information about the netlist
                    #     if hasattr(hls, 'netlist') and hls.netlist:
                    #         logger.info(f"Netlist modules count: {len(hls.netlist.modules)}")
                    #         for module_name, module in hls.netlist.modules.items():
                    #             logger.info(f"Module '{module_name}' attributes: {dir(module)}")
                                
                    #     metrics = {}
                    #     # Step-by-step gathering of metrics with error handling
                    #     try:
                    #         if hasattr(hls, 'netlist') and hls.netlist and hasattr(hls.netlist, 'total_area'):
                    #             metrics['total_area'] = hls.netlist.total_area
                    #         else:
                    #             logger.error("Netlist or total_area attribute not found")
                    #     except Exception as e:
                    #         logger.error(f"Error getting total_area: {e}")
                            
                    #     try:
                    #         if hasattr(hls, 'netlist') and hls.netlist and hasattr(hls.netlist, 'total_power'):
                    #             metrics['total_power'] = hls.netlist.total_power
                    #         else:
                    #             logger.error("Netlist or total_power attribute not found")
                    #     except Exception as e:
                    #         logger.error(f"Error getting total_power: {e}")
                            
                    #     # Collect power breakdown
                    #     power_breakdown = {}
                    #     try:
                    #         if hasattr(hls, 'netlist') and hls.netlist:
                    #             resource_report = hls.netlist.get_resource_report()
                    #             if 'modules' in resource_report:
                    #                 for module_name, module in resource_report['modules'].items():
                    #                     logger.info(f"Module {module_name} resource report: {type(module)}")
                    #                     if hasattr(module, 'power_breakdown'):
                    #                         power_breakdown[module_name] = module.power_breakdown
                    #                     elif isinstance(module, dict) and 'power_breakdown' in module:
                    #                         power_breakdown[module_name] = module['power_breakdown']
                    #                     else:
                    #                         logger.error(f"Module {module_name} doesn't have power_breakdown attribute. Type: {type(module)}")
                    #                         if isinstance(module, dict):
                    #                             logger.error(f"Module keys: {module.keys()}")
                    #             else:
                    #                 logger.error("No 'modules' in resource report")
                    #     except Exception as e:
                    #         logger.error(f"Error getting power breakdown: {str(e)}")
                    #         logger.error(traceback.format_exc())
                        
                    #     metrics['power_breakdown'] = power_breakdown
                    metrics = hls.get_performance_metrics()

                    # Print what we gathered
                    if metrics:
                        logger.info(f"Performance metrics for optimization level {opt_level}:")
                        logger.info(f"Latency: {metrics.get('latency_cycles', 'N/A')} cycles")
                        logger.info(f"Clock frequency: {metrics.get('clock_frequency_mhz', 'N/A')} MHz")
                        logger.info(f"  Area: {metrics.get('total_area', 'N/A')} μm²")
                        logger.info(f"  Power: {metrics.get('total_power', 'N/A')} mW")
                        logger.info(f"  Power breakdown: {metrics.get('power_breakdown', 'N/A')}")
                    # except Exception as e:
                    #     logger.error(f"Error getting performance metrics: {e}")
                    #     logger.error(traceback.format_exc())
                    
                    results[opt_level] = {
                        "datapath_file": datapath_file,
                        "scheduled_file": scheduled_file,
                        "control_file": control_file,
                        "netlist_file": netlist_file
                    }
                    output_dir = "visualization_output"

                    microarch_file = hls.visualize_netlist_microarch(output_file=os.path.join(output_dir, "aes_microarch.png"))   

                
                logger.info(f"Successfully compiled AES with optimization level {opt_level}")
                
            except Exception as e:
                logger.error(f"Error during compilation with optimization level {opt_level}: {e}")
                logger.error(traceback.format_exc())
        
        # Clean up
        shutil.rmtree(test_dir)
        
    except Exception as e:
        logger.error(f"Error during AES analysis: {e}")
        logger.error(traceback.format_exc())
        # Clean up
        shutil.rmtree(test_dir)
        
    logger.info("=" * 80)
    logger.info("AES HLS ANALYSIS SUMMARY")
    logger.info("=" * 80)
    
    return results

def main():
    """Main function to run the AES HLS analysis"""
    results = analyze_aes()
    
    return results

if __name__ == "__main__":
    main() 