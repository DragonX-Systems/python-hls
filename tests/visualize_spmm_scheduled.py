"""
Script to visualize the scheduled datapath for SPMM (Sparse Matrix-Matrix Multiplication)
with different matrix sizes.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add parent directory to path to import modules
script_dir = Path(__file__).parent
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))

# Import the HLS class from python_hls
from python_hls import HLS
from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("spmm_visualizer")

def create_spmm_code(size):
    """Generate SPMM code with specified matrix size"""
    return f"""
def spmm(A, values, row_num, row_ptr, C):
    # Matrix dimensions defined as constants
    M = {size}
    N = {size}
    K = {size}

    A = [[2.2] * M] * K
    C = [[0 for _ in range(N)] for _ in range(M)]

    values = [1, 5, 3, 0, 2, 6, 4]
    row_num = [1, 3, 2, 0, 1, 3, 2]
    row_ptr = [0, 2, 3, 6, 7]

    # Block size for tiled computation
    BLOCK_SIZE = 32

    # Process computation in 32x32 blocks
    count = 0
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
                    count += 1
                    for k_ptr in range(k_start, k_end):
                        k = row_num[k_ptr]
                        x = A[i][k]
                        wt = values[k_ptr]
                        C[i][j] += x * wt
    return C
"""

def write_spmm_file(size, filepath):
    """Write SPMM code to a file"""
    code = create_spmm_code(size)
    with open(filepath, "w") as f:
        f.write(code)
    logger.info(f"Created SPMM code with size {size} in {filepath}")
    return filepath

def visualize_spmm_scheduled_datapath(size, output_dir):
    """Compile and visualize the scheduled datapath for SPMM of specified size"""
    logger.info(f"Visualizing scheduled datapath for SPMM with size {size}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create the SPMM source file
    filepath = os.path.join(output_dir, f"spmm_{size}.py")
    write_spmm_file(size, filepath)
    
    # Create an HLS instance
    hls = HLS(optimization_level=1, tech_node=45)
    
    # Compile the SPMM code
    logger.info(f"Compiling SPMM code with size {size}")
    try:
        netlist = hls.compile(filepath, target="verilog")
        
        # Generate visualization
        output_file = os.path.join(output_dir, f"spmm_{size}_scheduled_datapath.png")
        scheduled_file = hls.visualize_scheduled_datapath(output_file=output_file)
        
        # Also generate the unscheduled datapath for comparison
        datapath_file = hls.visualize_datapath(
            output_file=os.path.join(output_dir, f"spmm_{size}_datapath.png")
        )
        
        logger.info(f"Generated scheduled datapath visualization: {scheduled_file}")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        logger.info(f"METRICS for size {size}:")
        logger.info(f"  - Technology node: {metrics['technology_node']} nm")
        logger.info(f"  - Total area: {metrics['total_area']} μm²")
        logger.info(f"  - Total power: {metrics['total_power']} mW")
        logger.info(f"  - Critical path: {metrics['critical_path']} ns")
        
        return {
            "scheduled_file": scheduled_file,
            "datapath_file": datapath_file,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"Error visualizing SPMM (size {size}): {e}")
        raise

def main():
    """Main function to visualize scheduled datapath for SPMM with different sizes"""
    parser = argparse.ArgumentParser(description="Visualize scheduled datapath for SPMM")
    parser.add_argument("--sizes", type=int, nargs="+", default=[256, 512],
                        help="Matrix sizes to visualize (default: 256, 512)")
    parser.add_argument("--output-dir", type=str, default="spmm_visualizations",
                        help="Directory to save visualizations (default: spmm_visualizations)")
    args = parser.parse_args()
    
    logger.info(f"Starting SPMM scheduled datapath visualization for sizes: {args.sizes}")
    
    # Dictionary to store results for comparison
    results = {}
    
    for size in args.sizes:
        results[size] = visualize_spmm_scheduled_datapath(size, args.output_dir)
    
    # Print comparison summary
    logger.info("\n" + "="*80)
    logger.info("COMPARISON SUMMARY")
    logger.info("="*80)
    
    # Print area and critical path comparisons if we have more than one size
    if len(args.sizes) > 1:
        base_size = args.sizes[0]
        base_metrics = results[base_size]["metrics"]
        
        for size in args.sizes[1:]:
            metrics = results[size]["metrics"]
            area_ratio = metrics["total_area"] / base_metrics["total_area"]
            path_ratio = metrics["critical_path"] / base_metrics["critical_path"]
            
            logger.info(f"Size {size} vs {base_size}:")
            logger.info(f"  - Area ratio: {area_ratio:.2f}x")
            logger.info(f"  - Critical path ratio: {path_ratio:.2f}x")
    
    logger.info(f"\nVisualization files are saved in: {os.path.abspath(args.output_dir)}")

if __name__ == "__main__":
    main()