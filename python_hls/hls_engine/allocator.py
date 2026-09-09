"""
Allocation module for HLS.

This module handles resource allocation and binding for the HLS compiler.
"""

import logging
from typing import Dict, List, Set, Tuple
import networkx as nx
import os

from ..ir.ir_nodes import IR, IRFunction, IROperation, OperationType, StreamingComponent
from ..tech.tech_library import TechLibrary, ResourceModel
from ..netlist.netlist import NetlistResource

# Set up module logger
logger = logging.getLogger(__name__)

class Allocator:
    """Resource allocator for HLS."""
    
    def __init__(self, tech_library: TechLibrary):
        """
        Initialize the allocator.
        
        Args:
            tech_library: Technology library for resource models
        """
        self.tech_library = tech_library
        self.ir = None  # Will store a reference to the IR during allocation
    
    def allocate(self, ir: IR, optimization_target: str = "area") -> Tuple[IR, Dict[str, int]]:
        """
        Allocate hardware resources for operations in the IR.
        
        Args:
            ir: Scheduled IR
            optimization_target: Target to optimize for ("area", "performance", "power")
            
        Returns:
            Tuple of (updated IR, resource allocation)
        """
        # Store a reference to the IR for use by other methods
        self.ir = ir
        
        total_resources = {}
        total_memory_size = 0
        
        # Process each function
        for func_name, func in ir.functions.items():
            # Track max unroll factor in blocks for proper scaling
            max_block_unroll = 1
            
            # Get overall function unroll factor
            func.total_unroll_factor = getattr(func, 'total_unroll_factor', 1)
            
            # Scan for unroll factors in blocks - ONLY if unrolling was explicitly requested
            for block in func.blocks:
                # Only consider unroll factors if unrolling was explicitly requested
                if (hasattr(block, 'unroll') and block.unroll and 
                    hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                    max_block_unroll = max(max_block_unroll, block.unroll_factor)
                    
                    # If this is a fully unrolled loop, adjust based on iterations
                    if hasattr(block, 'full_unroll') and block.full_unroll:
                        if hasattr(block, 'loop_iterations') and block.loop_iterations > 0:
                            max_block_unroll = max(max_block_unroll, block.loop_iterations)
            
            # Store max block unroll factor for resource scaling
            func.max_block_unroll = max_block_unroll
            
            # Identify large variables that need scratchpad memory
            self._identify_scratchpad_variables(func)
            
            # Track total memory requirements across all functions
            # Only count variables that actually use scratchpad memory (not register-based)
            for var_name, var in func.local_vars.items():
                if var.is_scratchpad or (var.data_type == "ARRAY" and not getattr(var, 'is_register', False)):
                    total_memory_size += var.bit_width * var.memory_size
            
            # Get required resources per control step
            resources_per_step = self._analyze_resource_usage(func)
            
            # Add memory requirements
            memory_resources = self._analyze_memory_requirements(func)
            
            # Allocate based on optimization target
            if optimization_target == "area":
                allocated = self._allocate_minimize_area(resources_per_step)
                # Area optimization uses resource sharing which can increase execution time
                self._update_execution_time_for_resource_sharing(func, resources_per_step, allocated)
            elif optimization_target == "performance":
                allocated = self._allocate_maximize_performance(resources_per_step)
            elif optimization_target == "power":
                allocated = self._allocate_minimize_power(resources_per_step)
                # When power optimization reduces resources, update execution time
                self._update_execution_time_for_reduced_resources(func, resources_per_step, allocated)
            else:
                allocated = self._allocate_minimize_area(resources_per_step)
                # Default area optimization also uses resource sharing
                self._update_execution_time_for_resource_sharing(func, resources_per_step, allocated)
            
            # Add memory resources to allocation
            for res_type, count in memory_resources.items():
                if res_type not in allocated:
                    allocated[res_type] = 0
                allocated[res_type] += count
            
            # Ensure at least some basic resources are allocated
            # This is to ensure area values are properly scaled with tech node
            if not allocated:
                # Add minimum set of resources for any function
                allocated = {
                    "ALU_32bit": 1,
                    "Register_32bit": 4,
                    "Multiplier_32bit": 1,
                    "Memory_1KB": 1,
                    "MUX_32bit": 2  # Minimum MUXes
                }
            
            # Allocate MUX resources based on application complexity and computational resources
            total_compute_resources = 0
            for res_type, count in allocated.items():
                if any(rt in res_type for rt in ["ALU", "Adder", "Subtractor", "Multiplier", "Divider", "BitOp", "Comparator", "RelationalOp", "Shifter"]):
                    total_compute_resources += count
            
            # Store the original compute resource counts before adjusting MUXes
            original_resource_counts = {key: value for key, value in allocated.items()}
            
            # Estimate complexity from the function
            complexity = self._estimate_function_complexity(func)
            
            # Determine number of MUXes based on complexity and compute resources
            # More complex functions and more computational units require more MUXes for input selection
            mux_count = max(2, min(32, int(total_compute_resources * 0.75)))  # At least 2, at most 32 MUXes
            
            # Adjust based on function complexity
            if complexity > 20:  # Very complex function
                mux_count = max(mux_count, min(32, int(complexity * 0.4)))
            elif complexity > 10:  # Moderately complex function
                mux_count = max(mux_count, min(16, int(complexity * 0.3)))
            
            # For unrolled loops, increase MUX count to handle parallel execution
            # Only scale if unrolling was explicitly requested (not just from loop_count pragma)
            has_explicit_unrolling = any(
                hasattr(block, 'unroll') and block.unroll and 
                hasattr(block, 'unroll_factor') and block.unroll_factor > 1
                for block in func.blocks
            )
            if has_explicit_unrolling and func.total_unroll_factor > 1:
                # Scale up MUXes based on unroll factor
                unroll_scale = min(4.0, max(1.0, func.total_unroll_factor / 2))
                mux_count = max(mux_count, min(64, int(mux_count * unroll_scale)))
            
            # Ensure we have MUXes in the allocation
            allocated["MUX_32bit"] = mux_count
            
            # Calculate the ratio of MUXes to computational resources
            # A healthy ratio ensures good connectivity
            mux_to_compute_ratio = mux_count / max(1, total_compute_resources)
            
            # If MUX count is high relative to compute resources, we should increase MUXes instead of compute resources
            # Compute resources are critical for datapath performance and shouldn't be unnecessarily increased
            if mux_to_compute_ratio > 1.5:  # More than 1.5 MUXes per compute unit
                # Instead of scaling compute resources, increase MUXes to improve connectivity
                # This preserves critical compute resources while ensuring sufficient routing
                target_mux_count = int(mux_count * 1.25)  # Increase MUXes by 25%
                
                # Cap the maximum number of MUXes to avoid excessive routing overhead
                allocated["MUX_32bit"] = min(96, target_mux_count)
                
                # Update the mux_count variable for later calculations
                mux_count = allocated["MUX_32bit"]
                
                # Recalculate the ratio after adjustment
                mux_to_compute_ratio = mux_count / max(1, total_compute_resources)
                
                # Also ensure register count is sufficient for the increased compute resources
                if "Register_32bit" in allocated:
                    # Each compute unit typically needs at least 2 registers
                    min_registers = total_compute_resources * 2
                    allocated["Register_32bit"] = max(allocated["Register_32bit"], int(min_registers))
            
            # Update total resources
            for res_type, count in allocated.items():
                if res_type not in total_resources:
                    total_resources[res_type] = 0
                total_resources[res_type] += count
        
        # Apply final scaling based on total memory size
        # This ensures larger problems get appropriate hardware scaling
        if total_memory_size > 0:
            memory_scale_factor = max(1.0, min(4.0, total_memory_size / (1024 * 1024)))  # Scale up to 4x for very large memory footprints
            
            # If problem is large enough, add additional resources
            if memory_scale_factor > 1.2:
                # Find existing memory resources
                memory_resources = []
                for res_type in total_resources.keys():
                    if "Memory" in res_type or "Scratchpad" in res_type:
                        memory_resources.append(res_type)
                
                # Store original resource counts before scaling
                original_total_resources = {key: value for key, value in total_resources.items()}
                
                # If we have memory resources, scale them up
                if memory_resources:
                    for res_type in memory_resources:
                        # Only scale up if we have resources of this type
                        if res_type in total_resources and total_resources[res_type] > 0:
                            # Apply scaling with some randomization to avoid identical resource counts
                            original_count = total_resources[res_type]
                            scaled_count = int(original_count * memory_scale_factor * (0.9 + 0.2 * (hash(res_type) % 10) / 10))
                            total_resources[res_type] = max(original_count, scaled_count)
                
                # Also scale MUXes for large memory problems (they need more input selection)
                if "MUX_32bit" in total_resources:
                    original_mux_count = total_resources["MUX_32bit"]
                    scaled_mux_count = int(original_mux_count * memory_scale_factor * 1.2)  # Extra scaling for MUXes
                    total_resources["MUX_32bit"] = max(original_mux_count, scaled_mux_count)
                    
                    # If MUX count increases significantly, ensure compute resources are scaled proportionally
                    if scaled_mux_count > original_mux_count * 1.3:  # 30% increase in MUXes
                        compute_scale_factor = scaled_mux_count / original_mux_count
                        
                        for res_type in total_resources.keys():
                            if any(rt in res_type for rt in ["ALU", "Adder", "Subtractor", "Multiplier", "Divider", "BitOp", "Comparator", "RelationalOp", "Shifter"]):
                                # Never decrease, only increase compute resources
                                total_resources[res_type] = max(total_resources[res_type], 
                                                              int(original_total_resources[res_type] * compute_scale_factor * 0.8))
                        
                        # Also ensure we have enough registers to support the compute resources and register-based variables
                        if "Register_32bit" in total_resources:
                            compute_resources_count = sum(total_resources.get(res, 0) for res in 
                                                        ["ALU_32bit", "Adder_32bit", "Subtractor_32bit", "Multiplier_32bit", 
                                                         "Divider_32bit", "BitOp_32bit", "Comparator_32bit", "RelationalOp_32bit", 
                                                         "Shifter_32bit"])
                            
                            min_registers = compute_resources_count * 2  # Each compute unit needs at least 2 registers
                            
                            # Add registers needed for register-based variables
                            register_based_variables = 0
                            for func_name, func in ir.functions.items():
                                for var_name, var in func.local_vars.items():
                                    if getattr(var, 'is_register', False):
                                        # Each register-based variable needs registers proportional to its size
                                        var_size_words = max(1, (var.bit_width * var.memory_size + 31) // 32)  # Round up to 32-bit words
                                        register_based_variables += var_size_words
                            
                            min_registers += register_based_variables
                            total_resources["Register_32bit"] = max(total_resources["Register_32bit"], int(min_registers))
        
        return ir, total_resources
    
    def _identify_scratchpad_variables(self, func: IRFunction) -> None:
        """
        Identify variables that need scratchpad memory.
        Small variables (<128 bytes) should use registers instead of scratchpad,
        especially when there are many ports (high unroll factors).
        
        Args:
            func: Function to analyze
        """
        # Threshold in bits beyond which we allocate a scratchpad
        SCRATCHPAD_THRESHOLD = 1024  # 1KB (original threshold)
        SMALL_VARIABLE_THRESHOLD = 1024  # 128 bytes = 1024 bits
        
        # Get function-level unroll factor to determine port pressure
        total_unroll_factor = getattr(func, 'total_unroll_factor', 1)
        max_block_unroll = getattr(func, 'max_block_unroll', 1)
        effective_unroll_factor = max(total_unroll_factor, max_block_unroll)
        
        # Count memory access operations to determine port pressure
        memory_access_count = 0
        for block in func.blocks:
            block_unroll_factor = getattr(block, 'unroll_factor', 1)
            for instr in block.instructions:
                for op in instr.operations:
                    if hasattr(op, 'op_type') and op.op_type.name in ['LOAD', 'STORE']:
                        memory_access_count += block_unroll_factor
        
        # Scale memory accesses by function-level unroll factor
        total_memory_accesses = memory_access_count * effective_unroll_factor
        
        # Determine if we have high port pressure
        # High port pressure means we should prefer registers over scratchpad for small variables
        high_port_pressure = (effective_unroll_factor >= 4) or (total_memory_accesses >= 16)
        
        for var_name, var in func.local_vars.items():
            # Calculate total memory size in bits
            total_size_bits = var.bit_width * var.memory_size
            
            # Optimization: For small variables, especially under high port pressure,
            # prefer registers over scratchpad memory
            if total_size_bits < SMALL_VARIABLE_THRESHOLD:  # < 128 bytes
                # Mark as register-based instead of scratchpad
                var.is_register = True
                var.is_scratchpad = False
                
                # Log the decision for debugging
                if high_port_pressure:
                    logger.info(f"Variable '{var_name}' ({total_size_bits} bits) using registers due to high port pressure "
                              f"(unroll_factor={effective_unroll_factor}, memory_accesses={total_memory_accesses})")
                else:
                    logger.info(f"Variable '{var_name}' ({total_size_bits} bits) using registers due to small size")
                
                continue
            
            # For larger variables, use the original scratchpad threshold logic
            if total_size_bits >= SCRATCHPAD_THRESHOLD:
                var.is_scratchpad = True
                
                # Round up to nearest KB for scratchpad allocation
                kb_size = (total_size_bits + 8191) // 8192  # 8192 bits = 1KB, round up
                var.memory_size = kb_size * 1024 // var.bit_width  # Update memory size accordingly
                
                logger.info(f"Variable '{var_name}' ({total_size_bits} bits) using scratchpad memory")
            else:
                # Variables between 128 bytes and 1KB: decide based on port pressure and array characteristics
                # For high port pressure, prefer registers even for medium-sized variables
                if high_port_pressure and total_size_bits < (SMALL_VARIABLE_THRESHOLD * 2):  # < 256 bytes
                    var.is_register = True
                    var.is_scratchpad = False
                    logger.info(f"Variable '{var_name}' ({total_size_bits} bits) using registers due to high port pressure")
                else:
                    # Use scratchpad for medium-sized variables under normal conditions
                    var.is_scratchpad = True
                    
                    # Round up to nearest KB for scratchpad allocation
                    kb_size = (total_size_bits + 8191) // 8192  # 8192 bits = 1KB, round up
                    var.memory_size = kb_size * 1024 // var.bit_width  # Update memory size accordingly
                    
                    logger.info(f"Variable '{var_name}' ({total_size_bits} bits) using scratchpad memory (medium size)")
    
    def _analyze_memory_requirements(self, func: IRFunction) -> Dict[str, int]:
        """
        Analyze memory requirements for the function.
        
        Args:
            func: Function to analyze
            
        Returns:
            Dictionary of {memory_resource_type: count}
        """
        memory_resources = {}
        array_vars = []
        total_memory_bits = 0
        
        # Get function-level unroll factor
        total_unroll_factor = getattr(func, 'total_unroll_factor', 1)
        
        # First pass: identify array variables and calculate total memory requirements
        # Only consider variables that actually need scratchpad memory (not register-based)
        for var_name, var in func.local_vars.items():
            if var.is_scratchpad or (var.data_type == "ARRAY" and not getattr(var, 'is_register', False)):
                # Calculate total memory size in bits
                var_size_bits = var.bit_width * var.memory_size
                total_memory_bits += var_size_bits
                array_vars.append((var_name, var, var_size_bits))
        
        # Scale memory based on problem size - track largest arrays and loop iterations
        memory_scale_factor = 1.0
        if hasattr(func, 'loop_count') and func.loop_count > 0:
            # If we have nested loops with large iteration counts, this might indicate
            # tiled access to large arrays
            if hasattr(func, 'loop_iterations') and func.loop_iterations > 0:
                # Apply a scaling factor based on loop iterations - larger problems need more memory
                memory_scale_factor = min(4.0, max(1.0, func.loop_iterations / 50))
                
                # Check for large loop counts which might indicate matrix computations
                loop_count_scale = min(2.0, max(1.0, func.loop_count / 3))
                memory_scale_factor *= loop_count_scale
        
        # Adjust memory scale factor based on unrolling
        # When loops are unrolled, we generally need more memory ports but not necessarily more total memory
        port_scale_factor = max(1.0, min(4.0, total_unroll_factor / 2))
        
        # Apply scaling to total memory
        scaled_total_memory = total_memory_bits * memory_scale_factor
        
        # Second pass: allocate appropriate memory resources based on scaled requirements
        large_arrays_count = 0
        medium_arrays_count = 0
        small_arrays_count = 0
        
        for var_name, var, var_size_bits in array_vars:
            # Scale individual array sizes based on the overall scaling
            scaled_size = var_size_bits * memory_scale_factor
            
            # Categorize arrays by size
            if scaled_size > 131072:  # > 16KB
                large_arrays_count += 1
            elif scaled_size > 32768:  # > 4KB
                medium_arrays_count += 1
            else:
                small_arrays_count += 1
        
        # Apply port scaling due to unrolling - unrolled loops need more memory ports
        if port_scale_factor > 1.0:
            large_arrays_count = int(large_arrays_count * port_scale_factor)
            medium_arrays_count = int(medium_arrays_count * port_scale_factor)
            small_arrays_count = int(small_arrays_count * port_scale_factor)
        
        # Allocate appropriate scratchpad sizes based on array counts
        if large_arrays_count > 0:
            if "Scratchpad_64KB" not in memory_resources:
                memory_resources["Scratchpad_64KB"] = 0
            memory_resources["Scratchpad_64KB"] += large_arrays_count
        
        if medium_arrays_count > 0:
            if "Scratchpad_16KB" not in memory_resources:
                memory_resources["Scratchpad_16KB"] = 0
            memory_resources["Scratchpad_16KB"] += medium_arrays_count
        
        if small_arrays_count > 0:
            if "Scratchpad_4KB" not in memory_resources:
                memory_resources["Scratchpad_4KB"] = 0
            memory_resources["Scratchpad_4KB"] += small_arrays_count
        
        # Add cache resources based on function complexity and memory requirements
        complexity = self._estimate_function_complexity(func)
        
        # Scale complexity by unroll factor since unrolled loops lead to more complex access patterns
        scaled_complexity = complexity * max(1.0, min(2.0, total_unroll_factor / 4))
        
        # if scaled_complexity > 10:  # High complexity function
        #     # Allocate cache based on total memory requirements
        #     if scaled_total_memory > 524288:  # > 64KB
        #         # Scale cache count based on unroll factor for very large problems
        #         cache_count = max(2, int(2 * port_scale_factor))
        #         memory_resources["Cache_16KB"] = cache_count
        #     elif scaled_total_memory > 131072:  # > 16KB
        #         # Scale cache count based on unroll factor
        #         cache_count = max(1, int(1 * port_scale_factor))
        #         memory_resources["Cache_16KB"] = cache_count
        
        return memory_resources
    
    def _estimate_function_complexity(self, func: IRFunction) -> int:
        """
        Estimate the complexity of a function based on various metrics.
        
        Args:
            func: Function to analyze
            
        Returns:
            Complexity score (higher is more complex)
        """
        complexity = 0
        
        # Get function-level unroll factor
        total_unroll_factor = getattr(func, 'total_unroll_factor', 1)
        
        # Factor 1: Number of operations
        op_count = 0
        for block in func.blocks:
            # Check if this block has an unroll factor
            block_unroll_factor = getattr(block, 'unroll_factor', 1)
            
            # Count operations, scaling by block unroll factor
            instr_count_for_block = 0
            for instr in block.instructions:
                instr_count_for_block += len(instr.operations)
            
            # Scale operation count by unroll factor if this block is unrolled
            op_count += instr_count_for_block * block_unroll_factor
        
        complexity += op_count // 5  # Each 5 operations add 1 point
        
        # Factor 2: Number of blocks (control flow complexity)
        complexity += len(func.blocks) // 2
        
        # Factor 3: Loop nesting and iterations
        if hasattr(func, 'loop_count') and func.loop_count > 0:
            # Base score for loop complexity
            base_loop_complexity = func.loop_count * 2  # Each loop adds 2 points
            
            # Adjust loop complexity based on unrolling
            # Unrolled loops introduce more complexity due to parallel execution
            # Only scale if unrolling was explicitly requested
            has_explicit_unrolling = any(
                hasattr(block, 'unroll') and block.unroll and 
                hasattr(block, 'unroll_factor') and block.unroll_factor > 1
                for block in func.blocks
            )
            if has_explicit_unrolling and total_unroll_factor > 1:
                # Scale the loop complexity by a factor that increases with unroll factor
                # but not linearly (diminishing returns)
                unroll_scale = max(1.0, min(3.0, 1.0 + total_unroll_factor / 4.0))
                base_loop_complexity = int(base_loop_complexity * unroll_scale)
            
            complexity += base_loop_complexity
            
            if hasattr(func, 'loop_iterations') and func.loop_iterations > 0:
                # More iterations means more complexity
                if func.loop_iterations > 100:
                    complexity += 10
                elif func.loop_iterations > 50:
                    complexity += 5
                elif func.loop_iterations > 10:
                    complexity += 2
        
        # Factor 4: Memory access patterns
        memory_access_count = 0
        for block in func.blocks:
            # Get block-level unroll factor
            block_unroll_factor = getattr(block, 'unroll_factor', 1)
            
            # Count memory operations in this block
            block_memory_ops = 0
            for instr in block.instructions:
                for op in instr.operations:
                    if op.op_type.name in ['LOAD', 'STORE']:
                        block_memory_ops += 1
            
            # Scale by unroll factor if block is unrolled
            memory_access_count += block_memory_ops * block_unroll_factor
        
        # Memory accesses in unrolled loops are more complex due to potential port conflicts
        memory_complexity_factor = 3  # Default: each 3 memory accesses add 1 point
        # Only scale if unrolling was explicitly requested
        has_explicit_unrolling = any(
            hasattr(block, 'unroll') and block.unroll and 
            hasattr(block, 'unroll_factor') and block.unroll_factor > 1
            for block in func.blocks
        )
        if has_explicit_unrolling and total_unroll_factor > 1:
            # Reduce the divisor for unrolled loops to increase complexity score
            # This reflects the increased complexity of managing concurrent memory accesses
            memory_complexity_factor = max(1, int(3 / min(3, total_unroll_factor / 2)))
        
        complexity += memory_access_count // memory_complexity_factor
        
        return complexity
    
    def _analyze_resource_usage(self, func: IRFunction) -> Dict[int, Dict[str, int]]:
        """
        Analyze resource usage for each control step in the function.
        
        Args:
            func: Function to analyze
            
        Returns:
            Dictionary mapping control step to resource requirements
        """
        resources_per_step = {}
        
        # Track memory operations to determine AGU requirements
        memory_ops_per_step = {}
        total_memory_ops = 0
        
        # Track control complexity for FSM requirements
        control_complexity = 0
        has_loops = False
        has_conditionals = False
        
        # Analyze control flow complexity
        for block in func.blocks:
            if len(block.successors) > 1:
                has_conditionals = True
                control_complexity += len(block.successors)
            if block.loop_header is not None:
                has_loops = True
                control_complexity += 2  # Loop adds significant control complexity
        
        # Process all operations
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    step = getattr(op, 'control_step', 0)
                    
                    if step not in resources_per_step:
                        resources_per_step[step] = {}
                        memory_ops_per_step[step] = 0
                    
                    # Get resource type for this operation
                    resource_type = self._get_resource_type(op)
                    if resource_type not in resources_per_step[step]:
                        resources_per_step[step][resource_type] = 0
                    resources_per_step[step][resource_type] += 1
                    
                    # Track memory operations for AGU allocation
                    if op.op_type and op.op_type.name in ['LOAD', 'STORE', 'ARRAY_ACCESS']:
                        memory_ops_per_step[step] += 1
                        total_memory_ops += 1
        
        # Allocate Address Generation Units based on memory operations and loop unrolling
        if total_memory_ops > 0:
            # Calculate AGU requirements
            max_concurrent_memory_ops = max(memory_ops_per_step.values()) if memory_ops_per_step else 0
            
            # Check for loop unrolling which increases memory parallelism
            unroll_factor = 1
            has_unrolled_loops = False
            for block in func.blocks:
                if (hasattr(block, 'unroll') and block.unroll and 
                    hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                    unroll_factor = max(unroll_factor, block.unroll_factor)
                    has_unrolled_loops = True
            
            # For complex memory access patterns, allocate more AGUs
            base_agu_count = max(1, min(4, max_concurrent_memory_ops))  # 1-4 AGUs
            
            # Scale AGU count based on unroll factor for parallel memory access
            if has_unrolled_loops and unroll_factor > 1:
                # Unrolled loops need more AGUs for parallel memory access
                agu_count = min(8, base_agu_count * min(4, unroll_factor))  # Cap at 8 AGUs
            else:
                agu_count = base_agu_count
            
            # If we have arrays or complex addressing, increase AGU count
            for var_name, var in func.local_vars.items():
                if var.data_type == "ARRAY" and var.memory_size > 32:
                    if has_unrolled_loops:
                        agu_count = max(agu_count, 4)  # More AGUs for unrolled array access
                    else:
                        agu_count = max(agu_count, 2)  # At least 2 AGUs for large arrays
            
            # Distribute AGUs across steps that have memory operations
            for step, mem_ops in memory_ops_per_step.items():
                if mem_ops > 0:
                    if "AGU_32bit" not in resources_per_step[step]:
                        resources_per_step[step]["AGU_32bit"] = 0
                    # Allocate AGUs proportional to memory operations in this step
                    # For unrolled loops, ensure we have enough AGUs for parallel access
                    if has_unrolled_loops and unroll_factor > 1:
                        step_agu_count = max(2, min(agu_count, mem_ops * min(2, unroll_factor // 2)))
                    else:
                        step_agu_count = max(1, min(agu_count, mem_ops))
                    
                    resources_per_step[step]["AGU_32bit"] = max(
                        resources_per_step[step]["AGU_32bit"], step_agu_count
                    )
        
        # Allocate FSM Controller based on control complexity
        fsm_count = 1  # Always need at least one FSM for basic control
        
        if has_loops or has_conditionals or control_complexity > 2:
            # Complex control flow needs more sophisticated FSM
            if control_complexity > 10:
                fsm_count = 2  # Very complex control may need hierarchical FSMs
            elif control_complexity > 5:
                fsm_count = 1  # Standard FSM with more states
        
        # Enhanced Memory Controller allocation with bandwidth analysis
        memory_controller_count = 0
        total_memory_size = 0
        memory_bandwidth_required = 0
        
        # Analyze memory access patterns and bandwidth requirements
        for var_name, var in func.local_vars.items():
            if var.data_type == "ARRAY":
                var_memory_size = var.bit_width * var.memory_size
                total_memory_size += var_memory_size
                
                # Estimate memory bandwidth based on access frequency
                access_frequency = 1  # Default: accessed once per loop iteration
                
                # Check if this variable is accessed in unrolled loops
                for block in func.blocks:
                    if (hasattr(block, 'unroll') and block.unroll and 
                        hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                        # Unrolled loops increase memory bandwidth requirements
                        access_frequency *= block.unroll_factor
                
                var_bandwidth = var.bit_width * access_frequency / 8  # bytes per cycle
                memory_bandwidth_required += var_bandwidth
                
                # Large arrays need dedicated memory controllers
                if var.memory_size > 1024:  # > 1KB
                    memory_controller_count += 1
                # High bandwidth arrays also need dedicated controllers
                elif var_bandwidth > 64:  # > 64 bytes/cycle
                    memory_controller_count += 1
        
        # Ensure adequate memory controllers based on bandwidth requirements
        # Each memory controller can handle ~128 bytes/cycle bandwidth
        # For unrolled loops, be more conservative (64 bytes/cycle per controller)
        has_unrolled_loops = any(
            hasattr(block, 'unroll') and block.unroll and 
            hasattr(block, 'unroll_factor') and block.unroll_factor > 1
            for block in func.blocks
        )
        
        if has_unrolled_loops:
            bandwidth_controllers = max(1, int(memory_bandwidth_required / 64))  # More controllers for unrolled
        else:
            bandwidth_controllers = max(1, int(memory_bandwidth_required / 128))  # Standard
        
        memory_controller_count = max(memory_controller_count, bandwidth_controllers)
        
        # Ensure at least one memory controller if we have significant memory usage
        if total_memory_size > 512 * 8:  # > 512 bytes
            memory_controller_count = max(memory_controller_count, 1)
        
        # Add FSM and Memory Controllers to the first control step (they're always active)
        if resources_per_step:
            first_step = min(resources_per_step.keys())
            
            if "FSM_Controller" not in resources_per_step[first_step]:
                resources_per_step[first_step]["FSM_Controller"] = 0
            resources_per_step[first_step]["FSM_Controller"] = max(
                resources_per_step[first_step]["FSM_Controller"], fsm_count
            )
            
            if memory_controller_count > 0:
                if "Memory_Controller" not in resources_per_step[first_step]:
                    resources_per_step[first_step]["Memory_Controller"] = 0
                resources_per_step[first_step]["Memory_Controller"] = max(
                    resources_per_step[first_step]["Memory_Controller"], memory_controller_count
                )
        
        return resources_per_step
    
    def _allocate_minimize_area(self, resources_per_step: Dict[int, Dict[str, int]]) -> Dict[str, int]:
        """
        Allocate resources to minimize area.
        
        Args:
            resources_per_step: Resource usage per control step
            
        Returns:
            Dictionary of {resource_type: count}
        """
        # Take the maximum usage of each resource type across all steps
        allocated = {}
        
        for step, resources in resources_per_step.items():
            for res_type, count in resources.items():
                if res_type not in allocated:
                    allocated[res_type] = 0
                
                # For area optimization, we use resource sharing
                allocated[res_type] = max(allocated[res_type], count)
        
        # Enhanced MUX allocation for unrolled loops and complex designs
        total_compute_resources = sum(
            allocated.get(res, 0) for res in [
                "ALU_32bit", "Adder_32bit", "Subtractor_32bit", "Multiplier_32bit", 
                "Divider_32bit", "BitOp_32bit", "Comparator_32bit", "RelationalOp_32bit", 
                "Shifter_32bit"
            ]
        )
        
        # Check for loop unrolling to adjust MUX allocation
        has_unrolled_loops = False
        max_unroll_factor = 1
        if hasattr(self, 'ir') and self.ir:
            for func_name, func in self.ir.functions.items():
                for block in func.blocks:
                    if (hasattr(block, 'unroll') and block.unroll and 
                        hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                        has_unrolled_loops = True
                        max_unroll_factor = max(max_unroll_factor, block.unroll_factor)
        
        # For area-optimized designs, we want fewer MUXes while still enabling resource sharing
        # But unrolled loops need more MUXes for parallel data routing
        if has_unrolled_loops and max_unroll_factor > 1:
            # Unrolled loops need more MUXes for parallel execution
            mux_scale_factor = min(3.0, 1.0 + (max_unroll_factor - 1) * 0.5)
            min_mux_count = max(4, int(total_compute_resources * mux_scale_factor))
        else:
            # Standard area-optimized MUX allocation
            min_mux_count = max(2, total_compute_resources // 2)
        
        if "MUX_32bit" not in allocated or allocated["MUX_32bit"] < min_mux_count:
            allocated["MUX_32bit"] = min_mux_count
        
        # Enhanced register allocation for unrolled loops and complex computation
        if total_compute_resources > 10 or has_unrolled_loops:  # Threshold suggesting unrolled loops or complex computation
            if has_unrolled_loops:
                # Unrolled loops need significantly more registers for parallel data flow
                min_registers = int(total_compute_resources * max_unroll_factor * 0.8)
            else:
                # Complex computation needs more registers for data flow
                min_registers = int(total_compute_resources * 1.5)
            
            if "Register_32bit" in allocated:
                allocated["Register_32bit"] = max(allocated["Register_32bit"], min_registers)
            else:
                allocated["Register_32bit"] = min_registers
        
        return allocated
    
    def _allocate_maximize_performance(self, resources_per_step: Dict[int, Dict[str, int]]) -> Dict[str, int]:
        """
        Allocate resources to maximize performance.
        
        Args:
            resources_per_step: Resource usage per control step
            
        Returns:
            Dictionary of {resource_type: count}
        """
        # For performance optimization, allocate more resources to enable parallel execution
        allocated = {}
        max_resources = {}
        
        # First pass: find the total resources needed across all steps
        for step, resources in resources_per_step.items():
            for res_type, count in resources.items():
                if res_type not in max_resources:
                    max_resources[res_type] = 0
                max_resources[res_type] = max(max_resources[res_type], count)
        
        # Initialize with the maximum per step
        allocated = max_resources.copy()
        
        # Identify computationally-intensive operations for potential scaling
        compute_ops = 0
        total_ops = 0
        computational_resources = ["ALU_32bit", "Multiplier_32bit", "Adder_32bit", "Subtractor_32bit", 
                                  "BitOp_32bit", "Divider_32bit", "Shifter_32bit"]
        
        for step, resources in resources_per_step.items():
            for res_type, count in resources.items():
                total_ops += count
                if res_type in computational_resources:
                    compute_ops += count
        
        # Calculate scaling based on computational intensity
        compute_scale = 1.0  # Default scaling factor
        if compute_ops > 0 and total_ops > 0:
            compute_ratio = compute_ops / total_ops
            if compute_ratio > 0.3:  # If more than 30% operations are compute
                # For unrolled loops, compute scale should be higher
                # Detect potential unrolled loops based on resource usage pattern
                unrolled_loop_pattern = False
                if any(count > 4 for res_type, count in max_resources.items() 
                      if res_type in computational_resources):
                    unrolled_loop_pattern = True
                
                if unrolled_loop_pattern:
                    # More aggressive scaling for unrolled computations
                    compute_scale = min(64.0, max(8.0, compute_ops / 5))
                else:
                    # Standard scaling for non-unrolled computations
                    compute_scale = min(32.0, max(4.0, compute_ops / 10))
        
        # Apply scaling to resources
        for res_type in allocated.keys():
            if res_type in computational_resources:
                # Scale computationally-intensive resources more aggressively
                if res_type == "Multiplier_32bit":
                    # Multiply-accumulate operations are common in matrix operations
                    # so ensure we have enough multipliers
                    # For unrolled loops, these are particularly critical
                    scale_factor = compute_scale * 1.5 if compute_scale > 8.0 else compute_scale
                    allocated[res_type] = max(
                        allocated[res_type],
                        int(max_resources.get(res_type, 1) * scale_factor)
                    )
                elif res_type == "ALU_32bit":
                    # ALUs handle many operations, so scale them up significantly
                    # For unrolled loops, we need even more ALUs
                    scale_factor = compute_scale * 2.5 if compute_scale > 8.0 else compute_scale * 2
                    allocated[res_type] = max(
                        allocated[res_type],
                        int(max_resources.get(res_type, 1) * scale_factor)
                    )
                else:
                    # Scale other compute resources
                    # For unrolled loops, increase scaling to support parallel execution
                    scale_factor = compute_scale * 1.5 if compute_scale > 8.0 else compute_scale
                    allocated[res_type] = max(
                        allocated[res_type],
                        int(max_resources.get(res_type, 1) * scale_factor)
                    )
        
        # Ensure minimum computational resources for matrix operations
        if "ALU_32bit" in allocated:
            # For unrolled loops, ensure even more ALUs
            min_alus = 16 if compute_scale > 8.0 else 8
            allocated["ALU_32bit"] = max(allocated["ALU_32bit"], min_alus)
        else:
            allocated["ALU_32bit"] = 16 if compute_scale > 8.0 else 8
        
        if "Multiplier_32bit" in allocated:
            # For unrolled loops with matrix operations, ensure more multipliers
            min_multipliers = 8 if compute_scale > 8.0 else 4
            allocated["Multiplier_32bit"] = max(allocated["Multiplier_32bit"], min_multipliers)
        else:
            allocated["Multiplier_32bit"] = 8 if compute_scale > 8.0 else 4
        
        # Enhanced MUX allocation for performance-optimized designs with unroll awareness
        # Calculate total compute resources for MUX scaling
        total_compute_resources = sum(
            allocated.get(res, 0) for res in computational_resources
        )
        
        # Check for actual loop unrolling in the IR
        has_unrolled_loops = False
        max_unroll_factor = 1
        total_unroll_factor = 1
        if hasattr(self, 'ir') and self.ir:
            for func_name, func in self.ir.functions.items():
                for block in func.blocks:
                    if (hasattr(block, 'unroll') and block.unroll and 
                        hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                        has_unrolled_loops = True
                        max_unroll_factor = max(max_unroll_factor, block.unroll_factor)
                        total_unroll_factor *= block.unroll_factor
        
        # Performance-optimized designs need more MUXes to feed parallel execution units
        # For unrolled loops, we need even more MUXes for complex data routing
        if has_unrolled_loops and max_unroll_factor > 1:
            # Sophisticated MUX calculation for unrolled loops
            base_mux_factor = 3.0  # Base factor for unrolled designs
            unroll_mux_factor = min(2.0, max_unroll_factor / 4.0)  # Additional factor based on unroll
            mux_multiplier = base_mux_factor + unroll_mux_factor
            mux_count = max(16, min(256, int(total_compute_resources * mux_multiplier)))
        elif compute_scale > 8.0:
            # High compute intensity without unrolling
            mux_count = max(8, min(128, int(total_compute_resources * 2.5)))
        else:
            # Standard performance optimization
            mux_count = max(4, min(64, total_compute_resources * 2))
        
        # Set the final MUX count
        allocated["MUX_32bit"] = mux_count
        
        # Enhanced register allocation for unrolled loops and high-performance designs
        if has_unrolled_loops and max_unroll_factor > 1:
            # Unrolled loops need extensive register files for parallel data management
            base_reg_factor = 4.0  # Base factor for unrolled designs
            unroll_reg_factor = min(3.0, max_unroll_factor / 2.0)  # Additional factor based on unroll
            reg_multiplier = base_reg_factor + unroll_reg_factor
            min_registers = int(total_compute_resources * reg_multiplier)
        elif compute_scale > 8.0:
            # High compute intensity needs more registers for pipeline stages
            min_registers = int(total_compute_resources * 3)
        else:
            # Standard performance optimization
            min_registers = int(total_compute_resources * 2)
        
        if "Register_32bit" in allocated:
            allocated["Register_32bit"] = max(allocated["Register_32bit"], min_registers)
        else:
            allocated["Register_32bit"] = min_registers
        
        return allocated
    
    def _allocate_minimize_power(self, resources_per_step: Dict[int, Dict[str, int]]) -> Dict[str, int]:
        """
        Allocate resources to minimize power.
        
        Args:
            resources_per_step: Resource usage per control step
            
        Returns:
            Dictionary of {resource_type: count}
        """
        # For power optimization, we might use more steps but fewer resources
        allocated = {}
        
        # First pass: allocate minimum resources
        for step, resources in resources_per_step.items():
            for res_type, count in resources.items():
                if res_type not in allocated:
                    allocated[res_type] = 0
                
                allocated[res_type] = max(allocated[res_type], count // 2 + count % 2)  # Use half resources
        
        # Ensure at least one of each type
        for step, resources in resources_per_step.items():
            for res_type in resources.keys():
                if allocated[res_type] == 0:
                    allocated[res_type] = 1
        
        # For power-optimized designs, allocate fewer MUXes to reduce switching activity
        # But ensure there are enough to handle resource sharing
        total_compute_resources = sum(
            allocated.get(res, 0) for res in [
                "ALU_32bit", "Adder_32bit", "Subtractor_32bit", "Multiplier_32bit", 
                "Divider_32bit", "BitOp_32bit", "Comparator_32bit", "RelationalOp_32bit", 
                "Shifter_32bit"
            ]
        )
        
        # For power-optimized designs, minimize MUX count while ensuring functionality
        mux_count = max(2, total_compute_resources // 2)
        
        # Set the final MUX count
        if "MUX_32bit" in allocated:
            allocated["MUX_32bit"] = max(allocated["MUX_32bit"], mux_count)
        else:
            allocated["MUX_32bit"] = mux_count
            
        return allocated
    
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
            "STORE": "Memory_1KB",  # Will be handled by Memory_Controller
            "LOAD": "Memory_1KB",   # Will be handled by Memory_Controller
            "ARRAY_ACCESS": "Memory_1KB",  # Array accesses need memory controllers
            "CALL": "ALU_32bit",
            # Add FIFO and Crossbar operation mappings
            "FIFO_WRITE": "FIFO_32bit",
            "FIFO_READ": "FIFO_32bit",
            "CROSSBAR_ROUTE": "CROSSBAR_32bit",
            # Add AXI-Stream operation mappings
            "AXIS_FIFO_WRITE": "FIFO_32bit",
            "AXIS_FIFO_READ": "FIFO_32bit",
            # Add AXI-Lite operation mappings
            "AXILITE_FIFO_WRITE": "FIFO_32bit",
            "AXILITE_FIFO_READ": "FIFO_32bit",
            # Control flow operations
            "BRANCH": "FSM_Controller",
            "JUMP": "FSM_Controller",
            "LOOP_START": "FSM_Controller",
            "LOOP_END": "FSM_Controller"
        }
        
        return op_to_resource.get(op.op_type.name, "ALU_32bit")
    
    def create_netlist_resources(self, allocated: Dict[str, int]) -> List[NetlistResource]:
        """
        Create netlist resources from allocation.
        
        Args:
            allocated: Allocated resources
            
        Returns:
            List of netlist resources
        """
        netlist_resources = []
        
        # Track which resources are ACTUALLY part of unrolled loops (not just guessing from count)
        potentially_unrolled = {}
        
        # Only mark resources as unrolled if there's actual evidence of unrolling in the IR
        if hasattr(self, 'ir') and self.ir:
            has_actual_unrolling = False
            for func_name, func in self.ir.functions.items():
                for block in func.blocks:
                    # Check if this block has explicit unrolling enabled
                    if (hasattr(block, 'unroll') and block.unroll and 
                        hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                        has_actual_unrolling = True
                        break
                if has_actual_unrolling:
                    break
            
            # Only apply unroll naming if there's actual unrolling in the IR
            if has_actual_unrolling:
                for res_type, count in allocated.items():
                    if any(rt in res_type for rt in ["ALU", "Adder", "Subtractor", "Multiplier", "Divider"]):
                        if count > 4:  # Threshold suggesting unrolled resources
                            potentially_unrolled[res_type] = True
        
        # Track total resources for power calculation
        self.resource_count = sum(allocated.values())
        self.memory_resources = 0
        self.compute_resources = 0
        
        for res_type, count in allocated.items():
            for i in range(count):
                # Get the resource model with the current tech node to ensure correct area scaling
                resource_model = self.tech_library.get_resource(res_type, self.tech_library.tech_node)
                
                # Determine memory attributes based on resource type
                memory_type = "none"
                memory_size = 1
                bit_width = 32  # Default
                
                # For potentially unrolled resources, create unique naming
                if res_type in potentially_unrolled:
                    unroll_instance = i % 4  # Assume groups of 4 for resource mapping
                    resource_name = f"{res_type}_{i}_unroll_{unroll_instance}"
                else:
                    resource_name = f"{res_type}_{i}"
                
                if "Scratchpad" in res_type:
                    memory_type = "scratchpad"
                    # Extract memory size from resource type name (e.g., Scratchpad_4KB -> 4KB)
                    if "_1KB" in res_type:
                        memory_size = 1024  # 1KB in bytes
                    elif "_4KB" in res_type:
                        memory_size = 4096  # 4KB in bytes
                    elif "_16KB" in res_type:
                        memory_size = 16384  # 16KB in bytes
                    elif "_64KB" in res_type:
                        memory_size = 65536  # 64KB in bytes
                    
                    # Scale area based on memory size
                    area_scale_factor = memory_size / 1024  # Scale relative to 1KB
                    area = resource_model.area * area_scale_factor
                    
                    # Track memory resource
                    self.memory_resources += 1
                    
                elif "Memory" in res_type:
                    memory_type = "sram"
                    if "_1KB" in res_type:
                        memory_size = 1024  # 1KB in bytes
                    elif "_4KB" in res_type:
                        memory_size = 4096  # 4KB in bytes
                    
                    # Scale area based on memory size
                    area_scale_factor = memory_size / 1024  # Scale relative to 1KB
                    area = resource_model.area * area_scale_factor
                    
                    # Track memory resource
                    self.memory_resources += 1
                    
                elif "Cache" in res_type:
                    memory_type = "cache"
                    if "_16KB" in res_type:
                        memory_size = 16384  # 16KB in bytes
                    
                    # Cache has higher area cost due to tag storage and control logic
                    area_scale_factor = memory_size / 1024 * 1.5  # 50% overhead for cache control
                    area = resource_model.area * area_scale_factor
                    
                    # Track memory resource
                    self.memory_resources += 1
                    
                else:
                    # For computational resources, use model's area directly
                    area = resource_model.area
                    
                    # Adjust bit width based on resource type
                    if "_64bit" in res_type:
                        bit_width = 64
                    elif "_16bit" in res_type:
                        bit_width = 16
                    elif "_8bit" in res_type:
                        bit_width = 8
                    
                    # Track compute resource
                    if any(rt in res_type for rt in ["ALU", "Adder", "Subtractor", "Multiplier", "Divider"]):
                        self.compute_resources += 1
                
                # For normal computational resources, area_scale_factor is 1.0 
                # For memory resources, we've already calculated a scale factor above
                area_scale_factor = 1.0
                if "Scratchpad" in res_type or "Memory" in res_type or "Cache" in res_type:
                    # For memory resources, derive scale factor from area calculation
                    if resource_model.area > 0:
                        area_scale_factor = area / resource_model.area
                
                # Calculate base resource power without additional components
                base_power = self._calculate_power(resource_model, area_scale_factor)
                
                netlist_resource = NetlistResource(
                    name=resource_name,
                    type=res_type,
                    bit_width=bit_width,
                    latency=resource_model.latency,
                    area=area,  # Use scaled area when appropriate
                    power=base_power,
                    technology_node=self.tech_library.tech_node,  # Explicitly use current tech node
                    supply_voltage=1.0,  # Default
                    memory_type=memory_type,
                    memory_size=memory_size
                )
                
                netlist_resources.append(netlist_resource)
        
        # Add handling for streaming components (FIFO, Crossbar)
        fifo_count = sum(1 for res_type in allocated.keys() if 'FIFO' in res_type)
        crossbar_count = sum(1 for res_type in allocated.keys() if 'CROSSBAR' in res_type)
        
        # Log the current resources for debugging
        logger.info(f"Creating netlist resources from {len(allocated)} resource types")
        logger.info(f"FIFO resources count: {fifo_count}")
        logger.info(f"Crossbar resources count: {crossbar_count}")
        
        # If no FIFO resources were allocated but we have streaming components in the IR,
        # extract them from the streaming_components attribute of the function
        if fifo_count == 0 and hasattr(self, 'ir') and self.ir:
            logger.info("No FIFO resources found in allocated resources, checking IR for streaming components")
            fifo_resources = {}
            
            # Look for streaming components in each function
            for func_name, func in self.ir.functions.items():
                if hasattr(func, 'streaming_components') and func.streaming_components:
                    logger.info(f"Found {len(func.streaming_components)} streaming components in function {func_name}")
                    
                    # Check each streaming component
                    for comp_name, comp in func.streaming_components.items():
                        if comp.component_type == 'fifo':
                            # Extract FIFO parameters
                            fifo_depth = comp.params.get('depth', 32)  # Default depth is 32
                            fifo_width = comp.params.get('width', 32)  # Default width is 32
                            
                            # Create a resource type name based on width
                            resource_type = f"FIFO_{fifo_width}bit"
                            
                            # Add to FIFO resources
                            if resource_type not in fifo_resources:
                                fifo_resources[resource_type] = 0
                            fifo_resources[resource_type] += 1
                            
                            # Add to allocated resources
                            if resource_type not in allocated:
                                allocated[resource_type] = 0
                            allocated[resource_type] += 1
                            
                            logger.info(f"Added FIFO resource {resource_type} from component {comp_name} with depth {fifo_depth}")
            
            # If we found FIFO resources from streaming components, log them
            if fifo_resources:
                logger.info(f"Added {sum(fifo_resources.values())} FIFO resources from streaming components")
                
                # Create netlist resources for each FIFO
                for res_type, count in fifo_resources.items():
                    for i in range(count):
                        # Get a base resource model (can use Register as template)
                        # since FIFOs are not directly in tech library
                        base_model = self.tech_library.get_resource("Register_32bit", self.tech_library.tech_node)
                        
                        # FIFO's area and power depend on depth and width
                        # For each FIFO component found earlier
                        fifo_depth = 32  # Default depth
                        fifo_width = 32  # Default width
                        
                        # Try to match with a component to get actual parameters
                        for func_name, func in self.ir.functions.items():
                            if hasattr(func, 'streaming_components'):
                                for comp_name, comp in func.streaming_components.items():
                                    if comp.component_type == 'fifo':
                                        fifo_depth = comp.params.get('depth', 32)
                                        fifo_width = comp.params.get('width', 32)
                                        break
                        
                        # Scale area based on depth and width
                        # FIFO area is roughly proportional to depth * width
                        area_scale_factor = (fifo_depth / 16) * (fifo_width / 32)
                        area = base_model.area * area_scale_factor * 2  # FIFOs are more complex than registers
                        
                        # Create the FIFO resource
                        netlist_resource = NetlistResource(
                            name=f"{res_type}_{i}",
                            type=res_type,
                            bit_width=fifo_width,
                            latency=1,  # FIFO read/write typically takes 1 cycle
                            area=area,
                            power=self._calculate_power(base_model, area_scale_factor),
                            technology_node=self.tech_library.tech_node,
                            supply_voltage=1.0,
                            memory_type="fifo",
                            memory_size=fifo_depth
                        )
                        
                        netlist_resources.append(netlist_resource)
                        logger.info(f"Created FIFO netlist resource: {netlist_resource.name}")
        
        # Handle crossbar resources similarly to FIFOs
        if crossbar_count == 0 and hasattr(self, 'ir') and self.ir:
            logger.info("No crossbar resources found in allocated resources, checking IR for streaming components")
            crossbar_resources = {}
            
            # Look for streaming components in each function
            for func_name, func in self.ir.functions.items():
                if hasattr(func, 'streaming_components') and func.streaming_components:
                    # Check each streaming component
                    for comp_name, comp in func.streaming_components.items():
                        if comp.component_type == 'crossbar':
                            # Extract crossbar parameters
                            inputs = comp.params.get('inputs', 4)  # Default 4 inputs
                            outputs = comp.params.get('outputs', 4)  # Default 4 outputs
                            width = comp.params.get('width', 32)  # Default width is 32
                            
                            # Create a resource type name based on width
                            resource_type = f"CROSSBAR_{width}bit"
                            
                            # Add to crossbar resources
                            if resource_type not in crossbar_resources:
                                crossbar_resources[resource_type] = 0
                            crossbar_resources[resource_type] += 1
                            
                            # Add to allocated resources
                            if resource_type not in allocated:
                                allocated[resource_type] = 0
                            allocated[resource_type] += 1
                            
                            logger.info(f"Added crossbar resource {resource_type} from component {comp_name} with {inputs}x{outputs} configuration")
            
            # If we found crossbar resources from streaming components, log them
            if crossbar_resources:
                logger.info(f"Added {sum(crossbar_resources.values())} crossbar resources from streaming components")
                
                # Create netlist resources for each crossbar
                for res_type, count in crossbar_resources.items():
                    for i in range(count):
                        try:
                            # Try to get the crossbar model from the tech library
                            crossbar_model = self.tech_library.get_resource(res_type, self.tech_library.tech_node)
                            base_model = crossbar_model
                        except ValueError:
                            # Fallback to using ALU as base if crossbar model not found
                            base_model = self.tech_library.get_resource("ALU_32bit", self.tech_library.tech_node)
                            logger.warning(f"Crossbar model {res_type} not found in tech library, using ALU_32bit as base")
                        
                        # Crossbar's area and power depend on inputs, outputs, and width
                        # For each crossbar component found earlier
                        inputs = 4  # Default inputs
                        outputs = 4  # Default outputs
                        width = 32  # Default width
                        
                        # Try to match with a component to get actual parameters
                        for func_name, func in self.ir.functions.items():
                            if hasattr(func, 'streaming_components'):
                                for comp_name, comp in func.streaming_components.items():
                                    if comp.component_type == 'crossbar':
                                        inputs = comp.params.get('inputs', 4)
                                        outputs = comp.params.get('outputs', 4)
                                        width = comp.params.get('width', 32)
                                        break
                        
                        # Scale area based on inputs, outputs, and width
                        # Crossbar area is roughly proportional to inputs * outputs * width
                        area_scale_factor = (inputs * outputs) / 16 * (width / 32)
                        area = base_model.area * area_scale_factor
                        
                        # Create the crossbar resource
                        netlist_resource = NetlistResource(
                            name=f"{res_type}_{i}",
                            type=res_type,
                            bit_width=width,
                            latency=1,  # Crossbar routing typically takes 1 cycle
                            area=area,
                            power=self._calculate_power(base_model, area_scale_factor),
                            technology_node=self.tech_library.tech_node,
                            supply_voltage=1.0,
                            memory_type="crossbar",
                            memory_size=inputs * outputs  # Use memory_size to store connection count
                        )
                        
                        netlist_resources.append(netlist_resource)
                        logger.info(f"Created crossbar netlist resource: {netlist_resource.name}")
        
        return netlist_resources
    
    def _calculate_power(self, resource_model: ResourceModel, area_scale_factor: float = 1.0) -> float:
        """
        Calculate power consumption for a resource using the critical path frequency when available.
        
        Args:
            resource_model: Resource model with energy and frequency data
            area_scale_factor: Scaling factor for area that also affects dynamic power (default: 1.0)
            
        Returns:
            Power in mW
        """
        # Try to use the IR's target frequency if available
        operating_frequency = resource_model.frequency  # Default to resource model frequency
        
        if hasattr(self, 'ir') and self.ir and hasattr(self.ir, 'target_frequency_mhz') and self.ir.target_frequency_mhz > 0:
            # Use the target frequency from the IR for dynamic power calculation
            operating_frequency = self.ir.target_frequency_mhz
            logger.debug(f"Using IR target frequency: {operating_frequency} MHz instead of resource frequency: {resource_model.frequency} MHz")
        else:
            logger.debug(f"Using resource model frequency: {operating_frequency} MHz (no IR target frequency available)")
        
        # Calculate dynamic power using operating frequency and add leakage power
        # Dynamic power scales with area factor (for memory/interconnect resources)
        # Power (mW) = Dynamic power + Leakage power
        # Dynamic power (mW) = Energy per operation (pJ) * Frequency (MHz) / 1000 * area_scale_factor
        # Leakage power (mW) = Leakage power (µW) / 1000 * area_scale_factor
        dynamic_power = resource_model.energy_per_op * operating_frequency / 1000 * area_scale_factor
        leakage_power = resource_model.leakage_power / 1000 * area_scale_factor
        total_power = dynamic_power + leakage_power
        
        logger.debug(f"Resource power calculation: dynamic={dynamic_power:.3f}mW + leakage={leakage_power:.3f}mW = {total_power:.3f}mW (area_scale={area_scale_factor:.2f})")
        
        return total_power
    
    def calculate_total_power(self, netlist_resources: List[NetlistResource]) -> float:
        """
        Calculate the total power consumption of the design including clock tree, PDN,
        interconnect, and control logic power.
        
        Args:
            netlist_resources: List of netlist resources
            
        Returns:
            Total power consumption in mW
        """
        # Calculate base power from all resources
        base_power = sum(resource.power for resource in netlist_resources)
        
        # Get design statistics for more accurate power modeling
        resource_count = len(netlist_resources)
        compute_resources = 0
        memory_resources = 0
        
        for resource in netlist_resources:
            if resource.memory_type != "none":
                memory_resources += 1
            elif any(rt in resource.type for rt in ["ALU", "Adder", "Subtractor", "Multiplier", "Divider"]):
                compute_resources += 1
        
        # Calculate clock tree power (scales with design size and operating frequency)
        # Clock tree can be 15-30% of dynamic power
        cts_factor = 0.15 + (0.15 * min(1.0, resource_count / 50))  # Scale up to 30% for larger designs
        cts_power = base_power * cts_factor
        
        # Power Distribution Network (PDN) losses
        # Typically 5-10% overhead, increasing with design complexity
        pdn_factor = 0.05 + (0.05 * min(1.0, resource_count / 100))
        pdn_power = base_power * pdn_factor
        
        # Interconnect power (wires, buffers, etc.)
        # Scales with design complexity and can be 20-40% of dynamic power
        if compute_resources > 0:
            # More complex designs with higher compute-to-memory ratio need more interconnect
            compute_memory_ratio = compute_resources / max(1, memory_resources)
            interconnect_factor = 0.2 + min(0.2, (0.1 * compute_memory_ratio) + (0.1 * resource_count / 50))
        else:
            interconnect_factor = 0.2  # Default 20% for simple designs
        
        interconnect_power = base_power * interconnect_factor
        
        # Control logic power (state machines, decoders, etc.)
        # Typically 10-15% of total power
        control_factor = 0.1 + (0.05 * min(1.0, compute_resources / 20))
        control_power = base_power * control_factor
        
        # Sum all power components
        total_power = base_power + cts_power + pdn_power + interconnect_power + control_power
        
        # Log the power breakdown
        logger.info(f"Power breakdown:")
        logger.info(f"  Base resource power: {base_power:.2f} mW ({(base_power/total_power*100):.1f}%)")
        logger.info(f"  Clock tree power: {cts_power:.2f} mW ({(cts_power/total_power*100):.1f}%)")
        logger.info(f"  PDN power: {pdn_power:.2f} mW ({(pdn_power/total_power*100):.1f}%)")
        logger.info(f"  Interconnect power: {interconnect_power:.2f} mW ({(interconnect_power/total_power*100):.1f}%)")
        logger.info(f"  Control logic power: {control_power:.2f} mW ({(control_power/total_power*100):.1f}%)")
        logger.info(f"  Total power: {total_power:.2f} mW")
        
        return total_power
    
    def _update_execution_time_for_reduced_resources(self, func: IRFunction, 
                                                   original_resources_per_step: Dict[int, Dict[str, int]], 
                                                   allocated_resources: Dict[str, int]) -> None:
        """
        Update execution time when resources are reduced due to power optimization.
        
        Args:
            func: Function to update
            original_resources_per_step: Original resource requirements per control step
            allocated_resources: Actually allocated resources (potentially reduced)
        """
        if not original_resources_per_step:
            return
        
        # Calculate the resource reduction factor for each resource type
        resource_reduction_factors = {}
        
        for step, step_resources in original_resources_per_step.items():
            for res_type, required_count in step_resources.items():
                if res_type in allocated_resources:
                    allocated_count = allocated_resources[res_type]
                    if allocated_count > 0 and required_count > allocated_count:
                        # Calculate how much longer operations will take due to resource constraints
                        reduction_factor = required_count / allocated_count
                        if res_type not in resource_reduction_factors:
                            resource_reduction_factors[res_type] = reduction_factor
                        else:
                            # Take the maximum reduction factor across all steps
                            resource_reduction_factors[res_type] = max(
                                resource_reduction_factors[res_type], reduction_factor
                            )
        
        if not resource_reduction_factors:
            return  # No resource constraints detected
        
        # Calculate the overall execution time increase
        # Use the maximum reduction factor as it represents the bottleneck
        max_reduction_factor = max(resource_reduction_factors.values())
        
        # Update the function's latency estimates
        if hasattr(func, 'single_iter_latency') and func.single_iter_latency > 0:
            original_single_iter = func.single_iter_latency
            func.single_iter_latency = int(func.single_iter_latency * max_reduction_factor)
            logger.info(f"Power optimization: Updated single iteration latency from {original_single_iter} to {func.single_iter_latency} cycles "
                       f"(reduction factor: {max_reduction_factor:.2f})")
        
        if hasattr(func, 'total_latency') and func.total_latency > 0:
            original_total = func.total_latency
            func.total_latency = int(func.total_latency * max_reduction_factor)
            logger.info(f"Power optimization: Updated total latency from {original_total} to {func.total_latency} cycles "
                       f"(reduction factor: {max_reduction_factor:.2f})")
        
        # Also update the max control step if it exists
        if hasattr(func, 'max_control_step') and func.max_control_step > 0:
            original_max_step = func.max_control_step
            func.max_control_step = int(func.max_control_step * max_reduction_factor)
            logger.info(f"Power optimization: Updated max control step from {original_max_step} to {func.max_control_step}")
        
        # Log the resource reduction details
        logger.info(f"Resource reduction factors for power optimization:")
        for res_type, factor in resource_reduction_factors.items():
            logger.info(f"  {res_type}: {factor:.2f}x longer execution due to resource constraints")
    
    def _update_execution_time_for_resource_sharing(self, func: IRFunction, 
                                                  original_resources_per_step: Dict[int, Dict[str, int]], 
                                                  allocated_resources: Dict[str, int]) -> None:
        """
        Update execution time when resource sharing is used in area optimization.
        
        Args:
            func: Function to update
            original_resources_per_step: Original resource requirements per control step
            allocated_resources: Actually allocated resources (using resource sharing)
        """
        if not original_resources_per_step:
            return
        
        # Calculate the total resource demand across all steps
        total_resource_demand = {}
        max_concurrent_demand = {}
        
        for step, step_resources in original_resources_per_step.items():
            for res_type, required_count in step_resources.items():
                # Track total demand across all steps
                if res_type not in total_resource_demand:
                    total_resource_demand[res_type] = 0
                total_resource_demand[res_type] += required_count
                
                # Track maximum concurrent demand (what we actually allocated)
                if res_type not in max_concurrent_demand:
                    max_concurrent_demand[res_type] = 0
                max_concurrent_demand[res_type] = max(max_concurrent_demand[res_type], required_count)
        
        # Calculate resource sharing factors
        sharing_factors = {}
        for res_type in total_resource_demand:
            if res_type in allocated_resources and allocated_resources[res_type] > 0:
                # The sharing factor is the ratio of total demand to allocated resources
                # This represents how much serialization is needed
                total_demand = total_resource_demand[res_type]
                allocated_count = allocated_resources[res_type]
                
                # Only consider significant resource sharing (more than 20% serialization)
                if total_demand > allocated_count * 1.2:
                    sharing_factor = total_demand / (allocated_count * len(original_resources_per_step))
                    if sharing_factor > 1.1:  # Only update if there's meaningful sharing
                        sharing_factors[res_type] = sharing_factor
        
        if not sharing_factors:
            return  # No significant resource sharing detected
        
        # Calculate the overall execution time increase due to resource sharing
        # Use a weighted average of sharing factors, weighted by resource importance
        weighted_sharing_factor = 0.0
        total_weight = 0.0
        
        for res_type, factor in sharing_factors.items():
            # Weight computational resources more heavily
            if any(rt in res_type for rt in ["ALU", "Multiplier", "Divider"]):
                weight = 3.0  # High weight for critical compute resources
            elif any(rt in res_type for rt in ["Adder", "Subtractor", "Shifter", "BitOp"]):
                weight = 2.0  # Medium weight for other compute resources
            else:
                weight = 1.0  # Lower weight for other resources
            
            weighted_sharing_factor += factor * weight
            total_weight += weight
        
        if total_weight > 0:
            avg_sharing_factor = weighted_sharing_factor / total_weight
            
            # Apply a more conservative scaling for resource sharing (less aggressive than power reduction)
            # Resource sharing typically has less impact than complete resource reduction
            conservative_factor = 1.0 + (avg_sharing_factor - 1.0) * 0.3  # 30% of the calculated impact
            
            # Update the function's latency estimates
            if hasattr(func, 'single_iter_latency') and func.single_iter_latency > 0:
                original_single_iter = func.single_iter_latency
                func.single_iter_latency = int(func.single_iter_latency * conservative_factor)
                if func.single_iter_latency != original_single_iter:
                    logger.info(f"Area optimization: Updated single iteration latency from {original_single_iter} to {func.single_iter_latency} cycles "
                               f"due to resource sharing (factor: {conservative_factor:.2f})")
            
            if hasattr(func, 'total_latency') and func.total_latency > 0:
                original_total = func.total_latency
                func.total_latency = int(func.total_latency * conservative_factor)
                if func.total_latency != original_total:
                    logger.info(f"Area optimization: Updated total latency from {original_total} to {func.total_latency} cycles "
                               f"due to resource sharing (factor: {conservative_factor:.2f})")
            
            # Log the resource sharing details
            logger.info(f"Resource sharing factors for area optimization:")
            for res_type, factor in sharing_factors.items():
                logger.info(f"  {res_type}: {factor:.2f}x sharing factor") 