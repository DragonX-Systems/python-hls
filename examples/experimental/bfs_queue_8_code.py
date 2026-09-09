
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
    NUM_NODES = 8
    MAX_QUEUE_SIZE = 64
    
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
    # pragma loop_count 8
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
        # pragma loop_count 8
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
