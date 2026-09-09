"""
Schedulers for HLS scheduling algorithms.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Set, Optional, Tuple
import networkx as nx
import inspect

from ..ir.ir_nodes import (
    IR, IRFunction, IRBlock, IRInstruction, IROperation, 
    IRVariable, IRConstant, OperationType, DataType
)
from ..tech.tech_library import TechLibrary

# Get logger for this module
logger = logging.getLogger('python_hls.hls_engine.scheduler')


class Scheduler(ABC):
    """Abstract base class for HLS schedulers."""
    
    def __init__(self, tech_library: TechLibrary):
        """
        Initialize the scheduler.
        
        Args:
            tech_library: Technology library for resource models
        """
        self.tech_library = tech_library
    
    @abstractmethod
    def schedule(self, ir: IR) -> IR:
        """
        Schedule operations in the IR.
        
        Args:
            ir: IR to schedule
            
        Returns:
            Scheduled IR
        """
        pass
    
    def _build_dfg(self, func: IRFunction) -> nx.DiGraph:
        """
        Build a data flow graph (DFG) for a function.
        
        Args:
            func: Function to build DFG for
            
        Returns:
            DFG as a networkx DiGraph
        """
        dfg = nx.DiGraph()
        
        # Operations are nodes
        op_nodes = []
        
        # Track operations that operate on the same variables
        var_consumers = {}  # Dict[variable_id, List[op_id]]
        var_producers = {}  # Dict[variable_id, List[op_id]]
        
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    # Debug print to see what operations are being scheduled
                    logger.debug(f"Adding operation to DFG: {op.name} (type: {op.op_type.name})")
                    dfg.add_node(op.node_id, op=op, block=block)  # Store block reference
                    op_nodes.append(op)
                    
                    # Track which variables this operation reads from and writes to
                    if hasattr(op, 'result') and op.result is not None:
                        result_id = op.result.node_id
                        if result_id not in var_producers:
                            var_producers[result_id] = []
                        var_producers[result_id].append(op.node_id)
                    
                    for operand in op.operands:
                        if hasattr(operand, 'node_id'):  # Only for IR nodes, not constants
                            operand_id = operand.node_id
                            if operand_id not in var_consumers:
                                var_consumers[operand_id] = []
                            var_consumers[operand_id].append(op.node_id)
        
        # Add data dependencies first - an operation depends on operations that produce its operands
        # This ensures proper flow of variable values
        for var_id, consumer_ops in var_consumers.items():
            if var_id in var_producers:
                for producer_op in var_producers[var_id]:
                    for consumer_op in consumer_ops:
                        if producer_op != consumer_op:  # Avoid self-loops
                            # Add edge from producer to consumer
                            logger.debug(f"Adding data dependency: {dfg.nodes[producer_op]['op'].name} -> {dfg.nodes[consumer_op]['op'].name}")
                            dfg.add_edge(producer_op, consumer_op, type="data")
        
        # Now add control dependencies - operations in the same block should respect program order
        for block in func.blocks:
            prev_op = None
            for instr in block.instructions:
                for op in instr.operations:
                    if prev_op is not None and prev_op.node_id != op.node_id:
                        # Only add control edge if there's no data dependency already
                        if not dfg.has_edge(prev_op.node_id, op.node_id):
                            logger.debug(f"Adding control dependency: {prev_op.name} -> {op.name}")
                            dfg.add_edge(prev_op.node_id, op.node_id, type="control")
                    prev_op = op
        
        # Additional inter-block control dependencies based on CFG
        for block in func.blocks:
            # Operations in predecessors should execute before operations in this block
            for pred_block in block.predecessors:
                if pred_block != block:  # Skip self-loops
                    # Find last operation in predecessor block
                    pred_ops = [op for instr in pred_block.instructions for op in instr.operations]
                    if pred_ops:
                        last_pred_op = pred_ops[-1]
                        
                        # Find first operation in current block
                        curr_ops = [op for instr in block.instructions for op in instr.operations]
                        if curr_ops:
                            first_curr_op = curr_ops[0]
                            
                            # Add control dependency from last op in predecessor to first op in current
                            if not dfg.has_edge(last_pred_op.node_id, first_curr_op.node_id):
                                logger.debug(f"Adding block transition dependency: {last_pred_op.name} -> {first_curr_op.name}")
                                dfg.add_edge(last_pred_op.node_id, first_curr_op.node_id, type="block_transition")
        
        # Add loop-carried dependencies
        for block in func.blocks:
            if block.loop_header == block:  # This is a loop header
                # Find operations that update loop variables
                loop_var_ops = []
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.op_type in [OperationType.ASSIGN, OperationType.ADD, OperationType.SUB]:
                            if hasattr(op, 'result') and op.result is not None:
                                loop_var_ops.append(op)
                
                # Find operations in loop body blocks
                for body_block in self._get_loop_body_blocks(block) + [block]:
                    for instr in body_block.instructions:
                        for op in instr.operations:
                            # Check if this operation uses loop variables
                            for loop_var_op in loop_var_ops:
                                if hasattr(loop_var_op, 'result') and loop_var_op.result is not None:
                                    for operand in op.operands:
                                        if hasattr(operand, 'node_id') and hasattr(loop_var_op.result, 'node_id'):
                                            if operand.node_id == loop_var_op.result.node_id:
                                                # This operation depends on a loop variable
                                                logger.debug(f"Adding loop-carried dependency: {loop_var_op.name} -> {op.name}")
                                                dfg.add_edge(loop_var_op.node_id, op.node_id, type="loop_carried")
        
        # We'll save adding priority edges until later after we establish that
        # the basic DFG structure is acyclic
        base_dfg = dfg.copy()
        
        # Check if the base graph has cycles already
        try:
            list(nx.topological_sort(base_dfg))
        except nx.NetworkXUnfeasible:
            logger.warning("Base graph already contains cycles. Fixing...")
            self._fix_cycles(base_dfg)
        
        # Now add priority edges for special operations like RETURN
        return_ops = [op for op in op_nodes if op.op_type.name in ['RETURN', 'STORE']]
        other_ops = [op for op in op_nodes if op.op_type.name not in ['RETURN', 'STORE']]
        
        # For each return operation, ensure it depends on other key operations
        for ret_op in return_ops:
            for other_op in other_ops:
                # Skip if there's already a path or if adding edge would create a cycle
                path_exists = False
                try:
                    path_exists = nx.has_path(base_dfg, other_op.node_id, ret_op.node_id)
                except:
                    pass  # If error in path check, assume no path exists
                
                if not path_exists:
                    # Create a temporary graph to test if adding this edge would create a cycle
                    test_dfg = base_dfg.copy()
                    test_dfg.add_edge(other_op.node_id, ret_op.node_id)
                    try:
                        list(nx.topological_sort(test_dfg))
                        # If we get here, no cycle was created
                        logger.debug(f"Adding priority edge: {other_op.name} -> {ret_op.name}")
                        base_dfg.add_edge(other_op.node_id, ret_op.node_id)
                    except nx.NetworkXUnfeasible:
                        logger.debug(f"Skipping priority edge: {other_op.name} -> {ret_op.name} (would create cycle)")
                        pass
        
        # Check if the graph is empty
        if len(base_dfg.nodes) == 0:
            logger.warning("Data flow graph is empty. No operations to schedule.")
            return base_dfg
        
        # Check if the graph is disconnected
        if len(base_dfg.nodes) > 1 and not nx.is_weakly_connected(base_dfg):
            logger.warning("Data flow graph is disconnected. Attempting to connect components...")
            # Find all weakly connected components
            components = list(nx.weakly_connected_components(base_dfg))
            if len(components) > 1:
                logger.info(f"Found {len(components)} disconnected components")
                # Try to connect components in a reasonable way
                self._connect_components(base_dfg, components, func)
        
        # Final check for cycles and fix if needed
        try:
            list(nx.topological_sort(base_dfg))
        except nx.NetworkXUnfeasible:
            logger.error("Final DFG contains cycles. Attempting to fix...")
            self._fix_cycles(base_dfg)
            
        return base_dfg
        
    def _fix_cycles(self, graph: nx.DiGraph) -> None:
        """
        Find and break cycles in a directed graph.
        
        Args:
            graph: Directed graph to fix
        """
        # Safety check - if graph is empty, nothing to do
        if len(graph.nodes) == 0:
            logger.debug("Empty graph - no cycles to fix")
            return
            
        # Track original edge count for progress monitoring
        original_edge_count = len(graph.edges)
        logger.debug(f"Fixing cycles in graph with {len(graph.nodes)} nodes and {original_edge_count} edges")
        
        # Try to find cycles
        try:
            cycles = list(nx.simple_cycles(graph))
            
            if not cycles:
                logger.warning("No simple cycles found but graph is not acyclic")
                # Fall back to a simpler approach - find and remove feedback edges
                try:
                    feedback_edges = list(nx.algorithms.cycles.find_cycle(graph))
                    for edge in feedback_edges:
                        u, v = edge
                        if graph.has_edge(u, v):  # Safety check
                            logger.debug(f"Breaking cycle by removing feedback edge: {graph.nodes[u]['op'].name} -> {graph.nodes[v]['op'].name}")
                            graph.remove_edge(u, v)
                except nx.NetworkXNoCycle:
                    logger.info("No cycles found - graph is already acyclic")
                    return
                except Exception as e:
                    logger.warning(f"Error finding feedback edges: {e}")
                return
                
            logger.info(f"Found {len(cycles)} cycles in the graph")
            
            # Process each cycle
            edges_removed = 0
            for cycle in cycles:
                if len(cycle) > 1:
                    # Identify the best edge to remove - prefer edges that aren't data dependencies
                    # We'll use a simple heuristic: remove the last edge in the cycle
                    u, v = cycle[-1], cycle[0]
                    if graph.has_edge(u, v):  # Safety check
                        logger.debug(f"Breaking cycle by removing edge: {graph.nodes[u]['op'].name} -> {graph.nodes[v]['op'].name}")
                        graph.remove_edge(u, v)
                        edges_removed += 1
            
            # Verify the fix worked
            try:
                list(nx.topological_sort(graph))
                logger.info(f"Graph cycles resolved after removing {edges_removed} edges")
            except nx.NetworkXUnfeasible:
                logger.warning("Failed to resolve all cycles. Trying more aggressive approach...")
                # More aggressive approach - keep removing edges until acyclic
                max_iterations = min(3, len(graph.edges))  # Limit iterations to prevent infinite loop
                if max_iterations == 0:  # Safety check for empty graphs
                    max_iterations = 1
                    
                iteration = 0
                edges_removed_aggressive = 0
                initial_edge_count = len(graph.edges)
                
                logger.info(f"Starting aggressive cycle removal: max_iterations={max_iterations}, initial_edges={initial_edge_count}")
                
                while iteration < max_iterations:
                    try:
                        list(nx.topological_sort(graph))
                        logger.info(f"Graph is now acyclic after {iteration} additional iterations and {edges_removed_aggressive} edge removals")
                        break
                    except nx.NetworkXUnfeasible:
                        # Find a cycle
                        try:
                            cycle = list(nx.algorithms.cycles.find_cycle(graph))
                            if cycle:
                                u, v = cycle[0]  # Get the first edge in the cycle
                                if graph.has_edge(u, v):  # Safety check
                                    logger.debug(f"Breaking cycle by removing edge: {graph.nodes[u]['op'].name} -> {graph.nodes[v]['op'].name}")
                                    graph.remove_edge(u, v)
                                    edges_removed_aggressive += 1
                                else:
                                    logger.warning(f"Edge {u}->{v} not found in graph")
                                    break
                            else:
                                logger.error("Cannot find any more cycles but graph is not acyclic")
                                break
                        except nx.NetworkXNoCycle:
                            logger.info("No more cycles found - graph should be acyclic now")
                            break
                        except Exception as e:
                            logger.error(f"Failed to find cycles to remove: {e}")
                            break
                    
                    iteration += 1
                    
                    # Additional safety check - if we've removed too many edges, stop
                    if edges_removed_aggressive > initial_edge_count // 2:
                        logger.warning(f"Removed {edges_removed_aggressive} edges (>{initial_edge_count//2}), stopping aggressive removal")
                        break
                
                if iteration >= max_iterations:
                    logger.error(f"Reached maximum iterations ({max_iterations}) in cycle removal - giving up")
                    # Emergency fallback: try to make the graph acyclic by removing all back edges
                    self._emergency_cycle_fix(graph)
                            
        except Exception as e:
            logger.error(f"Error detecting cycles: {str(e)}")
            # Last resort - remove all back edges to guarantee acyclic graph
            self._emergency_cycle_fix(graph)
    
    def _emergency_cycle_fix(self, graph: nx.DiGraph) -> None:
        """
        Emergency cycle fix by removing back edges using efficient DFS.
        
        Args:
            graph: Directed graph to fix
        """
        logger.warning("Applying emergency cycle fix - removing back edges")
        
        # Use DFS to efficiently identify back edges
        back_edges = []
        visited = set()
        rec_stack = set()  # Track nodes in current DFS path
        
        def dfs(node):
            """DFS to find back edges"""
            visited.add(node)
            rec_stack.add(node)
            
            for successor in graph.successors(node):
                if successor not in visited:
                    dfs(successor)
                elif successor in rec_stack:
                    # This is a back edge
                    back_edges.append((node, successor))
            
            rec_stack.remove(node)
        
        # Run DFS from all unvisited nodes
        for node in list(graph.nodes()):
            if node not in visited:
                try:
                    dfs(node)
                except Exception as e:
                    logger.warning(f"DFS failed for node {node}: {e}")
                    # If DFS fails, fall back to removing the edge if it exists
                    for successor in list(graph.successors(node)):
                        back_edges.append((node, successor))
                    break
        
        # Remove back edges
        edges_removed = 0
        for u, v in back_edges:
            if graph.has_edge(u, v):
                try:
                    logger.debug(f"Removing back edge: {graph.nodes[u]['op'].name} -> {graph.nodes[v]['op'].name}")
                    graph.remove_edge(u, v)
                    edges_removed += 1
                except Exception as e:
                    logger.warning(f"Failed to remove edge {u}->{v}: {e}")
        
        logger.info(f"Emergency cycle fix removed {edges_removed} back edges")
        
        # Verify the graph is now acyclic
        try:
            list(nx.topological_sort(graph))
            logger.info("Graph is now verified to be acyclic")
        except nx.NetworkXUnfeasible:
            logger.error("Graph still contains cycles after emergency fix - removing all remaining edges")
            # Last resort: remove all edges to make it acyclic
            edges_to_remove = list(graph.edges())
            for u, v in edges_to_remove:
                graph.remove_edge(u, v)
            logger.warning(f"Removed all {len(edges_to_remove)} edges as last resort")
    
    def _connect_components(self, graph: nx.DiGraph, components: List[Set[int]], func: IRFunction) -> None:
        """
        Connect disconnected components in the graph based on block structure.
        
        Args:
            graph: The data flow graph
            components: List of sets of node IDs for each component
            func: The function containing the blocks
        """
        # Map components to blocks
        component_blocks = {}
        for i, component in enumerate(components):
            component_blocks[i] = set()
            for node_id in component:
                block = graph.nodes[node_id]['block']
                component_blocks[i].add(block)
        
        # Sort components by block order in the function
        component_first_block = {}
        for i, blocks in component_blocks.items():
            min_idx = float('inf')
            for block in blocks:
                block_idx = func.blocks.index(block)
                min_idx = min(min_idx, block_idx)
            component_first_block[i] = min_idx
        
        sorted_components = sorted(range(len(components)), key=lambda i: component_first_block[i])
        
        # Connect components in order
        for i in range(len(sorted_components) - 1):
            curr_comp = sorted_components[i]
            next_comp = sorted_components[i + 1]
            
            # Find a reasonable node from each component to connect
            curr_nodes = list(components[curr_comp])
            next_nodes = list(components[next_comp])
            
            if curr_nodes and next_nodes:
                # Prefer to connect exit nodes (RETURN, STORE) from curr to entry nodes of next
                curr_exits = [n for n in curr_nodes if graph.nodes[n]['op'].op_type.name in ['RETURN', 'STORE']]
                next_entries = [n for n in next_nodes if graph.in_degree(n) == 0]
                
                # If no exit nodes, use the last node in program order
                if not curr_exits:
                    curr_exits = [curr_nodes[-1]]
                    
                # If no entry nodes, use the first node in program order
                if not next_entries:
                    next_entries = [next_nodes[0]]
                
                # Connect the components
                curr_node = curr_exits[0]
                next_node = next_entries[0]
                
                logger.debug(f"Connecting components: {graph.nodes[curr_node]['op'].name} -> {graph.nodes[next_node]['op'].name}")
                graph.add_edge(curr_node, next_node, type="component_link")
    
    def _get_operation_delay(self, op: IROperation) -> int:
        """
        Get the delay (latency) of an operation.
        
        Args:
            op: Operation to get delay for
            
        Returns:
            Delay in clock cycles
        """
        # Map operation types to resource types
        op_to_resource = {
            "ADD": "Adder_32bit",
            "SUB": "Subtractor_32bit",
            "MUL": "Multiplier_32bit",
            "DIV": "Divider_32bit",
            "MOD": "ALU_32bit",
            "POW": "ALU_32bit",
            "LSHIFT": "Shifter_32bit",
            "RSHIFT": "Shifter_32bit",
            "BIT_OR": "BitOp_32bit",
            "BIT_AND": "BitOp_32bit",
            "BIT_XOR": "BitOp_32bit",
            "LOGIC_OR": "BitOp_32bit",
            "LOGIC_AND": "BitOp_32bit",
            "EQ": "Comparator_32bit",
            "NEQ": "Comparator_32bit",
            "LT": "RelationalOp_32bit",
            "LTE": "RelationalOp_32bit",
            "GT": "RelationalOp_32bit",
            "GTE": "RelationalOp_32bit",
            "NEG": "Subtractor_32bit",
            "NOT": "BitOp_32bit",
            "BIT_NOT": "BitOp_32bit",
            "ASSIGN": "Register_32bit",
            "RETURN": "Register_32bit",
            "STORE": "Memory_1KB",
            "LOAD": "Memory_1KB",
            "CALL": "ALU_32bit"
        }
        
        op_type = op.op_type.name
        
        # Special handling for function calls - get the latency of the called function
        if op_type == "CALL" and hasattr(op, 'function_name'):
            function_name = op.function_name
            # Try to find the called function in the IR
            ir = self._get_ir_from_op(op)
            if ir and function_name in ir.functions:
                called_func = ir.functions[function_name]
                
                # If the called function has a calculated total_latency, use that
                if hasattr(called_func, 'total_latency') and called_func.total_latency > 0:
                    logger.info(f"  Using called function's latency for {op.name}: {called_func.total_latency} cycles")
                    return called_func.total_latency
                
                # If it has a single_iter_latency, use that as a fallback
                if hasattr(called_func, 'single_iter_latency') and called_func.single_iter_latency > 0:
                    logger.info(f"  Using called function's single iteration latency for {op.name}: {called_func.single_iter_latency} cycles")
                    return called_func.single_iter_latency
                
                # For recursive or cyclic function calls, use default value
                logger.info(f"  Called function {function_name} has no latency information. Using default for {op.name}")
        
        # Special handling for memory operations to account for array sizes
        if op_type in ["LOAD", "STORE"]:
            var = None
            if op_type == "LOAD" and op.operands and hasattr(op.operands[0], "data_type"):
                # For LOAD, the array is typically the first operand
                var = op.operands[0]
            elif op_type == "STORE" and op.result and hasattr(op.result, "data_type"):
                # For STORE, the array is typically the result
                var = op.result
            
            # Check if it's an array access and adjust latency based on size
            if var and (var.data_type == "ARRAY" or hasattr(var, "is_scratchpad") and var.is_scratchpad):
                # Calculate the memory size in bytes
                memory_size_bytes = 0
                if hasattr(var, "memory_size") and hasattr(var, "bit_width"):
                    memory_size_bytes = var.memory_size * (var.bit_width // 8)
                
                # Scale latency based on memory size
                if memory_size_bytes > 65536:  # > 64KB
                    logger.info(f"  High latency (3 cycles) for large memory access: {var.name} ({memory_size_bytes} bytes)")
                    return 3  # Highest latency for very large arrays
                elif memory_size_bytes > 16384:  # > 16KB
                    logger.info(f"  Medium-high latency (2 cycles) for large memory access: {var.name} ({memory_size_bytes} bytes)")
                    return 2  # Higher latency for large arrays
                elif memory_size_bytes > 4096:  # > 4KB
                    logger.info(f"  Medium latency (2 cycles) for medium memory access: {var.name} ({memory_size_bytes} bytes)")
                    return 2  # Medium latency for medium arrays
        
        # For non-memory operations or small arrays, use the regular mapping
        resource_type = op_to_resource.get(op_type, "ALU_32bit")
        
        # Get resource model from tech library
        resource = self.tech_library.get_resource(resource_type)
        
        return resource.latency
        
    def _get_ir_from_op(self, op: IROperation) -> Optional[IR]:
        """
        Try to get the IR instance from an operation by traversing up the object hierarchy.
        
        Args:
            op: Operation to find IR for
            
        Returns:
            IR instance or None if not found
        """
        # The challenging part is that operations don't typically have a direct reference to the IR
        # We need to check if we have any attributes that might help us find it
        
        # First check if the scheduler has a reference to the IR
        if hasattr(self, 'ir') and self.ir:
            return self.ir
            
        # Try to get the IR from the current context
        # This will only work if _get_operation_delay is called during the scheduling process
        # and the scheduler has access to the original IR
        current_frame = inspect.currentframe()
        try:
            while current_frame:
                if 'ir' in current_frame.f_locals:
                    return current_frame.f_locals['ir']
                current_frame = current_frame.f_back
        except:
            pass
        finally:
            del current_frame  # Avoid circular references
            
        # If we can't find the IR, return None
        return None

    def _identify_loop_structures(self, func: IRFunction, dfg: nx.DiGraph) -> Dict[int, Dict]:
        """
        Identify loop structures in the function.
        
        Args:
            func: Function to identify loops in
            dfg: Data flow graph
            
        Returns:
            Dictionary of loop structures with header block IDs as keys
        """
        loop_structures = {}
        
        for block in func.blocks:
            if block.loop_header == block:  # This is a loop header
                body_blocks = self._get_loop_body_blocks(block)
                
                # Get all nodes from operations in body blocks
                body_nodes = []
                for body_block in body_blocks + [block]:  # Include header block
                    for instr in body_block.instructions:
                        for op in instr.operations:
                            if op.node_id in dfg:
                                body_nodes.append(op.node_id)
                
                # Get loop iterations (or estimate)
                iterations = self._estimate_loop_iterations(block)
                
                # Handle unrolling factors
                unroll_factor = getattr(block, 'unroll_factor', 1)
                
                # Calculate effective iterations after unrolling
                effective_iterations = iterations
                if unroll_factor > 1:
                    # Use pre-calculated value if available
                    if hasattr(block, 'effective_iterations'):
                        effective_iterations = block.effective_iterations
                    else:
                        effective_iterations = (iterations + unroll_factor - 1) // unroll_factor
                
                # Track parent loop (for nested loop handling)
                parent_loop = None
                for other_block in func.blocks:
                    if other_block.loop_header == other_block and other_block != block:
                        other_body_blocks = self._get_loop_body_blocks(other_block)
                        if block in other_body_blocks or block == other_block:
                            # This other loop contains our current loop
                            parent_loop = other_block.node_id
                
                loop_structures[block.node_id] = {
                    'header_block': block,
                    'body_blocks': body_blocks,
                    'body_nodes': body_nodes,
                    'iterations': iterations,
                    'unroll_factor': unroll_factor,
                    'effective_iterations': effective_iterations,
                    'parent_loop': parent_loop,
                    'contains_loops': False,  # Will be set to True later if this loop contains other loops
                    'calculated_body_latency': None  # Will store the calculated body latency
                }
        
        # Mark loops that contain other loops
        for loop_id, loop_info in loop_structures.items():
            if loop_info['parent_loop'] is not None:
                parent_id = loop_info['parent_loop']
                if parent_id in loop_structures:
                    loop_structures[parent_id]['contains_loops'] = True
        
        return loop_structures
    
    def _get_loop_body_blocks(self, header_block: IRBlock) -> List[IRBlock]:
        """
        Get all blocks in the loop body (excluding the header).
        
        Args:
            header_block: Loop header block
            
        Returns:
            List of blocks in the loop body
        """
        if not header_block.loop_header or header_block.loop_exit is None:
            return []
        
        # The loop body includes all blocks reachable from the header
        # without going through the exit block
        body_blocks = []
        visited = set()
        
        def dfs(block):
            if block in visited or block == header_block.loop_exit:
                return
            visited.add(block)
            if block != header_block:  # Exclude header from body
                body_blocks.append(block)
            for succ in block.successors:
                dfs(succ)
        
        # Start from the header's successors
        for succ in header_block.successors:
            if succ != header_block.loop_exit:
                dfs(succ)
        
        return body_blocks
    
    def _estimate_loop_iterations(self, loop_header: IRBlock) -> int:
        """
        Estimate the number of iterations for a loop.
        
        Args:
            loop_header: Loop header block
            
        Returns:
            Estimated number of iterations
        """
        # First, check if the loop iterations were already calculated
        if hasattr(loop_header, 'loop_iterations'):
            if isinstance(loop_header.loop_iterations, str) and loop_header.loop_iterations == "dynamic":
                # For dynamic loops, use a conservative estimate for scheduling
                logger.info(f"  Using conservative estimate for dynamic loop: 16 iterations")
                return 16
            elif loop_header.loop_iterations > 0:
                logger.info(f"  Using pre-calculated iteration count: {loop_header.loop_iterations}")
                return loop_header.loop_iterations
            
        # If not pre-calculated, try to find iterations from loop conditions
        default_iterations = 10  # Default if we can't determine precisely
        
        # First, check for range-style loops with step sizes
        range_info = self._detect_range_pattern(loop_header)
        if range_info is not None:
            start, end, step = range_info
            if start is not None and end is not None and step is not None and step != 0:
                iterations = (end - start + (step - 1 if step > 0 else 0)) // abs(step)
                logger.info(f"  Detected range-style loop: range({start}, {end}, {step}) = {iterations} iterations")
                return iterations
        
        # Look for comparison operations that might be loop conditions
        for instr in loop_header.instructions:
            for op in instr.operations:
                if op.op_type in [OperationType.LT, OperationType.LTE, OperationType.GT, OperationType.GTE, OperationType.NEQ]:
                    # Different patterns of loop bounds
                    if len(op.operands) == 2:
                        # Pattern 1: Simple constant bounds (i < CONST)
                        if isinstance(op.operands[1], IRConstant):
                            if op.op_type == OperationType.LT:
                                return op.operands[1].value
                            elif op.op_type == OperationType.LTE:
                                return op.operands[1].value + 1
                            elif op.op_type == OperationType.GT:
                                # i > CONST is like a reverse loop
                                if isinstance(op.operands[0], IRVariable) and isinstance(op.operands[1], IRConstant):
                                    # Try to find the initialization value
                                    init_value = self._find_variable_init_value(op.operands[0], loop_header)
                                    if init_value is not None and init_value > op.operands[1].value:
                                        return init_value - op.operands[1].value
                            elif op.op_type == OperationType.GTE:
                                # Similar to GT but inclusive
                                if isinstance(op.operands[0], IRVariable) and isinstance(op.operands[1], IRConstant):
                                    init_value = self._find_variable_init_value(op.operands[0], loop_header)
                                    if init_value is not None and init_value >= op.operands[1].value:
                                        return init_value - op.operands[1].value + 1
                        
                        # Pattern 2: Range bound (i < variable) - look for variable's value
                        elif isinstance(op.operands[1], IRVariable):
                            bound_value = self._find_variable_value(op.operands[1], loop_header)
                            if bound_value is not None:
                                if op.op_type == OperationType.LT:
                                    return bound_value
                                elif op.op_type == OperationType.LTE:
                                    return bound_value + 1
                        
                        # Pattern 3: Range with subtraction/addition (i < var1-var2 or i < var1+var2)
                        elif isinstance(op.operands[1], IROperation):
                            range_op = op.operands[1]
                            if range_op.op_type in [OperationType.ADD, OperationType.SUB, OperationType.MUL]:
                                val1 = self._extract_value(range_op.operands[0], loop_header)
                                val2 = self._extract_value(range_op.operands[1], loop_header)
                                
                                if val1 is not None and val2 is not None:
                                    if range_op.op_type == OperationType.ADD:
                                        result = val1 + val2
                                    elif range_op.op_type == OperationType.SUB:
                                        result = val1 - val2
                                    elif range_op.op_type == OperationType.MUL:
                                        result = val1 * val2
                                    
                                    if op.op_type == OperationType.LT:
                                        return result
                                    elif op.op_type == OperationType.LTE:
                                        return result + 1
    
        logger.info(f"  Using default iteration count: {default_iterations}")
        return default_iterations

    def _detect_range_pattern(self, loop_header: IRBlock) -> Optional[Tuple[int, int, int]]:
        """
        Detect range-style loops like for i in range(start, end, step)
        
        Args:
            loop_header: Loop header block
            
        Returns:
            Tuple of (start, end, step) if detected, None otherwise
        """
        # Look for comparison operations (termination condition)
        loop_var = None
        end_value = None
        compare_op = None
        
        for instr in loop_header.instructions:
            for op in instr.operations:
                if op.op_type in [OperationType.LT, OperationType.LTE, OperationType.GT, OperationType.GTE]:
                    if len(op.operands) == 2 and isinstance(op.operands[0], IRVariable):
                        loop_var = op.operands[0]
                        compare_op = op.op_type
                        if isinstance(op.operands[1], IRConstant):
                            end_value = op.operands[1].value
                        elif isinstance(op.operands[1], IRVariable):
                            end_value = self._find_variable_value(op.operands[1], loop_header)
                        elif isinstance(op.operands[1], IROperation):
                            end_value = self._extract_value(op.operands[1], loop_header)
        
        if loop_var is None or end_value is None:
            return None
        
        # Look for initialization and increment
        start_value = self._find_variable_init_value(loop_var, loop_header)
        if start_value is None:
            start_value = 0  # Default
        
        # Look for step size in update operations
        step_size = self._find_loop_step_size(loop_var, loop_header)
        if step_size is None:
            step_size = 1  # Default step
        
        # For GT/GTE comparison, adjust step direction
        if compare_op in [OperationType.GT, OperationType.GTE] and step_size > 0:
            step_size = -step_size
        
        # For range(start, end, step) the loop runs floor((end-start)/step) times
        return (start_value, end_value, step_size)
    
    def _find_loop_step_size(self, loop_var: IRVariable, loop_header: IRBlock) -> Optional[int]:
        """
        Find the step size for a loop variable.
        
        Args:
            loop_var: Loop variable to find step size for
            loop_header: Loop header block
            
        Returns:
            The step size or None if can't be determined
        """
        # Look for updates to the loop variable within the loop header
        for instr in loop_header.instructions:
            for op in instr.operations:
                # Check for i = i + step or i += step patterns
                if op.op_type == OperationType.ASSIGN and op.result == loop_var:
                    if len(op.operands) > 0 and isinstance(op.operands[0], IROperation):
                        update_op = op.operands[0]
                        
                        # i = i + step
                        if update_op.op_type == OperationType.ADD and len(update_op.operands) == 2:
                            # First operand should be the loop variable
                            if update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRConstant):
                                return update_op.operands[1].value
                            elif update_op.operands[1] == loop_var and isinstance(update_op.operands[0], IRConstant):
                                return update_op.operands[0].value
                            elif update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRVariable):
                                return self._find_variable_value(update_op.operands[1], loop_header)
                            elif update_op.operands[1] == loop_var and isinstance(update_op.operands[0], IRVariable):
                                return self._find_variable_value(update_op.operands[0], loop_header)
                            
                        # i = i - step (negative step)
                        elif update_op.op_type == OperationType.SUB and len(update_op.operands) == 2:
                            # First operand should be the loop variable
                            if update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRConstant):
                                return -update_op.operands[1].value
                            elif update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRVariable):
                                step_val = self._find_variable_value(update_op.operands[1], loop_header)
                                if step_val is not None:
                                    return -step_val
        
        # Sometimes the update is in a separate back-edge block
        # Look for simple i++ or i+=step operations in successors
        for succ in loop_header.successors:
            if succ == loop_header or (hasattr(loop_header, 'loop_exit') and succ == loop_header.loop_exit):
                continue  # Skip loop header itself and exit block
            
            for instr in succ.instructions:
                for op in instr.operations:
                    if op.op_type == OperationType.ASSIGN and op.result == loop_var:
                        if len(op.operands) > 0:
                            if isinstance(op.operands[0], IROperation):
                                update_op = op.operands[0]
                                
                                # i = i + step
                                if update_op.op_type == OperationType.ADD and len(update_op.operands) == 2:
                                    if update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRConstant):
                                        return update_op.operands[1].value
                                    elif update_op.operands[1] == loop_var and isinstance(update_op.operands[0], IRConstant):
                                        return update_op.operands[0].value
                                    elif update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRVariable):
                                        return self._find_variable_value(update_op.operands[1], loop_header)
                                    elif update_op.operands[1] == loop_var and isinstance(update_op.operands[0], IRVariable):
                                        return self._find_variable_value(update_op.operands[0], loop_header)
                                    
                                # i = i - step (negative step)
                                elif update_op.op_type == OperationType.SUB and len(update_op.operands) == 2:
                                    if update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRConstant):
                                        return -update_op.operands[1].value
                                    elif update_op.operands[0] == loop_var and isinstance(update_op.operands[1], IRVariable):
                                        step_val = self._find_variable_value(update_op.operands[1], loop_header)
                                        if step_val is not None:
                                            return -step_val
        
        # Default step size is 1
        return 1

    def _extract_value(self, operand, loop_header: IRBlock) -> Optional[int]:
        """
        Extract a numeric value from an operand, which could be a constant, variable, or expression.
        
        Args:
            operand: The operand to extract value from
            loop_header: Loop header block for context
            
        Returns:
            The extracted value or None if can't be determined
        """
        if isinstance(operand, IRConstant):
            return operand.value
        elif isinstance(operand, IRVariable):
            return self._find_variable_value(operand, loop_header)
        elif isinstance(operand, IROperation):
            if operand.op_type in [OperationType.ADD, OperationType.SUB, OperationType.MUL]:
                val1 = self._extract_value(operand.operands[0], loop_header)
                val2 = self._extract_value(operand.operands[1], loop_header)
                
                if val1 is not None and val2 is not None:
                    if operand.op_type == OperationType.ADD:
                        return val1 + val2
                    elif operand.op_type == OperationType.SUB:
                        return val1 - val2
                    elif operand.op_type == OperationType.MUL:
                        return val1 * val2
        
        return None

    def _find_variable_init_value(self, variable: IRVariable, loop_header: IRBlock) -> Optional[int]:
        """
        Find the initialization value of a loop variable.
        
        Args:
            variable: Loop variable to find initialization for
            loop_header: Loop header block
            
        Returns:
            The initialization value or None if can't be determined
        """
        # Look for initializations in predecessors of the loop header
        for pred in loop_header.predecessors:
            if pred == loop_header:  # Skip self-loops
                continue
            
            # Look for assignments to the variable
            for instr in pred.instructions:
                for op in instr.operations:
                    if op.op_type == OperationType.ASSIGN and op.result == variable:
                        if len(op.operands) > 0 and isinstance(op.operands[0], IRConstant):
                            return op.operands[0].value
        
        # Default initialization often 0
        return 0

    def _find_variable_value(self, variable: IRVariable, context_block: IRBlock) -> Optional[int]:
        """
        Find the value of a variable in the context of a block.
        
        Args:
            variable: Variable to find value for
            context_block: Block providing context
            
        Returns:
            The variable's value or None if can't be determined
        """
        # First look in the current block for assignments
        for instr in context_block.instructions:
            for op in instr.operations:
                if op.op_type == OperationType.ASSIGN and op.result == variable:
                    if len(op.operands) > 0:
                        if isinstance(op.operands[0], IRConstant):
                            return op.operands[0].value
                        elif isinstance(op.operands[0], IROperation):
                            return self._extract_value(op.operands[0], context_block)
        
        # Then look in predecessors
        for pred in context_block.predecessors:
            if pred == context_block:  # Skip self-loops
                continue
            
            # Recursively search in predecessor blocks
            val = self._find_variable_value(variable, pred)
            if val is not None:
                return val
        
        return None

    def _calculate_pipelined_latency(self, loop_info: Dict, iterations: int, 
                                   body_latency: int, pipeline_depth: int = 1) -> int:
        """
        Calculate latency for a pipelined loop.
        
        Args:
            loop_info: Loop structure information
            iterations: Number of loop iterations
            body_latency: Latency of the loop body in cycles
            pipeline_depth: Pipeline depth (cycles between iterations)
            
        Returns:
            Latency of the pipelined loop in cycles
        """
        if pipeline_depth <= 0:
            pipeline_depth = 1
            
        # With perfect pipelining (depth=1), once pipeline is filled,
        # each new iteration takes 1 cycle
        if iterations <= pipeline_depth:
            # Not enough iterations to fill pipeline
            return body_latency * iterations
            
        # Calculate latency with pipeline
        # First 'pipeline_depth' iterations fill the pipeline
        # Remaining iterations each take 'pipeline_depth' cycles
        fill_latency = body_latency * pipeline_depth
        steady_latency = pipeline_depth * (iterations - pipeline_depth)
        
        total_latency = fill_latency + steady_latency
        
        logger.info(f"  Pipeline (depth {pipeline_depth}) reduces latency from {body_latency * iterations} to {total_latency} cycles")
        return total_latency

    def _pre_allocation_analysis(self, func: IRFunction) -> None:
        """
        Perform pre-allocation analysis to identify memory requirements.
        This helps with more accurate memory operation latency estimates.
        
        Args:
            func: Function to analyze
        """
        logger.info("Performing pre-allocation memory analysis...")
        large_arrays = []
        medium_arrays = []
        small_arrays = []
        total_memory_size = 0
        
        # Analyze all variables to identify arrays and their sizes
        for var_name, var in func.local_vars.items():
            if var.data_type == "ARRAY" or (hasattr(var, "is_scratchpad") and var.is_scratchpad):
                if hasattr(var, "memory_size") and var.memory_size > 0:
                    # Calculate total memory size in bytes
                    memory_size_bytes = var.memory_size * (var.bit_width // 8)
                    total_memory_size += memory_size_bytes
                    
                    # Categorize arrays by size
                    if memory_size_bytes > 65536:  # > 64KB
                        large_arrays.append((var_name, memory_size_bytes))
                    elif memory_size_bytes > 16384:  # > 16KB
                        medium_arrays.append((var_name, memory_size_bytes))
                    elif memory_size_bytes > 4096:  # > 4KB
                        small_arrays.append((var_name, memory_size_bytes))
        
        # Print memory analysis report
        if large_arrays or medium_arrays or small_arrays:
            logger.info(f"Memory analysis for function {func.name}:")
            logger.info(f"  Total memory requirement: {total_memory_size/1024:.2f} KB")
            
            if large_arrays:
                logger.info(f"  Large arrays ({len(large_arrays)}):")
                for name, size in large_arrays:
                    logger.info(f"    {name}: {size/1024:.2f} KB (high latency: 3 cycles)")
            
            if medium_arrays:
                logger.info(f"  Medium arrays ({len(medium_arrays)}):")
                for name, size in medium_arrays:
                    logger.info(f"    {name}: {size/1024:.2f} KB (medium latency: 2 cycles)")
            
            if small_arrays:
                logger.info(f"  Small arrays ({len(small_arrays)}):")
                for name, size in small_arrays:
                    logger.info(f"    {name}: {size/1024:.2f} KB (standard latency: 1 cycle)")
            
            # Store memory analysis results in the function for later use
            func.memory_analysis = {
                'total_size': total_memory_size,
                'large_arrays': large_arrays,
                'medium_arrays': medium_arrays,
                'small_arrays': small_arrays
            }
        else:
            logger.info(f"No significant array memory usage detected in function {func.name}")
            func.memory_analysis = {'total_size': 0}


class ASAPScheduler(Scheduler):
    """As Soon As Possible (ASAP) scheduler."""
    
    def schedule(self, ir: IR) -> IR:
        """
        Schedule operations using As Soon As Possible (ASAP) algorithm.
        
        Args:
            ir: IR to schedule
            
        Returns:
            Scheduled IR
        """
        # Store reference to IR for function call latency calculation
        self.ir = ir
        
        # First, build the function call graph to determine scheduling order
        # (we need to schedule callee functions before caller functions)
        call_graph = self._build_function_call_graph(ir)
        
        # Get the ordering of functions to schedule
        # Functions with no callees should be scheduled first
        schedule_order = self._get_function_schedule_order(call_graph)
        logger.info(f"Scheduling functions in order: {schedule_order}")
        
        # Process each function in the determined order
        max_critical_path = 0
        
        for func_name in schedule_order:
            func = ir.functions[func_name]
            # Perform pre-allocation memory analysis
            self._pre_allocation_analysis(func)
            # Build DFG
            dfg = self._build_dfg(func)
            
            # Identify loop structures
            loop_structures = self._identify_loop_structures(func, dfg)
            logger.info(f"Found {len(loop_structures)} loop structures")
            
            # Calculate priorities (critical path lengths)
            priorities = self._calculate_priorities(dfg)
            
            # Store the calculated max frequency for this function
            if hasattr(self, '_last_calculated_frequency'):
                func._calculated_max_frequency = self._last_calculated_frequency
            
            # Get maximum priority to determine critical path
            if priorities:
                func_critical_path = max(priorities.values())
                max_critical_path = max(max_critical_path, func_critical_path)
            
            # Initialize schedule
            schedule = {}
            
            # Get nodes with no predecessors (inputs/constants)
            ready = [n for n in dfg.nodes if dfg.in_degree(n) == 0]
            
            # Current control step
            current_step = 0
            
            # Process until all nodes are scheduled
            while ready:
                # Sort ready nodes by priority
                ready.sort(key=lambda n: priorities.get(n, 0), reverse=True)
                
                # Schedule highest-priority ready node
                node = ready.pop(0)
                schedule[node] = current_step
                
                # Check if new nodes are ready
                for succ in dfg.successors(node):
                    # If all predecessors of succ are scheduled, succ is ready
                    if all(pred in schedule for pred in dfg.predecessors(succ)):
                        ready.append(succ)
                
                # Move to next time step
                current_step += 1
            
            # Apply schedule to operations
            max_control_step = 0
            single_iter_latency = 0
            
            # Track function call operations for incorporating their latencies
            call_operations = []
            
            for block in func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.node_id in schedule:
                            # Update operation's control step in IR
                            control_step = schedule[op.node_id]
                            op.control_step = control_step
                            logger.info(f"  Operation {op.name} (type: {op.op_type.name}) scheduled at step {control_step}")
                            
                            # Calculate operation delay based on its type
                            op_delay = self._get_operation_delay(op)
                            
                            # Store delay for later latency calculation
                            op._delay = op_delay
                            
                            # Track function call operations
                            if op.op_type == OperationType.CALL and hasattr(op, 'function_name'):
                                call_operations.append(op)
                            
                            # Calculate latest operation completion time
                            op_end_time = control_step + op_delay
                            max_control_step = max(max_control_step, control_step)
                            single_iter_latency = max(single_iter_latency, op_end_time)
            
            # Calculate total latency considering loop iterations
            total_latency = self._calculate_total_latency(func, dfg, loop_structures, single_iter_latency)
            
            # Update total latency if this function makes function calls
            # For a function with function calls, its latency should include the latency of the called functions
            if len(call_operations) > 0:
                # If this is the main function or any function that calls others but doesn't have loops,
                # ensure its latency includes the called function latency
                if single_iter_latency == 1 or total_latency == single_iter_latency:
                    max_call_latency = 0
                    for call_op in call_operations:
                        if hasattr(call_op, 'function_name'):
                            callee_name = call_op.function_name
                            if callee_name in ir.functions:
                                callee = ir.functions[callee_name]
                                if hasattr(callee, 'total_latency') and callee.total_latency > 0:
                                    max_call_latency = max(max_call_latency, callee.total_latency)
                
                    # Update total latency to include called function latency
                    if max_call_latency > 0:
                        total_latency = max(total_latency, max_call_latency + 1)  # +1 for the call operation itself
                        logger.info(f"  Updated {func_name} total latency to {total_latency} to account for function calls")
            
            # Store both latencies in the function
            logger.info(f"Function {func_name} scheduled with single iteration latency: {single_iter_latency} cycles")
            logger.info(f"Function {func_name} scheduled with total latency (including loops): {total_latency} cycles")
            func.max_control_step = max_control_step
            func.single_iter_latency = single_iter_latency
            func.total_latency = total_latency
            
            # Also store the clock frequency from the IR
            func.clock_frequency_mhz = ir.target_frequency_mhz
            
            logger.info(f"Function {func_name} scheduling complete")
        
        # Set target frequency for the entire IR based on critical path
        if max_critical_path > 0:
            # Find the maximum achievable frequency from all functions
            max_achievable_freq = 0.0
            
            for func_name in schedule_order:
                func = ir.functions[func_name]
                if hasattr(func, '_calculated_max_frequency'):
                    max_achievable_freq = max(max_achievable_freq, func._calculated_max_frequency)
            
            # If we found a calculated frequency, use it; otherwise use a conservative default
            if max_achievable_freq > 0:
                target_freq = max_achievable_freq
            else:
                target_freq = 400.0  # Conservative default for unknown critical path
            
            ir.target_frequency_mhz = target_freq
            logger.info(f"Set IR target frequency to {target_freq:.2f} MHz based on technology-aware critical path analysis")
        
        return ir
        
    def _calculate_total_latency(self, func: IRFunction, dfg: nx.DiGraph, 
                              loop_structures: Dict[int, Dict], base_latency: int) -> int:
        """
        Calculate total latency including loop iterations.
        
        Args:
            func: Function to calculate latency for
            dfg: Data flow graph
            loop_structures: Loop structure information
            base_latency: Base latency without considering loops
            
        Returns:
            Total latency including loop iterations
        """
        # Start with base latency
        total_latency = base_latency
        
        if not loop_structures:
            return total_latency
        
        # First, build the loop hierarchy (nested loops)
        # We'll process loops from innermost to outermost
        loop_hierarchy = {}
        inner_loops = {}
        
        for loop_id, loop_info in loop_structures.items():
            parent_loop = loop_info.get('parent_loop')
            if parent_loop not in loop_hierarchy:
                loop_hierarchy[parent_loop] = []
            loop_hierarchy[parent_loop].append(loop_id)
            
            # Track which loops are inner loops of others
            if parent_loop is not None:
                if parent_loop not in inner_loops:
                    inner_loops[parent_loop] = []
                inner_loops[parent_loop].append(loop_id)
        
        # Process loops from innermost to outermost
        processed_loops = set()
        loop_latencies = {}
        
        # Helper function to process a loop and its inner loops
        def process_loop(loop_id):
            # Skip if already processed
            if loop_id in processed_loops:
                return loop_latencies.get(loop_id, 0)
            
            # Get loop info
            loop_info = loop_structures[loop_id]
            header_block = loop_info['header_block']
            body_nodes = loop_info['body_nodes']
            iterations = loop_info['iterations']
            unroll_factor = loop_info['unroll_factor']
            effective_iterations = loop_info['effective_iterations']
            
            # First, process any inner loops
            inner_loop_latencies = 0
            if loop_id in inner_loops:
                for inner_id in inner_loops[loop_id]:
                    inner_latency = process_loop(inner_id)
                    inner_loop_latencies += inner_latency
            
            # Calculate latency of the loop body excluding inner loops
            # For this, we need to identify nodes that are in this loop but not in any inner loop
            loop_only_nodes = set(body_nodes)
            if loop_id in inner_loops:
                for inner_id in inner_loops[loop_id]:
                    inner_nodes = set(loop_structures[inner_id]['body_nodes'])
                    loop_only_nodes -= inner_nodes
            
            # Calculate the base body latency (excluding inner loops)
            base_body_latency = self._calculate_loop_body_latency(dfg, list(loop_only_nodes))
            
            # Total body latency is base body latency plus the latency from inner loops
            total_body_latency = base_body_latency + inner_loop_latencies
            
            # Store the calculated body latency
            loop_info['calculated_body_latency'] = total_body_latency
            
            # Check if loop is pipelined
            pipeline_enabled = getattr(func, 'enable_pipeline', False)
            pipeline_depth = getattr(func, 'pipeline_depth', 1)
            
            # For unrolled loops, adjust the body latency and iteration count
            if unroll_factor > 1:
                # Resource usage increases proportionally to unroll factor,
                # but latency decreases by the same factor
                adjusted_body_latency = total_body_latency * unroll_factor
                iterations = effective_iterations
                
                # Log information about the unrolled loop
                logger.info(f"Loop {header_block.name} unrolled {unroll_factor}x: "
                      f"body latency={adjusted_body_latency}, iterations={iterations}")
            else:
                adjusted_body_latency = total_body_latency
            
            # Calculate the loop latency
            if pipeline_enabled and pipeline_depth > 1:
                # For pipelined loops, use special calculation
                loop_latency = self._calculate_pipelined_latency(
                    loop_info, iterations, adjusted_body_latency, pipeline_depth)
            else:
                # For sequential loops, multiply by iterations
                loop_latency = adjusted_body_latency * iterations
            
            # Store the loop latency
            loop_latencies[loop_id] = loop_latency
            processed_loops.add(loop_id)
            
            logger.info(f"  Loop {header_block.name} with {iterations} iterations: "
                  f"body latency={adjusted_body_latency}, total loop latency={loop_latency}")
            
            return loop_latency
        
        # Process all top-level loops (those without a parent)
        top_level_latency = 0
        if None in loop_hierarchy:
            for loop_id in loop_hierarchy[None]:
                top_level_latency += process_loop(loop_id)
        
        # Add the top-level loop latency to the base latency
        total_latency += top_level_latency
        
        # Record loop statistics in function
        for loop_id in processed_loops:
            loop_info = loop_structures[loop_id]
            func.loop_count += 1
            func.loop_iterations += loop_info['iterations']
        
        # Set total latency in function
        func.total_latency = total_latency
        
        return total_latency
    
    def _calculate_loop_body_latency(self, dfg: nx.DiGraph, body_nodes: List[int]) -> int:
        """
        Calculate latency of a loop body.
        
        Args:
            dfg: Data flow graph
            body_nodes: List of operation node IDs in the loop body
            
        Returns:
            Latency of the loop body
        """
        # Find the maximum control step among operations in the body
        max_step = 0
        for node_id in body_nodes:
            if node_id in dfg.nodes:
                op = dfg.nodes[node_id].get('op')
                if op and hasattr(op, 'control_step'):
                    max_step = max(max_step, op.control_step)
        
        # For unrolled operations, the latency doesn't increase linearly with the number of operations
        # because they're executed in parallel. Instead, the resource usage increases.
        # This is handled in the parent method (_calculate_total_latency).
        
        # Add 1 since control steps are 0-indexed
        return max_step + 1

    def _calculate_priorities(self, dfg: nx.DiGraph) -> Dict[int, int]:
        """
        Calculate priorities (critical path lengths) for nodes in the DFG.
        
        Args:
            dfg: Data flow graph
            
        Returns:
            Dictionary of node IDs to priorities
        """
        priorities = {}
        critical_path_ops = []  # Track operations on the critical path
        
        # Calculate priorities in reverse topological order
        for node in reversed(list(nx.topological_sort(dfg))):
            if dfg.out_degree(node) == 0:  # Sink node
                priorities[node] = self._get_operation_delay(dfg.nodes[node]["op"])
            else:
                max_succ_priority = 0
                critical_successor = None
                for succ in dfg.successors(node):
                    if priorities[succ] > max_succ_priority:
                        max_succ_priority = priorities[succ]
                        critical_successor = succ
                
                priorities[node] = self._get_operation_delay(dfg.nodes[node]["op"]) + max_succ_priority
                
                # If this is potentially part of the critical path, track it for logging
                if critical_successor is not None:
                    dfg.nodes[node]["critical_successor"] = critical_successor
        
        # Find node with maximum priority (start of critical path)
        if priorities:
            max_priority = max(priorities.values())
            critical_start_nodes = [n for n, p in priorities.items() if p == max_priority and dfg.in_degree(n) == 0]
            
            # If we found a starting point for critical path, trace it
            if critical_start_nodes:
                current_node = critical_start_nodes[0]  # Use the first one if multiple exist
                
                # Trace the critical path by following critical successors
                while current_node is not None:
                    op = dfg.nodes[current_node].get("op")
                    if op:
                        critical_path_ops.append({
                            "node_id": current_node,
                            "op_type": op.op_type.name if hasattr(op, "op_type") else "Unknown",
                            "delay": self._get_operation_delay(op),
                            "cumulative_delay": priorities[current_node]
                        })
                    
                    # Move to the next node in critical path
                    current_node = dfg.nodes[current_node].get("critical_successor")
            
            # Calculate the achievable frequency based on the critical path resources
            if max_priority > 0:
                # Find the slowest resource on the critical path
                min_frequency_mhz = float('inf')
                slowest_op_type = None
                
                for op_info in critical_path_ops:
                    # Map operation type to resource type
                    op_to_resource = {
                        "ADD": "Adder_32bit",
                        "SUB": "Subtractor_32bit",
                        "MUL": "Multiplier_32bit",
                        "DIV": "Divider_32bit",
                        "MOD": "ALU_32bit",
                        "POW": "ALU_32bit",
                        "LSHIFT": "Shifter_32bit",
                        "RSHIFT": "Shifter_32bit",
                        "BIT_OR": "BitOp_32bit",
                        "BIT_AND": "BitOp_32bit",
                        "BIT_XOR": "BitOp_32bit",
                        "LOGIC_OR": "BitOp_32bit",
                        "LOGIC_AND": "BitOp_32bit",
                        "EQ": "Comparator_32bit",
                        "NEQ": "Comparator_32bit",
                        "LT": "RelationalOp_32bit",
                        "LTE": "RelationalOp_32bit",
                        "GT": "RelationalOp_32bit",
                        "GTE": "RelationalOp_32bit",
                        "NEG": "Subtractor_32bit",
                        "NOT": "BitOp_32bit",
                        "BIT_NOT": "BitOp_32bit",
                        "ASSIGN": "Register_32bit",
                        "RETURN": "Register_32bit",
                        "STORE": "Memory_1KB",
                        "LOAD": "Memory_1KB",
                        "CALL": "ALU_32bit"
                    }
                    
                    resource_type = op_to_resource.get(op_info["op_type"], "ALU_32bit")
                    try:
                        resource = self.tech_library.get_resource(resource_type)
                        if resource.frequency < min_frequency_mhz:
                            min_frequency_mhz = resource.frequency
                            slowest_op_type = op_info["op_type"]
                    except ValueError:
                        # If resource not found, use a default frequency
                        default_freq = 400.0  # MHz
                        if default_freq < min_frequency_mhz:
                            min_frequency_mhz = default_freq
                            slowest_op_type = op_info["op_type"]
                
                # The maximum achievable frequency is limited by the slowest resource
                if min_frequency_mhz == float('inf'):
                    max_frequency_mhz = 1000.0  # Default fallback
                else:
                    max_frequency_mhz = min_frequency_mhz
                
                # Store the calculated frequency for later use
                self._last_calculated_frequency = max_frequency_mhz
                
                # Log critical path information
                logger.info(f"Critical Path Analysis:")
                logger.info(f"  Maximum path delay: {max_priority} cycles")
                logger.info(f"  Slowest resource: {slowest_op_type} limiting frequency to {max_frequency_mhz:.2f} MHz")
                logger.info(f"  Calculated target frequency: {max_frequency_mhz:.2f} MHz")
                logger.info(f"  Critical path operations:")
                
                for i, op_info in enumerate(critical_path_ops):
                    op_resource_type = op_to_resource.get(op_info["op_type"], "ALU_32bit")
                    try:
                        op_resource = self.tech_library.get_resource(op_resource_type)
                        op_freq = op_resource.frequency
                    except ValueError:
                        op_freq = 400.0  # Default
                    
                    logger.info(f"    {i+1}. {op_info['op_type']} (Node {op_info['node_id']}):")
                    logger.info(f"       Delay: {op_info['delay']} cycles")
                    logger.info(f"       Max frequency: {op_freq:.2f} MHz")
                    logger.info(f"       Cumulative: {op_info['cumulative_delay']} cycles")
        
        return priorities

    def _build_function_call_graph(self, ir: IR) -> Dict[str, List[str]]:
        """
        Build a function call graph to determine dependencies.
        
        Args:
            ir: The IR to analyze
            
        Returns:
            Dictionary mapping function names to lists of called function names
        """
        call_graph = {}
        
        # Initialize the call graph with empty lists for all functions
        for func_name in ir.functions:
            call_graph[func_name] = []
            
        # Find all function calls
        for caller_name, caller_func in ir.functions.items():
            # Look for CALL operations
            for block in caller_func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.op_type == OperationType.CALL and hasattr(op, 'function_name'):
                            callee_name = op.function_name
                            # Ensure the called function exists in the IR
                            if callee_name in ir.functions:
                                # Add a dependency from caller to callee
                                if callee_name not in call_graph[caller_name]:
                                    call_graph[caller_name].append(callee_name)
        
        return call_graph
        
    def _get_function_schedule_order(self, call_graph: Dict[str, List[str]]) -> List[str]:
        """
        Determine the order in which functions should be scheduled.
        
        Args:
            call_graph: Dictionary mapping function names to called function names
            
        Returns:
            List of function names in the order they should be scheduled
        """
        # Create a directed graph representing call relationships
        graph = nx.DiGraph()
        
        # Add all nodes and edges
        for func_name, callees in call_graph.items():
            graph.add_node(func_name)
            for callee in callees:
                graph.add_edge(func_name, callee)
        
        # Try to get a topological sort (functions with no callees first)
        try:
            # Reverse gives us callee functions first, which is what we want
            # (functions that don't call other functions should be scheduled first)
            schedule_order = list(reversed(list(nx.topological_sort(graph))))
            return schedule_order
        except nx.NetworkXUnfeasible:
            # If there are cycles (recursive calls), fall back to a simple ordering
            logger.warning("Warning: Detected recursive function calls. Using a heuristic scheduling order.")
            
            # Sort functions by the number of functions they call (ascending)
            # This is a simple heuristic that often works well
            return sorted(call_graph.keys(), key=lambda f: len(call_graph[f]))


class ALAPScheduler(Scheduler):
    """As Late As Possible (ALAP) scheduler."""
    
    def schedule(self, ir: IR, latency_constraint: Optional[int] = None) -> IR:
        """
        Schedule operations using ALAP algorithm.
        
        Args:
            ir: IR to schedule
            latency_constraint: Maximum latency in clock cycles
            
        Returns:
            Scheduled IR
        """
        # Store reference to IR for function call latency calculation
        self.ir = ir
        
        # First, build the function call graph to determine scheduling order
        # (we need to schedule callee functions before caller functions)
        call_graph = self._build_function_call_graph(ir)
        
        # Get the ordering of functions to schedule
        # Functions with no callees should be scheduled first
        schedule_order = self._get_function_schedule_order(call_graph)
        logger.info(f"Scheduling functions in order: {schedule_order}")
        
        # Process each function in the determined order
        for func_name in schedule_order:
            func = ir.functions[func_name]
            # Perform pre-allocation memory analysis
            self._pre_allocation_analysis(func)
            
            # Build DFG
            dfg = self._build_dfg(func)
            
            # Identify loop structures
            loop_structures = self._identify_loop_structures(func, dfg)
            logger.info(f"Found {len(loop_structures)} loop structures")
            
            # Determine total latency if not provided
            if latency_constraint is None:
                asap = ASAPScheduler(self.tech_library)
                asap.schedule(ir)
                
                # Find the max control step
                max_step = 0
                for block in func.blocks:
                    for instr in block.instructions:
                        for op in instr.operations:
                            max_step = max(max_step, op.control_step + self._get_operation_delay(op))
                
                latency_constraint = max_step
            
            # Initialize schedule
            schedule = {}
            
            # Get nodes with no successors (outputs)
            sinks = [n for n in dfg.nodes if dfg.out_degree(n) == 0]
            for sink in sinks:
                schedule[sink] = latency_constraint - self._get_operation_delay(dfg.nodes[sink]["op"])
            
            # Schedule remaining nodes in reverse topological order
            for node in reversed(list(nx.topological_sort(dfg))):
                if node in schedule:
                    continue
                
                # Find earliest successor start time
                min_succ_time = latency_constraint
                for succ in dfg.successors(node):
                    min_succ_time = min(min_succ_time, schedule[succ])
                
                op_delay = self._get_operation_delay(dfg.nodes[node]["op"])
                schedule[node] = min_succ_time - op_delay
            
            # Apply schedule to operations
            single_iter_latency = 0
            
            # Track function call operations for incorporating their latencies
            call_operations = []
            
            for block in func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.node_id in schedule:
                            # Update operation's control step in IR
                            control_step = schedule[op.node_id]
                            op.control_step = control_step
                            
                            # Calculate and store operation delay
                            op_delay = self._get_operation_delay(op)
                            op._delay = op_delay
                            
                            # Track function call operations
                            if op.op_type == OperationType.CALL and hasattr(op, 'function_name'):
                                call_operations.append(op)
                            
                            # Track single iteration latency
                            op_end_time = control_step + op_delay
                            single_iter_latency = max(single_iter_latency, op_end_time)
            
            # Calculate total latency considering loop iterations
            total_latency = self._calculate_total_latency(func, dfg, loop_structures, single_iter_latency)
            
            # Update total latency if this function makes function calls
            # For a function with function calls, its latency should include the latency of the called functions
            if len(call_operations) > 0:
                # If this is the main function or any function that calls others but doesn't have loops,
                # ensure its latency includes the called function latency
                if single_iter_latency == 1 or total_latency == single_iter_latency:
                    max_call_latency = 0
                    for call_op in call_operations:
                        if hasattr(call_op, 'function_name'):
                            callee_name = call_op.function_name
                            if callee_name in ir.functions:
                                callee = ir.functions[callee_name]
                                if hasattr(callee, 'total_latency') and callee.total_latency > 0:
                                    max_call_latency = max(max_call_latency, callee.total_latency)
                
                    # Update total latency to include called function latency
                    if max_call_latency > 0:
                        total_latency = max(total_latency, max_call_latency + 1)  # +1 for the call operation itself
                        logger.info(f"  Updated {func_name} total latency to {total_latency} to account for function calls")
            
            # Store both latencies in the function
            logger.info(f"Function {func_name} scheduled with single iteration latency: {single_iter_latency} cycles")
            logger.info(f"Function {func_name} scheduled with total latency (including loops): {total_latency} cycles")
            
            func.single_iter_latency = single_iter_latency
            func.total_latency = total_latency
        
        return ir
        
    def _calculate_total_latency(self, func: IRFunction, dfg: nx.DiGraph, 
                              loop_structures: Dict[int, Dict], base_latency: int) -> int:
        """
        Calculate total latency considering loop iterations.
        
        Args:
            func: Function being scheduled
            dfg: Data flow graph
            loop_structures: Dictionary of loop structures
            base_latency: Base latency without loop iteration multiplication
            
        Returns:
            Total latency in cycles
        """
        if not loop_structures:
            return base_latency
            
        # Start with base latency
        total_latency = base_latency
        
        # First, build the loop hierarchy (nested loops)
        # We'll process loops from innermost to outermost
        loop_hierarchy = {}
        inner_loops = {}
        
        for loop_id, loop_info in loop_structures.items():
            parent_loop = loop_info.get('parent_loop')
            if parent_loop not in loop_hierarchy:
                loop_hierarchy[parent_loop] = []
            loop_hierarchy[parent_loop].append(loop_id)
            
            # Track which loops are inner loops of others
            if parent_loop is not None:
                if parent_loop not in inner_loops:
                    inner_loops[parent_loop] = []
                inner_loops[parent_loop].append(loop_id)
        
        # Process loops from innermost to outermost
        processed_loops = set()
        loop_latencies = {}
        
        # Helper function to process a loop and its inner loops
        def process_loop(loop_id):
            # Skip if already processed
            if loop_id in processed_loops:
                return loop_latencies.get(loop_id, 0)
            
            # Get loop info
            loop_info = loop_structures[loop_id]
            iterations = loop_info['iterations']
            if iterations <= 1:
                processed_loops.add(loop_id)
                return 0  # No need to adjust for loops with 1 or fewer iterations
            
            # First, process any inner loops
            inner_loop_latencies = 0
            if loop_id in inner_loops:
                for inner_id in inner_loops[loop_id]:
                    inner_latency = process_loop(inner_id)
                    inner_loop_latencies += inner_latency
            
            # Calculate latency of the loop body excluding inner loops
            # For this, we need to identify nodes that are in this loop but not in any inner loop
            loop_only_nodes = set(loop_info['body_nodes'])
            if loop_id in inner_loops:
                for inner_id in inner_loops[loop_id]:
                    inner_nodes = set(loop_structures[inner_id]['body_nodes'])
                    loop_only_nodes -= inner_nodes
            
            # Calculate the base body latency (excluding inner loops)
            base_body_latency = self._calculate_loop_body_latency(dfg, list(loop_only_nodes))
            
            # Total body latency is base body latency plus the latency from inner loops
            total_body_latency = base_body_latency + inner_loop_latencies
            
            # Add the repeated execution of the loop body
            # Subtract 1 from iterations since one iteration is already in the base latency
            additional_latency = total_body_latency * (iterations - 1)
            
            # Store the loop latency
            loop_latencies[loop_id] = additional_latency
            processed_loops.add(loop_id)
            
            logger.info(f"  Loop with {iterations} iterations adds {additional_latency} cycles "
                  f"(body latency: {total_body_latency}, base: {base_body_latency}, inner loops: {inner_loop_latencies})")
            
            return additional_latency
        
        # Process all top-level loops (those without a parent)
        top_level_latency = 0
        if None in loop_hierarchy:
            for loop_id in loop_hierarchy[None]:
                top_level_latency += process_loop(loop_id)
        
        # Add the top-level loop latency to the base latency
        total_latency += top_level_latency
        
        return total_latency
    
    def _calculate_loop_body_latency(self, dfg: nx.DiGraph, body_nodes: List[int]) -> int:
        """
        Calculate the latency of a loop body.
        
        Args:
            dfg: Data flow graph
            body_nodes: List of node IDs in the loop body
            
        Returns:
            Latency of the loop body in cycles
        """
        if not body_nodes:
            return 0
            
        # Find max end time of any operation in the body
        max_latency = 0
        for node_id in body_nodes:
            node = dfg.nodes[node_id]
            op = node['op']
            end_time = op.control_step + self._get_operation_delay(op)
            max_latency = max(max_latency, end_time)
            
        return max_latency

    def _build_function_call_graph(self, ir: IR) -> Dict[str, List[str]]:
        """
        Build a function call graph to determine dependencies.
        
        Args:
            ir: The IR to analyze
            
        Returns:
            Dictionary mapping function names to lists of called function names
        """
        call_graph = {}
        
        # Initialize the call graph with empty lists for all functions
        for func_name in ir.functions:
            call_graph[func_name] = []
            
        # Find all function calls
        for caller_name, caller_func in ir.functions.items():
            # Look for CALL operations
            for block in caller_func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.op_type == OperationType.CALL and hasattr(op, 'function_name'):
                            callee_name = op.function_name
                            # Ensure the called function exists in the IR
                            if callee_name in ir.functions:
                                # Add a dependency from caller to callee
                                if callee_name not in call_graph[caller_name]:
                                    call_graph[caller_name].append(callee_name)
        
        return call_graph
        
    def _get_function_schedule_order(self, call_graph: Dict[str, List[str]]) -> List[str]:
        """
        Determine the order in which functions should be scheduled.
        
        Args:
            call_graph: Dictionary mapping function names to called function names
            
        Returns:
            List of function names in the order they should be scheduled
        """
        # Create a directed graph representing call relationships
        graph = nx.DiGraph()
        
        # Add all nodes and edges
        for func_name, callees in call_graph.items():
            graph.add_node(func_name)
            for callee in callees:
                graph.add_edge(func_name, callee)
        
        # Try to get a topological sort (functions with no callees first)
        try:
            # Reverse gives us callee functions first, which is what we want
            # (functions that don't call other functions should be scheduled first)
            schedule_order = list(reversed(list(nx.topological_sort(graph))))
            return schedule_order
        except nx.NetworkXUnfeasible:
            # If there are cycles (recursive calls), fall back to a simple ordering
            logger.warning("Warning: Detected recursive function calls. Using a heuristic scheduling order.")
            
            # Sort functions by the number of functions they call (ascending)
            # This is a simple heuristic that often works well
            return sorted(call_graph.keys(), key=lambda f: len(call_graph[f]))


class ListScheduler(Scheduler):
    """List scheduling algorithm with resource constraints."""

    def _build_function_call_graph(self, ir: IR) -> Dict[str, List[str]]:
        """Build function call graph for scheduling order."""
        call_graph = {}
        for func_name in ir.functions:
            call_graph[func_name] = []
        for caller_name, caller_func in ir.functions.items():
            for block in caller_func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.op_type == OperationType.CALL and hasattr(op, 'function_name'):
                            callee_name = op.function_name
                            if callee_name in ir.functions and callee_name not in call_graph[caller_name]:
                                call_graph[caller_name].append(callee_name)
        return call_graph

    def _get_function_schedule_order(self, call_graph: Dict[str, List[str]]) -> List[str]:
        """Determine scheduling order from call graph."""
        graph = nx.DiGraph()
        for func_name, callees in call_graph.items():
            graph.add_node(func_name)
            for callee in callees:
                graph.add_edge(func_name, callee)
        try:
            return list(reversed(list(nx.topological_sort(graph))))
        except nx.NetworkXUnfeasible:
            return sorted(call_graph.keys(), key=lambda f: len(call_graph[f]))
    
    def schedule(self, ir: IR, resource_constraints: Dict[str, int]) -> IR:
        """
        Schedule operations using list scheduling algorithm.
        
        Args:
            ir: IR to schedule
            resource_constraints: Dictionary of resource types and their counts
            
        Returns:
            Scheduled IR
        """
        # Store reference to IR for function call latency calculation
        self.ir = ir
        
        # First, build the function call graph to determine scheduling order
        # (we need to schedule callee functions before caller functions)
        call_graph = self._build_function_call_graph(ir)
        
        # Get the ordering of functions to schedule
        # Functions with no callees should be scheduled first
        schedule_order = self._get_function_schedule_order(call_graph)
        logger.info(f"Scheduling functions in order: {schedule_order}")
        
        # Process each function in the determined order
        for func_name in schedule_order:
            func = ir.functions[func_name]
            # Perform pre-allocation memory analysis
            self._pre_allocation_analysis(func)
            
            # Build DFG
            dfg = self._build_dfg(func)
            
            # Identify loop structures
            loop_structures = self._identify_loop_structures(func, dfg)
            logger.info(f"Found {len(loop_structures)} loop structures")
            
            # Calculate priorities (critical path lengths)
            priorities = self._calculate_priorities(dfg)
            
            # Initialize schedule
            schedule = {}
            resource_usage = {}  # {step: {resource_type: count}}
            
            # Get nodes with no predecessors (inputs/constants)
            ready = [n for n in dfg.nodes if dfg.in_degree(n) == 0]
            
            # Sort ready nodes by priority (descending)
            ready.sort(key=lambda n: priorities[n], reverse=True)
            
            current_step = 0
            
            # Track resource usage by control step
            while ready:
                # Sort ready nodes by priority
                ready.sort(key=lambda n: priorities[n], reverse=True)
                
                # Initialize resource usage for this step
                if current_step not in resource_usage:
                    resource_usage[current_step] = {rtype: 0 for rtype in resource_constraints}
                
                # Nodes that couldn't be scheduled in this step due to resource constraints
                deferred = []
                
                # Try to schedule ready nodes
                for node in list(ready):  # Use a copy to allow modification
                    op = dfg.nodes[node]["op"]
                    op_type = op.op_type.name
                    
                    # Check resource availability for this operation type
                    if op_type in resource_constraints:
                        # If we've reached the limit for this resource type, defer scheduling
                        if resource_usage[current_step].get(op_type, 0) >= resource_constraints[op_type]:
                            deferred.append(node)
                            ready.remove(node)
                            continue
                        
                        # Track resource usage
                        resource_usage[current_step][op_type] = resource_usage[current_step].get(op_type, 0) + 1
                    
                    # Schedule the node
                    schedule[node] = current_step
                    ready.remove(node)
                    
                    # Check if new nodes become ready
                    for succ in dfg.successors(node):
                        # If all predecessors of succ are scheduled, succ is ready
                        if all(pred in schedule for pred in dfg.predecessors(succ)):
                            ready.append(succ)
                
                # If no nodes were scheduled in this step but we have deferred nodes,
                # move to the next step and add deferred nodes back to ready
                if deferred:
                    ready.extend(deferred)
                
                # Check if operations finish at this step
                for node, step in schedule.items():
                    op = dfg.nodes[node]["op"]
                    if step + self._get_operation_delay(op) == current_step:
                        # Operation finished, add successors to ready list if all predecessors are done
                        for succ in dfg.successors(node):
                            if all(pred in schedule and schedule[pred] + self._get_operation_delay(dfg.nodes[pred]["op"]) <= current_step 
                                   for pred in dfg.predecessors(succ)):
                                if succ not in ready:
                                    ready.append(succ)
                
                # Sort ready nodes by priority
                ready.sort(key=lambda n: priorities[n], reverse=True)
                
                current_step += 1
            
            # Apply schedule to operations
            single_iter_latency = 0
            
            # Track function call operations for incorporating their latencies
            call_operations = []
            
            for block in func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if op.node_id in schedule:
                            # Update operation's control step in IR
                            control_step = schedule[op.node_id]
                            op.control_step = control_step
                            
                            # Calculate and store operation delay
                            op_delay = self._get_operation_delay(op)
                            op._delay = op_delay
                            
                            # Track function call operations
                            if op.op_type == OperationType.CALL and hasattr(op, 'function_name'):
                                call_operations.append(op)
                            
                            # Track single iteration latency
                            op_end_time = control_step + op_delay
                            single_iter_latency = max(single_iter_latency, op_end_time)
            
            # Calculate total latency considering loop iterations
            total_latency = self._calculate_total_latency(func, dfg, loop_structures, single_iter_latency)
            
            # Update total latency if this function makes function calls
            # For a function with function calls, its latency should include the latency of the called functions
            if len(call_operations) > 0:
                # If this is the main function or any function that calls others but doesn't have loops,
                # ensure its latency includes the called function latency
                if single_iter_latency == 1 or total_latency == single_iter_latency:
                    max_call_latency = 0
                    for call_op in call_operations:
                        if hasattr(call_op, 'function_name'):
                            callee_name = call_op.function_name
                            if callee_name in ir.functions:
                                callee = ir.functions[callee_name]
                                if hasattr(callee, 'total_latency') and callee.total_latency > 0:
                                    max_call_latency = max(max_call_latency, callee.total_latency)
                
                    # Update total latency to include called function latency
                    if max_call_latency > 0:
                        total_latency = max(total_latency, max_call_latency + 1)  # +1 for the call operation itself
                        logger.info(f"  Updated {func_name} total latency to {total_latency} to account for function calls")
            
            # Store both latencies in the function
            logger.info(f"Function {func_name} scheduled with single iteration latency: {single_iter_latency} cycles")
            logger.info(f"Function {func_name} scheduled with total latency (including loops): {total_latency} cycles")
            
            func.single_iter_latency = single_iter_latency
            func.total_latency = total_latency
        
        return ir
        
    def _calculate_total_latency(self, func: IRFunction, dfg: nx.DiGraph, 
                              loop_structures: Dict[int, Dict], base_latency: int) -> int:
        """
        Calculate total latency considering loop iterations.
        
        Args:
            func: Function being scheduled
            dfg: Data flow graph
            loop_structures: Dictionary of loop structures
            base_latency: Base latency without loop iteration multiplication
            
        Returns:
            Total latency in cycles
        """
        if not loop_structures:
            return base_latency
            
        # Start with base latency
        total_latency = base_latency
        
        # First, build the loop hierarchy (nested loops)
        # We'll process loops from innermost to outermost
        loop_hierarchy = {}
        inner_loops = {}
        
        for loop_id, loop_info in loop_structures.items():
            parent_loop = loop_info.get('parent_loop')
            if parent_loop not in loop_hierarchy:
                loop_hierarchy[parent_loop] = []
            loop_hierarchy[parent_loop].append(loop_id)
            
            # Track which loops are inner loops of others
            if parent_loop is not None:
                if parent_loop not in inner_loops:
                    inner_loops[parent_loop] = []
                inner_loops[parent_loop].append(loop_id)
        
        # Process loops from innermost to outermost
        processed_loops = set()
        loop_latencies = {}
        
        # Helper function to process a loop and its inner loops
        def process_loop(loop_id):
            # Skip if already processed
            if loop_id in processed_loops:
                return loop_latencies.get(loop_id, 0)
            
            # Get loop info
            loop_info = loop_structures[loop_id]
            iterations = loop_info['iterations']
            if iterations <= 1:
                processed_loops.add(loop_id)
                return 0  # No need to adjust for loops with 1 or fewer iterations
            
            # First, process any inner loops
            inner_loop_latencies = 0
            if loop_id in inner_loops:
                for inner_id in inner_loops[loop_id]:
                    inner_latency = process_loop(inner_id)
                    inner_loop_latencies += inner_latency
            
            # Calculate latency of the loop body excluding inner loops
            # For this, we need to identify nodes that are in this loop but not in any inner loop
            loop_only_nodes = set(loop_info['body_nodes'])
            if loop_id in inner_loops:
                for inner_id in inner_loops[loop_id]:
                    inner_nodes = set(loop_structures[inner_id]['body_nodes'])
                    loop_only_nodes -= inner_nodes
            
            # Calculate the base body latency (excluding inner loops)
            base_body_latency = self._calculate_loop_body_latency(dfg, list(loop_only_nodes))
            
            # Total body latency is base body latency plus the latency from inner loops
            total_body_latency = base_body_latency + inner_loop_latencies
            
            # Add the repeated execution of the loop body
            # Subtract 1 from iterations since one iteration is already in the base latency
            additional_latency = total_body_latency * (iterations - 1)
            
            # Store the loop latency
            loop_latencies[loop_id] = additional_latency
            processed_loops.add(loop_id)
            
            logger.info(f"  Loop with {iterations} iterations adds {additional_latency} cycles "
                  f"(body latency: {total_body_latency}, base: {base_body_latency}, inner loops: {inner_loop_latencies})")
            
            return additional_latency
        
        # Process all top-level loops (those without a parent)
        top_level_latency = 0
        if None in loop_hierarchy:
            for loop_id in loop_hierarchy[None]:
                top_level_latency += process_loop(loop_id)
        
        # Add the top-level loop latency to the base latency
        total_latency += top_level_latency
        
        return total_latency
    
    def _calculate_loop_body_latency(self, dfg: nx.DiGraph, body_nodes: List[int]) -> int:
        """
        Calculate the latency of a loop body.
        
        Args:
            dfg: Data flow graph
            body_nodes: List of node IDs in the loop body
            
        Returns:
            Latency of the loop body in cycles
        """
        if not body_nodes:
            return 0
            
        # Find max end time of any operation in the body
        max_latency = 0
        for node_id in body_nodes:
            node = dfg.nodes[node_id]
            op = node['op']
            end_time = op.control_step + self._get_operation_delay(op)
            max_latency = max(max_latency, end_time)
            
        return max_latency
    
    def _calculate_priorities(self, dfg: nx.DiGraph) -> Dict[int, int]:
        """
        Calculate priorities (critical path lengths) for nodes in the DFG.
        
        Args:
            dfg: Data flow graph
            
        Returns:
            Dictionary of node IDs to priorities
        """
        priorities = {}
        critical_path_ops = []  # Track operations on the critical path
        
        # Calculate priorities in reverse topological order
        for node in reversed(list(nx.topological_sort(dfg))):
            if dfg.out_degree(node) == 0:  # Sink node
                priorities[node] = self._get_operation_delay(dfg.nodes[node]["op"])
            else:
                max_succ_priority = 0
                critical_successor = None
                for succ in dfg.successors(node):
                    if priorities[succ] > max_succ_priority:
                        max_succ_priority = priorities[succ]
                        critical_successor = succ
                
                priorities[node] = self._get_operation_delay(dfg.nodes[node]["op"]) + max_succ_priority
                
                # If this is potentially part of the critical path, track it for logging
                if critical_successor is not None:
                    dfg.nodes[node]["critical_successor"] = critical_successor
        
        # Find node with maximum priority (start of critical path)
        if priorities:
            max_priority = max(priorities.values())
            critical_start_nodes = [n for n, p in priorities.items() if p == max_priority and dfg.in_degree(n) == 0]
            
            # If we found a starting point for critical path, trace it
            if critical_start_nodes:
                current_node = critical_start_nodes[0]  # Use the first one if multiple exist
                
                # Trace the critical path by following critical successors
                while current_node is not None:
                    op = dfg.nodes[current_node].get("op")
                    if op:
                        critical_path_ops.append({
                            "node_id": current_node,
                            "op_type": op.op_type.name if hasattr(op, "op_type") else "Unknown",
                            "delay": self._get_operation_delay(op),
                            "cumulative_delay": priorities[current_node]
                        })
                    
                    # Move to the next node in critical path
                    current_node = dfg.nodes[current_node].get("critical_successor")
            
            # Calculate the achievable frequency based on the critical path resources
            if max_priority > 0:
                # Find the slowest resource on the critical path
                min_frequency_mhz = float('inf')
                slowest_op_type = None
                
                for op_info in critical_path_ops:
                    # Map operation type to resource type
                    op_to_resource = {
                        "ADD": "Adder_32bit",
                        "SUB": "Subtractor_32bit",
                        "MUL": "Multiplier_32bit",
                        "DIV": "Divider_32bit",
                        "MOD": "ALU_32bit",
                        "POW": "ALU_32bit",
                        "LSHIFT": "Shifter_32bit",
                        "RSHIFT": "Shifter_32bit",
                        "BIT_OR": "BitOp_32bit",
                        "BIT_AND": "BitOp_32bit",
                        "BIT_XOR": "BitOp_32bit",
                        "LOGIC_OR": "BitOp_32bit",
                        "LOGIC_AND": "BitOp_32bit",
                        "EQ": "Comparator_32bit",
                        "NEQ": "Comparator_32bit",
                        "LT": "RelationalOp_32bit",
                        "LTE": "RelationalOp_32bit",
                        "GT": "RelationalOp_32bit",
                        "GTE": "RelationalOp_32bit",
                        "NEG": "Subtractor_32bit",
                        "NOT": "BitOp_32bit",
                        "BIT_NOT": "BitOp_32bit",
                        "ASSIGN": "Register_32bit",
                        "RETURN": "Register_32bit",
                        "STORE": "Memory_1KB",
                        "LOAD": "Memory_1KB",
                        "CALL": "ALU_32bit"
                    }
                    
                    resource_type = op_to_resource.get(op_info["op_type"], "ALU_32bit")
                    try:
                        resource = self.tech_library.get_resource(resource_type)
                        if resource.frequency < min_frequency_mhz:
                            min_frequency_mhz = resource.frequency
                            slowest_op_type = op_info["op_type"]
                    except ValueError:
                        # If resource not found, use a default frequency
                        default_freq = 400.0  # MHz
                        if default_freq < min_frequency_mhz:
                            min_frequency_mhz = default_freq
                            slowest_op_type = op_info["op_type"]
                
                # The maximum achievable frequency is limited by the slowest resource
                if min_frequency_mhz == float('inf'):
                    max_frequency_mhz = 1000.0  # Default fallback
                else:
                    max_frequency_mhz = min_frequency_mhz
                
                # Store the calculated frequency for later use
                self._last_calculated_frequency = max_frequency_mhz
                
                # Log critical path information
                logger.info(f"Critical Path Analysis:")
                logger.info(f"  Maximum path delay: {max_priority} cycles")
                logger.info(f"  Slowest resource: {slowest_op_type} limiting frequency to {max_frequency_mhz:.2f} MHz")
                logger.info(f"  Calculated target frequency: {max_frequency_mhz:.2f} MHz")
                logger.info(f"  Critical path operations:")
                
                for i, op_info in enumerate(critical_path_ops):
                    op_resource_type = op_to_resource.get(op_info["op_type"], "ALU_32bit")
                    try:
                        op_resource = self.tech_library.get_resource(op_resource_type)
                        op_freq = op_resource.frequency
                    except ValueError:
                        op_freq = 400.0  # Default
                    
                    logger.info(f"    {i+1}. {op_info['op_type']} (Node {op_info['node_id']}):")
                    logger.info(f"       Delay: {op_info['delay']} cycles")
                    logger.info(f"       Max frequency: {op_freq:.2f} MHz")
                    logger.info(f"       Cumulative: {op_info['cumulative_delay']} cycles")
        
        return priorities
    
    def _get_resource_type(self, op: IROperation) -> str:
        """
        Get the resource type for an operation.
        
        Args:
            op: Operation
            
        Returns:
            Resource type string
        """
        # Map operation types to resource types
        op_to_resource = {
            "ADD": "Adder_32bit",
            "SUB": "Subtractor_32bit",
            "MUL": "Multiplier_32bit",
            "DIV": "Divider_32bit",
            "MOD": "ALU_32bit",
            "POW": "ALU_32bit",
            "LSHIFT": "Shifter_32bit",
            "RSHIFT": "Shifter_32bit",
            "BIT_OR": "BitOp_32bit",
            "BIT_AND": "BitOp_32bit",
            "BIT_XOR": "BitOp_32bit",
            "LOGIC_OR": "BitOp_32bit",
            "LOGIC_AND": "BitOp_32bit",
            "EQ": "Comparator_32bit",
            "NEQ": "Comparator_32bit",
            "LT": "RelationalOp_32bit",
            "LTE": "RelationalOp_32bit",
            "GT": "RelationalOp_32bit",
            "GTE": "RelationalOp_32bit",
            "NEG": "Subtractor_32bit",
            "NOT": "BitOp_32bit",
            "BIT_NOT": "BitOp_32bit",
            "ASSIGN": "Register_32bit",
            "RETURN": "Register_32bit",
            "STORE": "Memory_1KB",
            "LOAD": "Memory_1KB",
            "CALL": "ALU_32bit"
        }
        
        return op_to_resource.get(op.op_type.name, "ALU_32bit") 