import os
import sys
import logging
from pprint import pformat

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mentor_spmm_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mentor_spmm_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import HLS tools
from python_hls import HLS

# Import the mentor_spmm function from the example file
from mentor_spmm_example import mentor_spmm

def test_mentor_spmm():
    """Test the mentor_spmm function and generate visualizations"""
    logger.info("=" * 80)
    logger.info("Testing Mentor SpMM implementation")
    logger.info("=" * 80)
    
    # Create an HLS instance
    hls = HLS(optimization_level=1, tech_node=45)
    
    # Compile the mentor_spmm_example.py file
    try:
        logger.info("Compiling Mentor SpMM code")
        
        # Path to the mentor_spmm_example.py file
        filepath = os.path.join(current_dir, "mentor_spmm_example.py")
        
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
        datapath_file = hls.visualize_datapath(output_file="mentor_spmm_datapath.png")
        scheduled_file = hls.visualize_scheduled_datapath(output_file="mentor_spmm_scheduled_datapath.png")
        control_file = hls.visualize_control_flow(output_file="mentor_spmm_control_flow.png")
        netlist_file = hls.visualize_netlist(output_file="mentor_spmm_netlist.png")
        
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
    """Test the actual functionality of the mentor_spmm function"""
    # Example sparse matrix in CSC format (from mentor_spmm_example.py)
    sparse_matrix = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    dense_matrix = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    row_indices = [0, 2, 1, 3, 0, 2, 1, 3]
    output_size = 4
    
    # Run the Mentor SpMM function
    result = mentor_spmm(sparse_matrix, dense_matrix, row_indices, output_size)
    
    # Print the result
    logger.info("SpMM functional test result:")
    logger.info(pformat(result))
    
    return result

if __name__ == "__main__":
    # First run a functional test to verify the algorithm works
    functional_result = functional_test()
    
    # Then test HLS compilation and generate visualizations
    hls_result = test_mentor_spmm() 