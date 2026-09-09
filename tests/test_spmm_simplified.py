import os
import sys
import logging
import tempfile
import shutil

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("spmm_simplified_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("spmm_simplified_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS

def create_simple_spmm_code(size):
    """Generate simple SPMM code with specified matrix size without tiling"""
    return f"""
def spmm_simple(A, values, row_num, row_ptr, C, size):
    # Matrix dimensions: size = {size}
    
    # Simple direct implementation without tiling
    for i in range(size):
        for j in range(size):
            # For each element in the output matrix
            sum_val = 0
            k_start = row_ptr[j]
            k_end = row_ptr[j+1]
            
            # This loop depends on the sparsity pattern
            # For testing, we'll make it proportional to size
            for k_ptr in range(k_start, k_start + size // 4):
                k = row_num[k_ptr]
                x = A[i][k]
                wt = values[k_ptr]
                sum_val += x * wt
            
            C[i][j] = sum_val
    
    return C
"""

def create_fixed_size_code(size):
    """Generate code with size hardcoded in the loops"""
    return f"""
def spmm_fixed_{size}(A, values, row_num, row_ptr, C):
    # Hardcoded size = {size}
    
    # Completely unrolled outer loops
    for i in range({size}):
        for j in range({size}):
            sum_val = 0
            k_start = row_ptr[j]
            
            # Inner loop with fixed iteration count
            for k_idx in range({size // 4}):
                k_ptr = k_start + k_idx
                k = row_num[k_ptr]
                x = A[i][k]
                wt = values[k_ptr]
                sum_val += x * wt
            
            C[i][j] = sum_val
    
    return C
"""

def analyze_simple_spmm(size):
    """Analyze simple SPMM code with specified size"""
    logger.info(f"=" * 80)
    logger.info(f"Analyzing Simple SPMM with size {size}")
    logger.info(f"=" * 80)
    
    # Create a temporary directory for test output
    test_dir = tempfile.mkdtemp()
    
    try:
        # Generate code and save to file
        filepath = os.path.join(test_dir, f"spmm_simple_{size}.py")
        with open(filepath, 'w') as f:
            f.write(create_simple_spmm_code(size))
        logger.info(f"Generated simple SPMM code with size {size} in {filepath}")
        
        # Also save to current directory for inspection
        with open(f"spmm_simple_{size}.py", "w") as f:
            f.write(create_simple_spmm_code(size))
        
        # Create an HLS instance
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile the SPMM code
        logger.info(f"Compiling simple SPMM code with size {size}")
        netlist = hls.compile(filepath, target="verilog")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        logger.info(f"RESULTS for simple SPMM with size {size}:")
        logger.info(f"  - Technology node: {metrics['technology_node']}")
        logger.info(f"  - Total area: {metrics['total_area']}")
        logger.info(f"  - Total power: {metrics['total_power']}")
        logger.info(f"  - Critical path: {metrics['critical_path']}")
        
        # Check allocated resources
        logger.info(f"Allocated resources: {hls.allocated_resources}")
        
        # Check if any modules were created
        if hls.netlist and hls.netlist.modules:
            logger.info(f"Number of modules: {len(hls.netlist.modules)}")
            for module_name, module in hls.netlist.modules.items():
                logger.info(f"Module {module_name}:")
                logger.info(f"  Resources count: {len(module.resources)}")
                logger.info(f"  Area: {module.area}")
        
        # Return the metrics
        result = {
            "metrics": metrics,
            "allocated_resources": hls.allocated_resources
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error during simple SPMM analysis: {e}")
        raise
    
    finally:
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

def analyze_fixed_size_spmm(size):
    """Analyze fixed-size SPMM code"""
    logger.info(f"=" * 80)
    logger.info(f"Analyzing Fixed-Size SPMM with size {size}")
    logger.info(f"=" * 80)
    
    # Create a temporary directory for test output
    test_dir = tempfile.mkdtemp()
    
    try:
        # Generate code and save to file
        filepath = os.path.join(test_dir, f"spmm_fixed_{size}.py")
        with open(filepath, 'w') as f:
            f.write(create_fixed_size_code(size))
        logger.info(f"Generated fixed-size SPMM code with size {size} in {filepath}")
        
        # Also save to current directory for inspection
        with open(f"spmm_fixed_{size}.py", "w") as f:
            f.write(create_fixed_size_code(size))
        
        # Create an HLS instance with debug flags for extra info
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile the SPMM code
        logger.info(f"Compiling fixed-size SPMM code with size {size}")
        netlist = hls.compile(filepath, target="verilog")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        logger.info(f"RESULTS for fixed-size SPMM with size {size}:")
        logger.info(f"  - Technology node: {metrics['technology_node']}")
        logger.info(f"  - Total area: {metrics['total_area']}")
        logger.info(f"  - Total power: {metrics['total_power']}")
        logger.info(f"  - Critical path: {metrics['critical_path']}")
        
        # Check allocated resources
        logger.info(f"Allocated resources: {hls.allocated_resources}")
        
        # Return the metrics
        result = {
            "metrics": metrics,
            "allocated_resources": hls.allocated_resources
        }
        
        return result
    
    except Exception as e:
        logger.error(f"Error during fixed-size SPMM analysis: {e}")
        raise
    
    finally:
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

def main():
    """Main function to run the simplified tests"""
    logger.info("Starting Simplified SPMM Analysis")
    
    # Analyze simple SPMM with different sizes
    results_256 = analyze_simple_spmm(256)
    results_512 = analyze_simple_spmm(512)
    
    # Log comparison
    logger.info("=" * 80)
    logger.info("COMPARISON OF SIMPLE SPMM RESULTS:")
    logger.info("=" * 80)
    logger.info(f"Total area for size 256: {results_256['metrics']['total_area']}")
    logger.info(f"Total area for size 512: {results_512['metrics']['total_area']}")
    logger.info(f"Area ratio 512/256: {results_512['metrics']['total_area']/results_256['metrics']['total_area'] if results_256['metrics']['total_area'] != 0 else 'N/A'}")
    
    # Analyze fixed size implementations
    fixed_results_256 = analyze_fixed_size_spmm(256)
    fixed_results_512 = analyze_fixed_size_spmm(512)
    
    # Log comparison of fixed size results
    logger.info("=" * 80)
    logger.info("COMPARISON OF FIXED-SIZE SPMM RESULTS:")
    logger.info("=" * 80)
    logger.info(f"Total area for size 256: {fixed_results_256['metrics']['total_area']}")
    logger.info(f"Total area for size 512: {fixed_results_512['metrics']['total_area']}")
    logger.info(f"Area ratio 512/256: {fixed_results_512['metrics']['total_area']/fixed_results_256['metrics']['total_area'] if fixed_results_256['metrics']['total_area'] != 0 else 'N/A'}")
    
    return {
        "simple": {
            "256": results_256,
            "512": results_512
        },
        "fixed": {
            "256": fixed_results_256,
            "512": fixed_results_512
        }
    }

if __name__ == "__main__":
    main() 