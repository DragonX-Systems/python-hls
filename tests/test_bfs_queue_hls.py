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
        logging.FileHandler("bfs_queue_hls_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("bfs_queue_hls_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS
from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator

def create_bfs_queue_code(num_nodes, max_queue_size=64):
    """Create BFS queue code with a given number of nodes"""
    
    return f"""
def bfs_queue(adjacency_matrix, source_node, num_nodes, max_queue_size):
    '''
    Perform Breadth-First Search using a queue-based approach.
    This implementation uses a FIFO queue to process nodes one by one.
    
    Args:
        adjacency_matrix: A flattened num_nodes x num_nodes adjacency matrix
        source_node: The starting node for the BFS
        num_nodes: Total number of nodes in the graph
        max_queue_size: Maximum size of the queue buffer
        
    Returns:
        A list of distances from source node to each node in the graph
    '''
    # Memory size annotations for the HLS scheduler
    NUM_NODES = {num_nodes}
    MAX_QUEUE_SIZE = {max_queue_size}
    
    # Output distance array
    # pragma hls memory_type RAM
    distances = [NUM_NODES] * NUM_NODES  # NUM_NODES indicates infinity (unreachable)
    distances_memory_size = NUM_NODES
    
    # Visited flags
    # pragma hls memory_type RAM
    visited = [0] * NUM_NODES
    visited_memory_size = NUM_NODES
    
    # Queue for BFS (fixed-size circular buffer)
    # pragma hls memory_type RAM
    queue = [0] * MAX_QUEUE_SIZE
    queue_memory_size = MAX_QUEUE_SIZE
    
    # Initialize adjacency matrix (for testing)
    # pragma hls memory_type RAM
    adj_matrix = [0] * (NUM_NODES * NUM_NODES)
    adj_matrix_memory_size = NUM_NODES * NUM_NODES
    
    # Create a simple test graph (linear chain for predictable results)
    # pragma loop_count {num_nodes}
    for i in range(NUM_NODES - 1):
        # Connect each node to the next one (linear chain)
        adj_matrix[i * NUM_NODES + (i + 1)] = 1
        adj_matrix[(i + 1) * NUM_NODES + i] = 1  # Undirected graph
    
    # Queue management variables
    front = 0
    rear = 0
    queue_count = 0  # Track number of elements in queue
    
    # Pragma: Enable pipeline optimization for this function
    # pragma hls pipeline enable
    
    # Pragma: Queue operation hint
    # pragma hls queue_operation circular_buffer
    
    # Initialize with source node
    distances[source_node] = 0
    visited[source_node] = 1
    
    # Enqueue source node
    queue[rear] = source_node
    rear = (rear + 1) % MAX_QUEUE_SIZE
    queue_count += 1
    
    # Main BFS loop
    # pragma hls pipeline enable
    # pragma loop_count 128
    while queue_count > 0:
        # Dequeue node
        current_node = queue[front]
        front = (front + 1) % MAX_QUEUE_SIZE
        queue_count -= 1
        
        # Process all possible neighbors
        # pragma hls pipeline enable
        # pragma loop_count {num_nodes}
        for neighbor in range(NUM_NODES):
            # Check if there's an edge and neighbor not visited
            if adj_matrix[current_node*NUM_NODES + neighbor] == 1 and visited[neighbor] == 0:
                # Mark as visited
                visited[neighbor] = 1
                
                # Set distance
                distances[neighbor] = distances[current_node] + 1
                
                # Enqueue neighbor if queue not full
                if queue_count < MAX_QUEUE_SIZE:
                    queue[rear] = neighbor
                    rear = (rear + 1) % MAX_QUEUE_SIZE
                    queue_count += 1
    
    return distances
"""

def write_bfs_queue_file(num_nodes, filename):
    """Write BFS queue code to a file"""
    max_queue_size = max(64, num_nodes)
    code = create_bfs_queue_code(num_nodes, max_queue_size)
    with open(filename, "w") as f:
        f.write(code)
    # Also save to a visible location for inspection
    with open(f"bfs_queue_{num_nodes}_code.py", "w") as f:
        f.write(code)
    return filename

def analyze_bfs_queue(num_nodes):
    """Analyze BFS queue code with specified number of nodes"""
    logger.info(f"=" * 80)
    logger.info(f"Analyzing BFS Queue with {num_nodes} nodes")
    logger.info(f"=" * 80)
    
    # Create a temporary directory for test output
    import tempfile
    import shutil
    test_dir = tempfile.mkdtemp()
    
    try:
        # Generate code and save to file
        filepath = os.path.join(test_dir, f"bfs_queue_{num_nodes}.py")
        write_bfs_queue_file(num_nodes, filepath)
        logger.info(f"Generated BFS Queue code with {num_nodes} nodes in {filepath}")
        
        # Create an HLS instance
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile the BFS queue code
        try:
            logger.info(f"Compiling BFS Queue code with {num_nodes} nodes")
            
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
        logger.error(f"Error during BFS Queue analysis: {e}")
        # Clean up
        shutil.rmtree(test_dir)
        raise

def main():
    """Main function to run tests"""
    logger.info("Starting BFS Queue HLS analysis")
    
    # Analyze with 16 nodes
    results_16 = analyze_bfs_queue(16)
    
    # Analyze with 32 nodes
    results_32 = analyze_bfs_queue(32)
    
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


class TestBFSQueue(unittest.TestCase):
    """Test BFS Queue HLS functionality"""
    
    def test_bfs_queue_hls(self):
        """Test that BFS Queue HLS compilation runs successfully"""
        # Run the analysis with a small size for testing
        results = analyze_bfs_queue(8)
        
        # Verify results
        self.assertIsNotNone(results["netlist"], "Netlist should not be None")
        self.assertGreater(results["metrics"]["total_area"], 0, "Area should be greater than 0")
        self.assertGreater(results["metrics"]["latency_cycles"], 0, "Latency should be greater than 0")


if __name__ == "__main__":
    main() 