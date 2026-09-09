# def bfs_queue(adjacency_list, source_node, num_nodes):
#     """
#     Perform Breadth-First Search using a queue-based approach.
#     This implementation uses a FIFO queue to process nodes one by one.
    
#     Args:
#         adjacency_list: A flattened representation of the graph's adjacency list.
#                         Format: [node0_num_neighbors, node0_neighbor1, node0_neighbor2, ..., 
#                                  node1_num_neighbors, node1_neighbor1, ...]
#         source_node: The starting node for the BFS
#         num_nodes: Total number of nodes in the graph
        
#     Returns:
#         A list of distances from source node to each node in the graph
#     """
#     # Memory size annotations for the HLS scheduler
#     adjacency_list_memory_size = len(adjacency_list)  # Variable size
    
#     # Output distance array
#     # pragma hls memory_type RAM
#     distances = [-1] * num_nodes  # -1 indicates node not yet visited
#     distances_memory_size = num_nodes
    
#     # Queue for BFS (implemented as a circular buffer)
#     # pragma hls memory_type RAM
#     queue = [0] * num_nodes
#     queue_memory_size = num_nodes
    
#     # Queue front and rear pointers
#     front = 0
#     rear = 0
    
#     # Pragma: Enable pipeline optimization for this function
#     # pragma hls pipeline enable
    
#     # Pragma: Graph operation hint
#     # pragma hls graph_operation bfs_queue
    
#     # Initialize queue with source node
#     distances[source_node] = 0
#     queue[rear] = source_node
#     rear = (rear + 1) % num_nodes
    
#     # Continue until queue is empty
#     # pragma hls pipeline enable
#     # pragma loop_count 64
#     while front != rear:  # Queue not empty
#         # Dequeue a node
#         current_node = queue[front]
#         front = (front + 1) % num_nodes
        
#         # Get the offset in adjacency list for this node
#         offset = 0
#         # pragma loop_count 32
#         for i in range(current_node):
#             # Skip past previous nodes' entries
#             offset += 1 + adjacency_list[offset]  # 1 for count + num_neighbors
        
#         # Get number of neighbors for this node
#         num_neighbors = adjacency_list[offset]
        
#         # Process all neighbors
#         # pragma hls pipeline enable
#         # pragma loop_count 8
#         for i in range(num_neighbors):
#             neighbor = adjacency_list[offset + 1 + i]
            
#             # If neighbor not yet visited
#             if distances[neighbor] == -1:
#                 # Mark as visited with distance = parent's distance + 1
#                 distances[neighbor] = distances[current_node] + 1
                
#                 # Enqueue neighbor
#                 queue[rear] = neighbor
#                 rear = (rear + 1) % num_nodes
    
#     return distances


def bfs_queue_optimized(adjacency_matrix, source_node, num_nodes, max_queue_size=32):
    """
    Optimized BFS implementation using a queue and adjacency matrix.
    This implementation uses a fixed-size circular buffer for the queue.
    
    Sized for 16-node graphs to match Cadence benchmarks.
    
    Args:
        adjacency_matrix: A flattened num_nodes x num_nodes adjacency matrix where
                         adjacency_matrix[i*num_nodes + j] = 1 if edge from i to j exists
        source_node: The starting node for the BFS
        num_nodes: Total number of nodes in the graph (16 for benchmark)
        max_queue_size: Maximum size of the queue buffer (32 for 16-node graphs)
        
    Returns:
        A list of distances from source node to each node in the graph
    """
    # Memory size annotations for the HLS scheduler
    MAX_NODES = 16  # Fixed size for fair comparison with Cadence
    adjacency_matrix_memory_size = MAX_NODES * MAX_NODES
    
    # Output distance array
    # pragma hls memory_type RAM
    distances = [MAX_NODES] * MAX_NODES  # MAX_NODES indicates infinity (unreachable)
    distances_memory_size = MAX_NODES
    
    # Visited flags
    # pragma hls memory_type RAM
    visited = [0] * MAX_NODES
    visited_memory_size = MAX_NODES
    
    # Queue for BFS (fixed-size circular buffer)
    # pragma hls memory_type RAM
    queue = [0] * max_queue_size
    queue_memory_size = max_queue_size
    
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
    rear = (rear + 1) % max_queue_size
    queue_count += 1
    
    # Main BFS loop
    # pragma hls pipeline enable
    # pragma loop_count 32
    while queue_count > 0:
        # Dequeue node
        current_node = queue[front]
        front = (front + 1) % max_queue_size
        queue_count -= 1
        
        # Process all possible neighbors
        # pragma hls pipeline enable
        # pragma loop_count 16
        for neighbor in range(MAX_NODES):
            # Check if there's an edge and neighbor not visited
            if adjacency_matrix[current_node*MAX_NODES + neighbor] == 1 and visited[neighbor] == 0:
                # Mark as visited
                visited[neighbor] = 1
                
                # Set distance
                distances[neighbor] = distances[current_node] + 1
                
                # Enqueue neighbor if queue not full
                if queue_count < max_queue_size:
                    queue[rear] = neighbor
                    rear = (rear + 1) % max_queue_size
                    queue_count += 1
    
    return distances


# def test_bfs_queue():
#     """Test the BFS queue implementations with a small example graph"""
#     # Create a 16-node test graph (ring topology for predictable results)
#     # Graph: 0-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-0 (circular)
#     MAX_NODES = 16
    
#     # Adjacency list representation
#     # Format: [num_neighbors, neighbors, num_neighbors, neighbors, ...]
#     adj_list = []
#     for i in range(MAX_NODES):
#         # Each node connects to next node (and previous for undirected)
#         next_node = (i + 1) % MAX_NODES
#         prev_node = (i - 1) % MAX_NODES
#         adj_list.extend([2, next_node, prev_node])  # 2 neighbors each
    
#     # Adjacency matrix representation
#     # 16x16 matrix flattened to 1D array
#     adj_matrix = [0] * (MAX_NODES * MAX_NODES)
#     for i in range(MAX_NODES):
#         next_node = (i + 1) % MAX_NODES
#         prev_node = (i - 1) % MAX_NODES
#         # Undirected edges
#         adj_matrix[i * MAX_NODES + next_node] = 1
#         adj_matrix[i * MAX_NODES + prev_node] = 1
    
#     # Test the first implementation
#     result1 = bfs_queue(adj_list, 0, MAX_NODES)
    
#     # Test the optimized implementation
#     result2 = bfs_queue_optimized(adj_matrix, 0, MAX_NODES)
    
#     return result1, result2


# if __name__ == "__main__":
#     test_bfs_queue() 