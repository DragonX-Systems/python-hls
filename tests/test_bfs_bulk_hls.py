import os
import sys
import time
import ast
import logging
import copy
import shutil
from pprint import pformat
import unittest

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bfs_bulk_hls_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bfs_bulk_hls_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS
from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator

def create_bfs_bulk_code(num_nodes):
    """Create BFS bulk code with a given number of nodes"""
    # Scale parameters based on number of nodes
    max_edges = num_nodes * 2  # Assume sparse graph
    
    return f"""
def bfs_bulk(adjacency_matrix, source_node, num_nodes):
    '''
    Perform Breadth-First Search using a bulk processing approach.
    This implementation processes nodes in batches (levels) rather than one by one.
    
    Args:
        adjacency_matrix: A flattened num_nodes x num_nodes adjacency matrix
        source_node: The starting node for the BFS
        num_nodes: Total number of nodes in the graph
        
    Returns:
        A list of distances from source node to each node in the graph
    '''
    # Memory size annotations for the HLS scheduler
    NUM_NODES = {num_nodes}
    
    # Output distance array
    # pragma hls memory_type RAM
    distances = [NUM_NODES] * NUM_NODES  # NUM_NODES indicates infinity (unreachable)
    distances_memory_size = NUM_NODES
    
    # Visited flags for each node
    # pragma hls memory_type RAM
    visited = [0] * NUM_NODES  # 0 = not visited, 1 = visited
    visited_memory_size = NUM_NODES
    
    # Current and next level masks
    # pragma hls memory_type RAM
    current_level = [0] * NUM_NODES
    current_level_memory_size = NUM_NODES
    
    # pragma hls memory_type RAM
    next_level = [0] * NUM_NODES
    next_level_memory_size = NUM_NODES
    
    # Initialize adjacency matrix (for testing)
    # pragma hls memory_type RAM
    adj_matrix = [0] * (NUM_NODES * NUM_NODES)
    adj_matrix_memory_size = NUM_NODES * NUM_NODES
    
    # Create a simple test graph (ring topology for predictable results)
    # pragma loop_count {num_nodes}
    for i in range(NUM_NODES):
        # Connect each node to the next one (ring)
        next_node = (i + 1) % NUM_NODES
        adj_matrix[i * NUM_NODES + next_node] = 1
        adj_matrix[next_node * NUM_NODES + i] = 1  # Undirected graph
    
    # Pragma: Enable pipeline optimization for this function
    # pragma hls pipeline enable
    
    # Pragma: Graph operation hint
    # pragma hls graph_operation bfs_matrix
    
    # Initialize with source node
    distances[source_node] = 0
    current_level[source_node] = 1
    visited[source_node] = 1
    
    # Current distance level
    level = 1
    
    # Flag to track if any nodes are in current level
    has_current_nodes = 1
    
    # Continue until no more nodes to process
    # pragma hls pipeline enable
    # pragma loop_count 32
    while has_current_nodes and level < NUM_NODES:
        has_current_nodes = 0
        has_next_nodes = 0
        
        # Process all nodes in the graph
        # pragma hls pipeline enable
        # pragma loop_count {num_nodes}
        for i in range(NUM_NODES):
            # If node is in current level
            if current_level[i] == 1:
                # Look at all possible neighbors
                # pragma hls pipeline enable
                # pragma loop_count {num_nodes}
                for j in range(NUM_NODES):
                    # If there's an edge and node not visited
                    if adj_matrix[i*NUM_NODES + j] == 1 and visited[j] == 0:
                        # Mark for next level
                        next_level[j] = 1
                        has_next_nodes = 1
                        # Set distance
                        distances[j] = level
                        # Mark as visited
                        visited[j] = 1
        
        # Move to next level
        # pragma hls unroll factor=4
        # pragma loop_count {num_nodes}
        for i in range(NUM_NODES):
            current_level[i] = next_level[i]
            next_level[i] = 0
            if current_level[i] == 1:
                has_current_nodes = 1
        
        level += 1
    
    return distances
"""

def write_bfs_bulk_file(num_nodes, filename):
    """Write BFS bulk code to a file"""
    code = create_bfs_bulk_code(num_nodes)
    with open(filename, "w") as f:
        f.write(code)
    # Also save to a visible location for inspection
    with open(f"bfs_bulk_{num_nodes}_code.py", "w") as f:
        f.write(code)
    return filename

