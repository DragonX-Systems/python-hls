# def bfs_bulk(adjacency_list, source_node, num_nodes):
#     """
#     Perform Breadth-First Search using a bulk processing approach.
#     This implementation processes nodes in batches (levels) rather than one by one.
    
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
    
#     # Current frontier (nodes to process in current level)
#     # pragma hls memory_type RAM
#     current_frontier = [0] * num_nodes
#     current_frontier_memory_size = num_nodes
    
#     # Next frontier (nodes to process in next level)
#     # pragma hls memory_type RAM
#     next_frontier = [0] * num_nodes
#     next_frontier_memory_size = num_nodes
    
#     # Size of each frontier
#     current_size = 0
#     next_size = 0
    
#     # Pragma: Enable pipeline optimization for this function
#     # pragma hls pipeline enable
    
#     # Pragma: Graph operation hint
#     # pragma hls graph_operation bfs
    
#     # Initialize with source node
#     distances[source_node] = 0
#     current_frontier[0] = source_node
#     current_size = 1
    
#     # Current distance level
#     level = 1
    
#     # Continue until current frontier is empty
#     # pragma hls pipeline enable
#     # pragma loop_count 64
#     while current_size > 0:
#         # Reset next frontier
#         next_size = 0
        
#         # Process all nodes in current frontier
#         # pragma hls pipeline enable
#         # pragma loop_count 32
#         for i in range(current_size):
#             node = current_frontier[i]
            
#             # Get the offset in adjacency list for this node
#             offset = 0
#             # pragma loop_count 32
#             for j in range(node):
#                 # Skip past previous nodes' entries
#                 offset += 1 + adjacency_list[offset]  # 1 for count + num_neighbors
            
#             # Get number of neighbors for this node
#             num_neighbors = adjacency_list[offset]
            
#             # Process all neighbors
#             # pragma hls pipeline enable
#             # pragma loop_count 8
#             for j in range(num_neighbors):
#                 neighbor = adjacency_list[offset + 1 + j]
                
#                 # If neighbor not yet visited
#                 if distances[neighbor] == -1:
#                     # Mark as visited with current level distance
#                     distances[neighbor] = level
                    
#                     # Add to next frontier
#                     next_frontier[next_size] = neighbor
#                     next_size += 1
        
#         # Swap frontiers
#         # pragma hls unroll
#         for i in range(num_nodes):
#             current_frontier[i] = next_frontier[i]
#             next_frontier[i] = 0
        
#         current_size = next_size
#         level += 1
    
#     return distances


def bfs_bulk_optimized(adjacency_matrix, source_node, num_nodes):
    """
    Optimized BFS implementation using adjacency matrix representation.
    This approach is more suitable for hardware implementation as it avoids
    variable-length lists and irregular memory access patterns.
    
    Sized for 16-node graphs to match Cadence benchmarks.
    
    Args:
        adjacency_matrix: A flattened num_nodes x num_nodes adjacency matrix where
                         adjacency_matrix[i*num_nodes + j] = 1 if edge from i to j exists
        source_node: The starting node for the BFS
        num_nodes: Total number of nodes in the graph (16 for benchmark)
        
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
    
    # Visited flags for each node
    # pragma hls memory_type RAM
    visited = [0] * MAX_NODES  # 0 = not visited, 1 = visited
    visited_memory_size = MAX_NODES
    
    # Current and next level masks
    # pragma hls memory_type RAM
    current_level = [0] * MAX_NODES
    current_level_memory_size = MAX_NODES
    
    # pragma hls memory_type RAM
    next_level = [0] * MAX_NODES
    next_level_memory_size = MAX_NODES
    
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
    # pragma loop_count 16
    while has_current_nodes:
        has_current_nodes = 0
        has_next_nodes = 0
        
        # Process all nodes in the graph
        # pragma hls pipeline enable
        # pragma loop_count 16
        for i in range(MAX_NODES):
            # If node is in current level
            if current_level[i] == 1:
                # Look at all possible neighbors
                # pragma hls pipeline enable
                # pragma loop_count 16
                for j in range(MAX_NODES):
                    # If there's an edge and node not visited
                    if adjacency_matrix[i*MAX_NODES + j] == 1 and visited[j] == 0:
                        # Mark for next level
                        next_level[j] = 1
                        has_next_nodes = 1
                        # Set distance
                        distances[j] = level
                        # Mark as visited
                        visited[j] = 1
            
        # Move to next level
        # pragma loop_count 16
        for i in range(MAX_NODES):
            current_level[i] = next_level[i]
            next_level[i] = 0
            if current_level[i] == 1:
                has_current_nodes = 1
        
        level += 1
    
    return distances


# def test_bfs():
#     """Test the BFS implementations with a small example graph"""
#     # Create a 16-node test graph (ring topology for predictable results)
#     # Graph: 0-1-2-3-4-5-6-7-8-9-10-11-12-13-14-15-0 (circular)
#     MAX_NODES = 16
    
#     # Adjacency list representation for first implementation
#     # Format: [num_neighbors, neighbors, num_neighbors, neighbors, ...]
#     adj_list = []
#     for i in range(MAX_NODES):
#         # Each node connects to next node (and previous for undirected)
#         next_node = (i + 1) % MAX_NODES
#         prev_node = (i - 1) % MAX_NODES
#         adj_list.extend([2, next_node, prev_node])  # 2 neighbors each
    
#     # Adjacency matrix representation for optimized implementation
#     # 16x16 matrix flattened to 1D array
#     adj_matrix = [0] * (MAX_NODES * MAX_NODES)
#     for i in range(MAX_NODES):
#         next_node = (i + 1) % MAX_NODES
#         prev_node = (i - 1) % MAX_NODES
#         # Undirected edges
#         adj_matrix[i * MAX_NODES + next_node] = 1
#         adj_matrix[i * MAX_NODES + prev_node] = 1
    
#     # Test the first implementation
#     result1 = bfs_bulk(adj_list, 0, MAX_NODES)
    
#     # Test the optimized implementation
#     result2 = bfs_bulk_optimized(adj_matrix, 0, MAX_NODES)
    
#     return result1, result2


# if __name__ == "__main__":
#     test_bfs() 