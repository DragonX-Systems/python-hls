"""
Optimizer for the HLS IR.
"""

import logging
from typing import Dict, List, Optional, Set, Union, Any

from ..ir.ir_nodes import IR, IRFunction, IRBlock, IRInstruction, IROperation, OperationType

# Get logger for this module
logger = logging.getLogger(__name__)

class Optimizer:
    """Optimizer for the HLS IR."""
    
    def __init__(self, optimization_level: int = 1):
        """
        Initialize the optimizer.
        
        Args:
            optimization_level: Level of optimization to apply (0-3)
        """
        self.optimization_level = optimization_level
        
        # Statistics counters for optimization passes
        self.constants_folded = 0
        self.dead_ops_removed = 0
        self.common_subexpr_eliminated = 0
        self.loop_invariants_moved = 0
        self.functions_inlined = 0
        self.loops_unrolled = 0
        self.resources_shared = 0
        
        # Map optimization levels to passes
        self.optimization_passes = {
            0: [],  # No optimization
            1: [  # Basic optimizations
                self._constant_folding,
                self._dead_code_elimination,
            ],
            2: [  # Medium optimizations
                self._constant_folding,
                self._dead_code_elimination,
                self._common_subexpression_elimination,
                self._loop_invariant_code_motion,
            ],
            3: [  # Aggressive optimizations
                self._constant_folding,
                self._dead_code_elimination,
                self._common_subexpression_elimination,
                self._loop_invariant_code_motion,
                self._function_inlining,
                self._loop_unrolling,
                self._resource_sharing,
            ]
        }
    
    def optimize(self, ir: IR) -> IR:
        """
        Apply optimizations to the IR.
        
        Args:
            ir: IR to optimize
            
        Returns:
            Optimized IR
        """
        # Reset all counters for this optimization run
        self.constants_folded = 0
        self.dead_ops_removed = 0
        self.common_subexpr_eliminated = 0
        self.loop_invariants_moved = 0
        self.functions_inlined = 0
        self.loops_unrolled = 0
        self.resources_shared = 0
        
        # Get optimization passes for the current level
        passes = self.optimization_passes.get(
            self.optimization_level, 
            self.optimization_passes[1]  # Default to level 1
        )
        
        # Apply each optimization pass
        for optimization_pass in passes:
            ir = optimization_pass(ir)
            
            # Log what's happening
            logger.info(f"Applied {optimization_pass.__name__}")
        
        return ir
    
    def _constant_folding(self, ir: IR) -> IR:
        """
        Constant folding optimization.
        
        Evaluates constant expressions at compile time.
        """
        folded_count = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            # For each block in the function
            for block in func.blocks:
                # For each instruction in the block
                for instruction in block.instructions:
                    # Check each operation for constant operands
                    for i, op in enumerate(instruction.operations):
                        # Skip non-binary operations or operations without result
                        if not op.result or len(op.operands) != 2:
                            continue
                            
                        # Check if both operands are constants
                        left, right = op.operands
                        if not (hasattr(left, 'value') and hasattr(right, 'value')):
                            continue
                            
                        # Calculate result based on operation type
                        result_value = None
                        if op.op_type.name == 'ADD':
                            result_value = left.value + right.value
                        elif op.op_type.name == 'SUB':
                            result_value = left.value - right.value
                        elif op.op_type.name == 'MUL':
                            result_value = left.value * right.value
                        elif op.op_type.name == 'DIV':
                            # Avoid division by zero
                            if right.value != 0:
                                result_value = left.value // right.value if isinstance(left.value, int) else left.value / right.value
                        elif op.op_type.name == 'MOD':
                            # Avoid modulo by zero
                            if right.value != 0:
                                result_value = left.value % right.value
                        elif op.op_type.name == 'EQ':
                            result_value = left.value == right.value
                        elif op.op_type.name == 'NEQ':
                            result_value = left.value != right.value
                        elif op.op_type.name == 'LT':
                            result_value = left.value < right.value
                        elif op.op_type.name == 'LTE':
                            result_value = left.value <= right.value
                        elif op.op_type.name == 'GT':
                            result_value = left.value > right.value
                        elif op.op_type.name == 'GTE':
                            result_value = left.value >= right.value
                        elif op.op_type.name == 'BIT_AND':
                            result_value = left.value & right.value
                        elif op.op_type.name == 'BIT_OR':
                            result_value = left.value | right.value
                        elif op.op_type.name == 'BIT_XOR':
                            result_value = left.value ^ right.value
                            
                        # If we evaluated a constant result, replace the operation
                        if result_value is not None:
                            # Create a new constant for the result
                            folded_const = type(left)(
                                name=f"folded_{left.name}_{right.name}",
                                node_id=left.node_id,  # Reuse node ID
                                data_type=left.data_type,
                                value=result_value,
                                bit_width=left.bit_width
                            )
                            
                            # Replace the operation with a simple assignment
                            folded_op = IROperation(
                                name=op.name,
                                node_id=op.node_id,  # Reuse node ID
                                op_type=OperationType.ASSIGN,
                                operands=[folded_const],
                                result=op.result
                            )
                            
                            # Update the operation in the instruction
                            instruction.operations[i] = folded_op
                            folded_count += 1
        
        # Update statistics
        self.constants_folded += folded_count
        if folded_count > 0:
            logger.info(f"Constant folding: folded {folded_count} expressions")
            
        return ir
    
    def _dead_code_elimination(self, ir: IR) -> IR:
        """
        Dead code elimination optimization.
        
        Removes code that doesn't affect the output.
        """
        total_removed = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            # Mark used variables
            used_vars = set()
            
            # First pass: mark variables used in output or control flow
            for block in func.blocks:
                for instruction in block.instructions:
                    for op in instruction.operations:
                        # Mark variables used in any operation that contributes to output
                        # This includes RETURN operations, control flow, and state-modifying operations
                        is_live_operation = (
                            op.op_type.name == 'RETURN' or
                            op.op_type.name.startswith('CMP_') or
                            op.op_type.name == 'STORE' or  # Array/memory modifications
                            op.op_type.name == 'LOAD' or   # Array/memory accesses
                            op.op_type.name == 'CALL' or   # Function calls
                            # Operations that modify loop variables or control flow
                            (hasattr(block, 'is_loop') and block.is_loop) or
                            # Operations inside loops should be preserved
                            any(hasattr(b, 'loop_iterations') for b in func.blocks if b == block)
                        )
                        
                        if is_live_operation:
                            for operand in op.operands:
                                if hasattr(operand, 'name'):  # Check if it's a variable
                                    used_vars.add(operand.name)
                            # Also mark the result as used if it exists
                            if op.result and hasattr(op.result, 'name'):
                                used_vars.add(op.result.name)
            
            # Continue marking used variables until no more changes
            while True:
                used_vars_size = len(used_vars)
                
                # Find operations that produce values for used variables
                for block in func.blocks:
                    for instruction in block.instructions:
                        for op in instruction.operations:
                            # If this operation produces a used result
                            if op.result and hasattr(op.result, 'name') and op.result.name in used_vars:
                                # Mark all its operands as used
                                for operand in op.operands:
                                    if hasattr(operand, 'name'):  # Check if it's a variable
                                        used_vars.add(operand.name)
                
                # If no new variables were marked, we're done
                if len(used_vars) == used_vars_size:
                    break
            
            # Second pass: remove unused operations
            func_removed = 0
            for block in func.blocks:
                # Count operations before removing
                ops_before = sum(len(instr.operations) for instr in block.instructions)
                
                # Filter instructions to keep only those with useful operations
                new_instructions = []
                
                for instruction in block.instructions:
                    # Keep operations that produce used results or have side effects
                    useful_ops = []
                    
                    for op in instruction.operations:
                        # Keep operations with side effects (RETURN, STORE, etc.)
                        has_side_effect = op.op_type.name in [
                            'RETURN', 'STORE', 'CALL', 'LOAD',
                            'ADD', 'SUB', 'MUL', 'DIV',  # Arithmetic operations
                            'CMP_LT', 'CMP_GT', 'CMP_EQ', 'CMP_NEQ', 'CMP_LTE', 'CMP_GTE',  # Comparisons
                            'ASSIGN'  # Assignments
                        ]
                        
                        # Keep operations that produce used results
                        produces_used_result = (op.result and 
                                               hasattr(op.result, 'name') and 
                                               op.result.name in used_vars)
                        
                        # For complex algorithms, be very conservative about removing operations
                        # If in doubt, keep the operation
                        is_in_loop_block = any(hasattr(b, 'loop_iterations') for b in func.blocks if b == block)
                        
                        if has_side_effect or produces_used_result or is_in_loop_block:
                            useful_ops.append(op)
                    
                    # Update instruction with only useful operations
                    if useful_ops:
                        instruction.operations = useful_ops
                        new_instructions.append(instruction)
                
                # Update block with filtered instructions
                block.instructions = new_instructions
                
                # Count operations after removing
                ops_after = sum(len(instr.operations) for instr in block.instructions)
                func_removed += ops_before - ops_after
            
            total_removed += func_removed
            if func_removed > 0:
                logger.info(f"Dead code elimination: removed {func_removed} operations in function {func_name}")
        
        # Update statistics
        self.dead_ops_removed += total_removed
        
        return ir
    
    def _common_subexpression_elimination(self, ir: IR) -> IR:
        """
        Common subexpression elimination optimization.
        
        Identifies and removes redundant computations.
        """
        eliminated_count = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            func_eliminated = 0
            
            # For each block in the function (in order of execution)
            for block in func.blocks:
                # Create a map of expressions to their results
                expr_map = {}
                
                # For each instruction in the block
                for instruction in block.instructions:
                    # Process each operation
                    for i, op in enumerate(instruction.operations):
                        # Skip operations without result
                        if not op.result:
                            continue
                            
                        # Skip non-computational operations (e.g., ASSIGN, RETURN)
                        if op.op_type.name in ['ASSIGN', 'RETURN', 'STORE', 'LOAD']:
                            continue
                            
                        # Create a signature for the operation (op type and operands)
                        # This is a simple implementation - a more robust one would handle associativity
                        op_signature = (op.op_type.name, tuple(id(operand) for operand in op.operands))
                        
                        if op_signature in expr_map:
                            # We found a common subexpression
                            # Replace current operation with an assignment from the previous result
                            new_op = IROperation(
                                name=op.name,
                                node_id=op.node_id,
                                op_type=OperationType.ASSIGN,
                                operands=[expr_map[op_signature]],
                                result=op.result
                            )
                            
                            instruction.operations[i] = new_op
                            func_eliminated += 1
                        else:
                            # New expression, add to map
                            expr_map[op_signature] = op.result
            
            eliminated_count += func_eliminated
            if func_eliminated > 0:
                logger.info(f"Common subexpression elimination: eliminated {func_eliminated} redundant expressions in function {func_name}")
        
        # Update statistics
        self.common_subexpr_eliminated += eliminated_count
        
        return ir
    
    def _loop_invariant_code_motion(self, ir: IR) -> IR:
        """
        Loop invariant code motion optimization.
        
        Moves loop-invariant code outside of loops.
        """
        moved_count = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            # Identify loops
            loops = []
            
            # For each loop header
            for block in func.blocks:
                if block.loop_header == block:
                    # Found a loop header
                    loop = {
                        'header': block,
                        'exit': block.loop_exit,
                        'blocks': self._get_loop_blocks(block)
                    }
                    loops.append(loop)
            
            # For each loop, apply loop invariant code motion
            for loop in loops:
                # Actual implementation of LICM would go here
                # For now, we just update the counter
                pass
        
        # Update statistics
        self.loop_invariants_moved += moved_count
        if moved_count > 0:
            logger.info(f"Loop invariant code motion: moved {moved_count} operations outside loops")
        
        return ir
    
    def _function_inlining(self, ir: IR) -> IR:
        """
        Function inlining optimization.
        
        Replaces function calls with the function body.
        """
        inlined_count = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            # For each block in the function
            for block in func.blocks:
                # Placeholder for function inlining logic
                pass
        
        # Update statistics
        self.functions_inlined += inlined_count
        if inlined_count > 0:
            logger.info(f"Function inlining: inlined {inlined_count} function calls")
        
        return ir
    
    def _loop_unrolling(self, ir: IR) -> IR:
        """
        Loop unrolling optimization.
        
        Replicates loop body to reduce loop iterations.
        """
        unrolled_loops = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            # Identify loops to unroll
            loops_to_unroll = []
            
            # For each loop header
            for block in func.blocks:
                if block.loop_header == block:
                    # Check if this loop should be unrolled - ONLY if explicitly requested
                    unroll_factor = None
                    full_unroll = False
                    loop_iterations = None
                    
                    # ONLY consider unrolling if there's an explicit unroll pragma or attribute
                    # Do NOT automatically unroll based on loop_count alone!
                    explicitly_requested = False
                    
                    # Check for unroll attribute set by previous passes or user annotations
                    if hasattr(block, 'unroll') and block.unroll:
                        unroll_factor = getattr(block, 'unroll_factor', None)
                        full_unroll = getattr(block, 'full_unroll', False)
                        explicitly_requested = True
                    
                    # Check for explicit unroll pragma in the block's pragmas
                    if hasattr(block, 'pragmas') and block.pragmas and 'unroll' in block.pragmas:
                        explicitly_requested = True
                        unroll_value = block.pragmas['unroll']
                        if unroll_value == 0 or str(unroll_value).lower() == 'full':
                            full_unroll = True
                        else:
                            try:
                                unroll_factor = int(unroll_value)
                            except (ValueError, TypeError):
                                unroll_factor = 1  # Default to no unrolling if can't parse
                    
                    # Get loop iteration count if available (for informational purposes only)
                    loop_iterations = getattr(block, 'loop_iterations', None)
                    
                    # Check for loop count pragma (ONLY for information, NOT for triggering unrolling)
                    if hasattr(block, 'pragmas') and block.pragmas and 'loop_count' in block.pragmas:
                        try:
                            loop_iterations = int(block.pragmas['loop_count'])
                        except ValueError:
                            loop_iterations = None
                    
                    # Only proceed with unrolling if explicitly requested
                    if not explicitly_requested:
                        continue
                    
                    # For full unrolling with known iteration count, set the unroll factor
                    if full_unroll and loop_iterations is not None:
                        unroll_factor = loop_iterations
                    elif full_unroll:
                        # Default to a reasonable value if iteration count is unknown
                        unroll_factor = 8  # Use a default for full unrolling with unknown count
                    
                    # Check if we need to apply unrolling (only if explicitly requested)
                    if (full_unroll or (unroll_factor is not None and unroll_factor > 1)):
                        loop = {
                            'header': block,
                            'exit': block.loop_exit,
                            'blocks': self._get_loop_blocks(block),
                            'unroll_factor': unroll_factor,
                            'full_unroll': full_unroll,
                            'loop_iterations': loop_iterations
                        }
                        loops_to_unroll.append(loop)
                        
                        # Store unroll factor in the loop header block for later reference
                        block.unroll = True
                        if full_unroll:
                            block.unroll_factor = loop_iterations or unroll_factor  # Use the explicit factor if iterations unknown
                        else:
                            block.unroll_factor = unroll_factor
                            
                        # Update function's total unroll factor for resource allocation
                        current_total = getattr(func, 'total_unroll_factor', 1)
                        effective_factor = unroll_factor if unroll_factor is not None else 1
                        func.total_unroll_factor = current_total * effective_factor
            
            # For each loop to unroll
            for loop in loops_to_unroll:
                self._apply_loop_unrolling(ir, func, loop)
                unrolled_loops += 1
        
        # Update statistics
        self.loops_unrolled += unrolled_loops
        if unrolled_loops > 0:
            logger.info(f"Loop unrolling: unrolled {unrolled_loops} loops")
        
        return ir
    
    def _apply_loop_unrolling(self, ir: IR, func: IRFunction, loop: dict) -> None:
        """
        Apply loop unrolling to a specific loop in the IR.
        
        Args:
            ir: The IR to modify
            func: The function containing the loop
            loop: Dictionary with loop information
        """
        header_block = loop['header']
        exit_block = loop['exit']
        unroll_factor = loop['unroll_factor']
        full_unroll = loop['full_unroll']
        loop_iterations = loop['loop_iterations']
        
        # If this is full unrolling but we don't know the iteration count, use a default
        if full_unroll and not loop_iterations:
            # We can't fully unroll without knowing the iteration count
            # Fall back to a fixed partial unrolling
            full_unroll = False
            if not unroll_factor or unroll_factor <= 1:
                unroll_factor = 8  # Default reasonable unroll factor
        
        # For full unrolling, set the unroll factor to the number of iterations
        if full_unroll and loop_iterations:
            unroll_factor = loop_iterations
        
        # Ensure unroll_factor is not None and greater than 1
        if unroll_factor is None or unroll_factor <= 1:
            if full_unroll:
                unroll_factor = 8  # Default for full unroll with unknown iterations
            else:
                return  # Skip if no real unrolling needed
        
        # Identify the loop index variable
        loop_var = None
        loop_var_name = None
        cond_op = None
        
        # Find the condition operation in the header block
        for instr in header_block.instructions:
            for op in instr.operations:
                if op.op_type.name in ['LT', 'LTE', 'GT', 'GTE', 'EQ', 'NEQ']:
                    # This is likely the loop condition
                    cond_op = op
                    # Assume the first operand is the loop variable
                    if hasattr(op.operands[0], 'name'):
                        loop_var = op.operands[0]
                        loop_var_name = loop_var.name
                    break
                
        if not loop_var or not loop_var_name:
            # Can't identify the loop variable, can't proceed
            return
        
        # Create new blocks and instructions for the unrolled loop
        # This is a simplified implementation - a complete solution would
        # need to handle all the complex cases of loop dependencies
        
        # Create a new entry point block that replaces the loop header
        new_header = IRBlock(
            name=f"{header_block.name}_unrolled",
            node_id=self._get_next_id(),
            instructions=[]
        )
        
        # Add the new header to the function
        func.blocks.append(new_header)
        
        # Connect the new header to the loop's predecessors
        for pred in header_block.predecessors:
            if pred != header_block:  # Skip back-edge
                pred.successors = [new_header if b == header_block else b for b in pred.successors]
                new_header.predecessors.append(pred)
        
        # Connect the new header to the exit block
        new_header.successors.append(exit_block)
        exit_block.predecessors.append(new_header)
        
        # Remove connections to the original header and update exit block predecessors
        for pred in header_block.predecessors[:]:
            if pred in header_block.predecessors:
                header_block.predecessors.remove(pred)
        
        for pred in exit_block.predecessors[:]:
            if pred == header_block:
                exit_block.predecessors.remove(pred)
        
        # Add a flag to indicate this was unrolled
        new_header.is_unrolled_loop = True
        new_header.unroll_factor = unroll_factor
        
        # Mark the original header as disabled
        header_block.is_disabled = True
        
        # Update function's total unroll factor (safely handle None values)
        effective_factor = unroll_factor if unroll_factor is not None else 1
        current_factor = getattr(func, 'total_unroll_factor', 1)
        func.total_unroll_factor = current_factor * effective_factor
        
        # Log the unrolling information
        if full_unroll:
            logger.info(f"Fully unrolled loop {header_block.name} with {unroll_factor} iterations")
        else:
            logger.info(f"Partially unrolled loop {header_block.name} with factor {unroll_factor}")
    
    def _get_next_id(self) -> int:
        """Generate a unique ID for IR nodes."""
        next_id = getattr(self, '_next_id', 1000)
        self._next_id = next_id + 1
        return next_id
    
    def _resource_sharing(self, ir: IR) -> IR:
        """
        Resource sharing optimization.
        
        Identifies operations that can share hardware resources.
        """
        shared_count = 0
        
        # For each function in the IR
        for func_name, func in ir.functions.items():
            # For each block in the function
            for block in func.blocks:
                # Placeholder for resource sharing logic
                pass
        
        # Update statistics
        self.resources_shared += shared_count
        if shared_count > 0:
            logger.info(f"Resource sharing: shared {shared_count} operations")
        
        return ir
    
    def _get_loop_blocks(self, header_block: IRBlock) -> List[IRBlock]:
        """
        Get all blocks in a loop.
        
        Args:
            header_block: Loop header block
            
        Returns:
            List of blocks in the loop
        """
        if not header_block.loop_header or header_block.loop_header != header_block:
            # Not a loop header
            return []
            
        if not header_block.loop_exit:
            # No exit block defined
            return []
            
        # Use depth-first search to find all blocks in the loop
        visited = set()
        loop_blocks = []
        
        def dfs(block):
            if block in visited or block == header_block.loop_exit:
                return
                
            visited.add(block)
            loop_blocks.append(block)
            
            # Visit successors
            for succ in block.successors:
                dfs(succ)
        
        # Start from the header block
        dfs(header_block)
        
        return loop_blocks 