def analyze_bfs_bulk(num_nodes):
    """Analyze BFS bulk code with specified number of nodes"""
    logger.info(f"=" * 80)
    logger.info(f"Analyzing BFS Bulk with {num_nodes} nodes")
    logger.info(f"=" * 80)
    
    # Create a temporary directory for test output
    import tempfile
    import shutil
    test_dir = tempfile.mkdtemp()
    
    try:
        # Generate code and save to file
        filepath = os.path.join(test_dir, f"bfs_bulk_{num_nodes}.py")
        write_bfs_bulk_file(num_nodes, filepath)
        logger.info(f"Generated BFS Bulk code with {num_nodes} nodes in {filepath}")
        
        # Create an HLS instance
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile the BFS bulk code
        try:
            logger.info(f"Compiling BFS Bulk code with {num_nodes} nodes")
            
            # Perform the compilation
            netlist = hls.compile(filepath, target="verilog")
            
            # Get performance metrics
            metrics = hls.get_performance_metrics()
            opt_report = hls.get_optimization_report()
            opt_summary = hls.get_optimization_summary()
            
            logger.info(f"RESULTS for {num_nodes} nodes:")
            logger.info(f"  - Technology node: {metrics['technology_node']}")
            logger.info(f"  - Total area: {metrics['total_area']}")
            logger.info(f"  - Total power: {metrics['total_power']}")
            logger.info(f"  - Critical path: {metrics['critical_path']}")
            logger.info(f"  - Latency cycles: {metrics['latency_cycles']}")
            logger.info(f"  - Power breakdown: {metrics['power_breakdown']}")
            logger.info(f"  - Optimization summary: {opt_summary}")
            
            # Clean up
            shutil.rmtree(test_dir)
            
            return {
                "netlist": netlist,
                "metrics": metrics,
                "opt_report": opt_report,
                "opt_summary": opt_summary
            }
            
        except Exception as e:
            logger.error(f"Error during compilation: {e}")
            # Clean up
            shutil.rmtree(test_dir)
            raise

    except Exception as e:
        logger.error(f"Error during BFS Bulk analysis: {e}")
        # Clean up
        shutil.rmtree(test_dir)
        raise

def main():
    """Main function to run tests"""
    logger.info("Starting BFS Bulk HLS analysis")
    
    # Analyze with 16 nodes
    results_16 = analyze_bfs_bulk(16)
    
    # Analyze with 32 nodes
    results_32 = analyze_bfs_bulk(32)
    
    # Compare results
    logger.info("=" * 80)
    logger.info("COMPARISON OF RESULTS:")
    logger.info("=" * 80)
    
    # Compare performance metrics
    metrics_16 = results_16["metrics"]
    metrics_32 = results_32["metrics"]
    
    logger.info(f"Total area for 16 nodes: {metrics_16['total_area']}")
    logger.info(f"Total area for 32 nodes: {metrics_32['total_area']}")
    logger.info(f"Area ratio 32/16: {metrics_32['total_area']/metrics_16['total_area'] if metrics_16['total_area'] != 0 else 'N/A'}")
    
    logger.info(f"Critical path for 16 nodes: {metrics_16['critical_path']}")
    logger.info(f"Critical path for 32 nodes: {metrics_32['critical_path']}")
    logger.info(f"Critical path ratio 32/16: {metrics_32['critical_path']/metrics_16['critical_path'] if metrics_16['critical_path'] != 0 else 'N/A'}")
    
    logger.info(f"Latency cycles for 16 nodes: {metrics_16['latency_cycles']}")
    logger.info(f"Latency cycles for 32 nodes: {metrics_32['latency_cycles']}")
    logger.info(f"Latency ratio 32/16: {metrics_32['latency_cycles']/metrics_16['latency_cycles'] if metrics_16['latency_cycles'] != 0 else 'N/A'}")
    
    return results_16, results_32


class TestBFSBulk(unittest.TestCase):
    """Test BFS Bulk HLS functionality"""
    
    def test_bfs_bulk_hls(self):
        """Test that BFS Bulk HLS compilation runs successfully"""
        # Run the analysis with a small size for testing
        results = analyze_bfs_bulk(8)
        
        # Verify results
        self.assertIsNotNone(results["netlist"], "Netlist should not be None")
        self.assertGreater(results["metrics"]["total_area"], 0, "Area should be greater than 0")
        self.assertGreater(results["metrics"]["latency_cycles"], 0, "Latency should be greater than 0")


if __name__ == "__main__":
    main() 