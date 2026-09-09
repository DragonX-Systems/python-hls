import os
import sys
import logging
from pprint import pformat

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("spmm_simple_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("spmm_simple_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import HLS tools
from python_hls import HLS

# Import the spmm function from the example file
from mentor_spmm_simple import spmm

def test_spmm():
    """Test the spmm function and generate visualizations"""
    logger.info("=" * 80)
    logger.info("Testing Simplified Mentor SpMM implementation")
    logger.info("=" * 80)
    
    # Create an HLS instance
    hls = HLS(optimization_level=1, tech_node=45)
    
    # Compile the mentor_spmm_simple.py file
    try:
        logger.info("Compiling Mentor SpMM code")
        
        # Path to the mentor_spmm_simple.py file
        filepath = os.path.join(current_dir, "mentor_spmm_simple.py")
        
        # Perform the compilation
        netlist = hls.compile(filepath, target="verilog")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        opt_report = hls.get_optimization_report()
        opt_summary = hls.get_optimization_summary()
        
        logger.info("RESULTS:")
        logger.info(f"  - Technology node: {metrics['technology_node']}")
        logger.info(f"  - Total area: {metrics['total_area']}")
        logger.info(f"  - Total power: {metrics['total_power']}")
        logger.info(f"  - Critical path: {metrics['critical_path']}")
        logger.info(f"  - Power breakdown: {metrics['power_breakdown']}")
        
        # Generate visualizations
        datapath_file = hls.visualize_datapath(output_file="spmm_simple_datapath.png")
        scheduled_file = hls.visualize_scheduled_datapath(output_file="spmm_simple_scheduled_datapath.png")
        control_file = hls.visualize_control_flow(output_file="spmm_simple_control_flow.png")
        netlist_file = hls.visualize_netlist(output_file="spmm_simple_netlist.png")
        
        logger.info("Generated visualizations:")
        logger.info(f"  - Datapath: {datapath_file}")
        logger.info(f"  - Scheduled datapath: {scheduled_file}")
        logger.info(f"  - Control flow: {control_file}")
        logger.info(f"  - Netlist: {netlist_file}")
        logger.info(f"  - Optimization summary: {opt_summary}")
        
        return {
            "netlist": netlist,
            "metrics": metrics,
            "datapath_file": datapath_file,
            "scheduled_file": scheduled_file,
            "control_file": control_file,
            "netlist_file": netlist_file
        }
        
    except Exception as e:
        logger.error(f"Error during compilation: {e}")
        raise

def functional_test():
    """Test the actual functionality of the spmm function"""
    # Example sparse matrix in CSC format
    sparse_matrix = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    dense_matrix = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    row_indices = [0, 2, 1, 3, 0, 2, 1, 3]
    output_size = 4
    
    # Run the Mentor SpMM function
    result = spmm(sparse_matrix, dense_matrix, row_indices, output_size)
    
    # Print the result
    logger.info("SpMM functional test result:")
    logger.info(pformat(result))
    
    return result

if __name__ == "__main__":
    # First run a functional test to verify the algorithm works
    functional_result = functional_test()
    
    # Then test HLS compilation and generate visualizations
    hls_result = test_spmm() 