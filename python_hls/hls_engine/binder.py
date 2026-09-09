"""
Binder for HLS resource binding.
"""

from typing import Dict, List, Set, Tuple, Any
import networkx as nx
import numpy as np

from ..ir.ir_nodes import IR, IRFunction, IROperation
from ..netlist.netlist import NetlistOperation, NetlistResource, NetlistModule


class Binder:
    """Binder for hardware resource binding in HLS."""
    
    def __init__(self):
        """Initialize the binder."""
        # Dictionary to track resource bindings
        self.resource_bindings = {}
        
        # Mapping from operation types to resource types
        self.op_to_resource = {
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
        
        # Default latencies for operations
        self.default_latencies = {
            "ALU_32bit": 1,
            "Adder_32bit": 1,
            "Subtractor_32bit": 1,
            "BitOp_32bit": 1,
            "Comparator_32bit": 1,
            "RelationalOp_32bit": 1,
            "Shifter_32bit": 1,
            "Multiplier_32bit": 2,
            "Divider_32bit": 10,
            "Memory_1KB": 1,
            "Register_32bit": 1,
            # Add more as needed
        }
    
    def bind(self, ir: IR, allocated_resources: Dict[str, int], 
             netlist_resources: List[NetlistResource]) -> Tuple[IR, List[NetlistOperation]]:
        """
        Bind operations to hardware resources.
        
        Args:
            ir: Scheduled IR
            allocated_resources: Allocated resources
            netlist_resources: Netlist resources
            
        Returns:
            Tuple of (updated IR, netlist operations)
        """
        netlist_operations = []
        
        # Group resources by type
        resources_by_type = {}
        for resource in netlist_resources:
            if resource.type not in resources_by_type:
                resources_by_type[resource.type] = []
            resources_by_type[resource.type].append(resource)
        
        # Find scratchpad memory resources
        scratchpad_resources = {}
        for resource in netlist_resources:
            if resource.memory_type == "scratchpad":
                scratchpad_resources[resource.name] = resource
        
        # Bind scratchpad memory to variables that need it
        var_to_memory_map = self._bind_variables_to_memory(ir, scratchpad_resources)
        
        # Process each function
        for func_name, func in ir.functions.items():
            # Group operations by type and control step
            ops_by_type_step = {}
            for block in func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        resource_type = self._get_resource_type(op)
                        step = op.control_step
                        
                        if resource_type not in ops_by_type_step:
                            ops_by_type_step[resource_type] = {}
                        
                        if step not in ops_by_type_step[resource_type]:
                            ops_by_type_step[resource_type][step] = []
                        
                        ops_by_type_step[resource_type][step].append(op)
            
            # Bind operations to resources
            bindings = self._left_edge_binding(ops_by_type_step, resources_by_type)
            
            # Create netlist operations
            for resource_type, step_ops in ops_by_type_step.items():
                for step, ops in step_ops.items():
                    for op in ops:
                        if op in bindings and bindings[op] is not None:
                            resource = bindings[op]
                            
                            # Handle memory operations specially
                            # print(op.op_type.name, op.result.name, var_to_memory_map)
                            if op.op_type is not None and op.op_type.name in ["LOAD", "STORE"] and op.result and op.result.name and var_to_memory_map is not None and op.result.name in var_to_memory_map:
                                memory_resource = var_to_memory_map[op.result.name]
                                
                                # Create memory access operation
                                memory_op = NetlistOperation(
                                    operation=op.op_type.name,
                                    operands=[op_arg.name if hasattr(op_arg, "name") else str(op_arg) for op_arg in (op.operands or [])],
                                    result=op.result.name if op.result else "",
                                    control_step=step
                                )
                                
                                # Set target memory resource
                                memory_op.memory_resource = memory_resource.name
                                netlist_operations.append(memory_op)
                            else:
                                # Regular operation
                                netlist_op = NetlistOperation(
                                    operation=op.op_type.name if op.op_type is not None else "UNKNOWN",
                                    operands=[op_arg.name if hasattr(op_arg, "name") else str(op_arg) for op_arg in (op.operands or [])],
                                    result=op.result.name if op.result else "",
                                    control_step=step
                                )
                                
                                netlist_operations.append(netlist_op)
        
        return ir, netlist_operations
    
    def _left_edge_binding(self, ops_by_type_step: Dict[str, Dict[int, List[IROperation]]], 
                         resources_by_type: Dict[str, List[NetlistResource]]) -> Dict[IROperation, NetlistResource]:
        """
        Perform left-edge algorithm for resource binding.
        
        Args:
            ops_by_type_step: Operations grouped by type and control step
            resources_by_type: Resources grouped by type
            
        Returns:
            Dictionary mapping operations to resources
        """
        bindings = {}
        
        # Process each resource type
        for resource_type, step_ops in ops_by_type_step.items():
            if resource_type not in resources_by_type:
                # Skip if no resources of this type
                continue
            
            resources = resources_by_type[resource_type]
            
            # Create compatibility graph
            compatibility_graph = self._create_compatibility_graph(step_ops)
            
            # Sort operations by start time
            all_ops = []
            for step, ops in step_ops.items():
                all_ops.extend(ops)
            
            all_ops.sort(key=lambda op: op.control_step)
            
            # Assign resources using left-edge algorithm
            resource_lifetimes = []
            for i in range(len(resources)):
                resource_lifetimes.append((-1, -1))  # (start, end) times
            
            for op in all_ops:
                op_start = op.control_step
                op_end = op_start + self._get_operation_latency(op)
                
                # Find a resource that's not in use at this time
                resource_idx = -1
                for i, (res_start, res_end) in enumerate(resource_lifetimes):
                    if res_end <= op_start:
                        resource_idx = i
                        break
                
                if resource_idx == -1:
                    # No resource available, this shouldn't happen with proper allocation
                    continue
                
                # Assign the resource
                bindings[op] = resources[resource_idx]
                resource_lifetimes[resource_idx] = (op_start, op_end)
                
                # Sort resource lifetimes to keep the list in end time order
                resource_lifetimes.sort(key=lambda lifetime: lifetime[1])
        
        return bindings
    
    def _create_compatibility_graph(self, step_ops: Dict[int, List[IROperation]]) -> nx.Graph:
        """
        Create a compatibility graph for operations.
        
        Operations are compatible if they can share a resource (don't overlap in time).
        
        Args:
            step_ops: Operations grouped by control step
            
        Returns:
            Compatibility graph
        """
        graph = nx.Graph()
        
        # Get all operations
        all_ops = []
        for step, ops in step_ops.items():
            all_ops.extend(ops)
        
        # Add nodes for all operations
        for op in all_ops:
            graph.add_node(op.node_id, op=op)
        
        # Add edges for compatible operations
        for i, op1 in enumerate(all_ops):
            op1_start = op1.control_step
            op1_end = op1_start + self._get_operation_latency(op1)
            
            for j in range(i + 1, len(all_ops)):
                op2 = all_ops[j]
                op2_start = op2.control_step
                op2_end = op2_start + self._get_operation_latency(op2)
                
                # Check if operations overlap in time
                if op1_end <= op2_start or op2_end <= op1_start:
                    # No overlap, can share a resource
                    graph.add_edge(op1.node_id, op2.node_id)
        
        return graph
    
    def _get_resource_type(self, op: IROperation) -> str:
        """
        Get the resource type for an operation.
        
        Args:
            op: Operation
            
        Returns:
            Resource type string
        """
        # Check if op.op_type is None
        if op.op_type is None:
            return "ALU_32bit"  # Default resource type
            
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
            "CALL": "ALU_32bit",
            # FIFO and Crossbar operation mappings
            "FIFO_WRITE": "FIFO_32bit",
            "FIFO_READ": "FIFO_32bit",
            "CROSSBAR_ROUTE": "Crossbar_32bit",
            # AXI-Stream operation mappings
            "AXIS_FIFO_WRITE": "FIFO_AXIS_32bit",
            "AXIS_FIFO_READ": "FIFO_AXIS_32bit",
            # AXI-Lite operation mappings
            "AXILITE_FIFO_WRITE": "FIFO_AXILITE_32bit",
            "AXILITE_FIFO_READ": "FIFO_AXILITE_32bit"
        }
        
        return op_to_resource.get(op.op_type.name, "ALU_32bit")
    
    def _get_operation_latency(self, op: IROperation) -> int:
        """
        Get the latency of an operation in control steps.
        
        Args:
            op: Operation
            
        Returns:
            Latency in control steps
        """
        return self.default_latencies.get(self._get_resource_type(op), 1)
    
    def create_netlist_module(self, func_name: str, netlist_operations: List[NetlistOperation],
                            netlist_resources: List[NetlistResource]) -> NetlistModule:
        """
        Create a netlist module from the binding results.
        
        Args:
            func_name: Function name
            netlist_operations: Bound operations
            netlist_resources: Allocated resources
            
        Returns:
            Netlist module
        """
        module = NetlistModule(name=func_name)
        
        # Add resources
        for resource in netlist_resources:
            module.add_resource(resource)
        
        # Add operations
        for op in netlist_operations:
            module.add_operation(op)
        
        # Set metrics
        module.latency = self._calculate_latency(netlist_operations)
        module.area = sum(r.area for r in netlist_resources)
        module.power = sum(r.power for r in netlist_resources)
        
        return module
    
    def _calculate_latency(self, operations: List[NetlistOperation]) -> int:
        """
        Calculate the latency of the scheduled operations.
        
        Args:
            operations: Scheduled operations
            
        Returns:
            Latency in control steps
        """
        if not operations:
            return 0
        
        # Find the latest operation completion
        max_step = 0
        for op in operations:
            op_end = op.control_step + self._get_operation_latency_from_name(op.operation)
            max_step = max(max_step, op_end)
        
        return max_step
    
    def _get_operation_latency_from_name(self, op_name: str) -> int:
        """
        Get the latency of an operation from its name.
        
        Args:
            op_name: Operation name
            
        Returns:
            Latency in control steps
        """
        return self.default_latencies.get(op_name, 1)
    
    def _bind_variables_to_memory(self, ir: IR, scratchpad_resources: Dict[str, NetlistResource]) -> Dict[str, NetlistResource]:
        """
        Bind variables that need scratchpad memory to memory resources.
        
        Args:
            ir: IR to process
            scratchpad_resources: Available scratchpad memory resources
            
        Returns:
            Mapping from variable names to allocated memory resources
        """
        var_to_memory_map = {}
        
        # Group scratchpad resources by size
        resources_by_size = {}
        for name, resource in scratchpad_resources.items():
            size_kb = resource.memory_size // 1024  # Convert bytes to KB
            if size_kb not in resources_by_size:
                resources_by_size[size_kb] = []
            resources_by_size[size_kb].append(resource)
        
        # Process each function
        for func_name, func in ir.functions.items():
            for var_name, var in func.local_vars.items():
                if var.is_scratchpad:
                    # Calculate required size in KB
                    size_bits = var.bit_width * var.memory_size
                    size_kb = (size_bits + 8191) // 8192  # Round up to nearest KB
                    
                    # Find a suitable memory resource
                    allocated_resource = None
                    
                    # Try to find exact size match first
                    if size_kb in resources_by_size and resources_by_size[size_kb]:
                        allocated_resource = resources_by_size[size_kb].pop(0)
                    else:
                        # Find the smallest resource that can fit this variable
                        suitable_sizes = [s for s in resources_by_size.keys() if s >= size_kb]
                        if suitable_sizes:
                            best_size = min(suitable_sizes)
                            if resources_by_size[best_size]:
                                allocated_resource = resources_by_size[best_size].pop(0)
                    
                    if allocated_resource:
                        var_to_memory_map[var_name] = allocated_resource 