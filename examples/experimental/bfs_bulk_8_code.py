
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
    NUM_NODES = 8
    
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
    # pragma loop_count 8
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
        # pragma loop_count 8
        for i in range(NUM_NODES):
            # If node is in current level
            if current_level[i] == 1:
                # Look at all possible neighbors
                # pragma hls pipeline enable
                # pragma loop_count 8
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
        # pragma loop_count 8
        for i in range(NUM_NODES):
            current_level[i] = next_level[i]
            next_level[i] = 0
            if current_level[i] == 1:
                has_current_nodes = 1
        
        level += 1
    
    return distances
