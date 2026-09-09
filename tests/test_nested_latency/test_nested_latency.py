"""
Test script to verify correct latency calculation for nested loops and function calls.
"""

import os
import sys
import unittest
import logging

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from python_hls.hls import HLS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get test file path
CURRENT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'functions_to_compile.py'))

class TestNestedLatency(unittest.TestCase):
    """Test case for verifying nested loop and function call latency calculations."""
    
    def test_nested_latency(self):
        """Test that our improved scheduler handles nested structures correctly."""
        # Compile the file with all functions
        hls = HLS(optimization_level=0, tech_node=45)
        hls.compile(source_file=CURRENT_FILE)
        
        # Get the IR for analysis
        ir = hls.ir
        
        # Get function objects
        inner_func = ir.functions.get('inner_function')
        middle_func = ir.functions.get('middle_function')
        outer_func = ir.functions.get('outer_function')
        main_func = ir.functions.get('main')
        
        self.assertIsNotNone(inner_func, "inner_function should be in the IR")
        self.assertIsNotNone(middle_func, "middle_function should be in the IR")
        self.assertIsNotNone(outer_func, "outer_function should be in the IR")
        self.assertIsNotNone(main_func, "main should be in the IR")
        
        # Print latency information
        logger.info("\n--- Function Latencies ---")
        logger.info(f"inner_function: single_iter_latency={inner_func.single_iter_latency}, total_latency={inner_func.total_latency}")
        logger.info(f"middle_function: single_iter_latency={middle_func.single_iter_latency}, total_latency={middle_func.total_latency}")
        logger.info(f"outer_function: single_iter_latency={outer_func.single_iter_latency}, total_latency={outer_func.total_latency}")
        logger.info(f"main: single_iter_latency={main_func.single_iter_latency}, total_latency={main_func.total_latency}")
        
        # Check that loop functions have greater total latency than single iteration latency
        for func_name, func in [('inner_function', inner_func), 
                               ('middle_function', middle_func), 
                               ('outer_function', outer_func)]:
            self.assertGreater(func.total_latency, func.single_iter_latency, 
                              f"{func_name} should have total_latency > single_iter_latency")
        
        # Analyze function calls
        logger.info("\n--- Function Call Analysis ---")
        call_count = 0
        function_calls = {
            'main': [],
            'outer_function': [],
            'middle_function': [],
            'inner_function': []
        }
        
        for func_name, func in ir.functions.items():
            for block in func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        if hasattr(op, 'op_type') and op.op_type.name == 'CALL':
                            call_count += 1
                            called_func_name = getattr(op, 'function_name', 'Unknown')
                            function_calls[func_name].append(called_func_name)
                            
                            logger.info(f"{func_name} calls {called_func_name}")
                            
                            called_func = ir.functions.get(called_func_name)
                            
                            if called_func:
                                logger.info(f"  Called function latency: {called_func.total_latency}")
                            
                            # Get the operation's own latency/delay
                            if hasattr(op, 'control_step'):
                                # Calculate delay based on its data dependencies/scheduling
                                delay = getattr(op, '_delay', None)
                                logger.info(f"  Operation control_step: {op.control_step}")
                                logger.info(f"  Operation delay: {delay}")
        
        # Verify expected function call hierarchy
        logger.info("\n--- Function Call Hierarchy Analysis ---")
        logger.info(f"Total detected CALL operations: {call_count}")
        for caller, callees in function_calls.items():
            logger.info(f"{caller} calls: {', '.join(callees) if callees else 'no functions'}")
        
        # Verify the expected call hierarchy
        self.assertIn('outer_function', function_calls['main'], "main should call outer_function")
        self.assertIn('middle_function', function_calls['outer_function'], "outer_function should call middle_function")
        self.assertIn('inner_function', function_calls['middle_function'], "middle_function should call inner_function")
        
        # Verify loop nesting is reflected in latency
        logger.info("\n--- Loop Structure Analysis ---")
        
        # Count loops in each function
        for func_name, func in ir.functions.items():
            loop_count = sum(1 for block in func.blocks if block.loop_header == block)
            logger.info(f"{func_name} has {loop_count} loops")
            
            # Analyze loop nesting
            nested_loops = []
            for block in func.blocks:
                if block.loop_header == block:
                    # Check if this is a nested loop
                    for other_block in func.blocks:
                        if other_block.loop_header == other_block and other_block != block:
                            # Check if this block is inside the other loop's body
                            if block in self._get_loop_body(other_block):
                                nested_loops.append((block, other_block))
            
            logger.info(f"{func_name} has {len(nested_loops)} nested loops")
            
            for inner, outer in nested_loops:
                logger.info(f"  Loop {inner.name} is nested inside {outer.name}")
        
        # Verify latency propagation
        logger.info("\n--- Latency Propagation Analysis ---")
        if call_count > 0:
            # Main should have latency at least as large as outer_function's
            self.assertGreaterEqual(main_func.total_latency, outer_func.total_latency, 
                                  "main latency should include outer_function latency")
            
            # Outer function should have latency at least as large as middle_function's
            self.assertGreaterEqual(outer_func.total_latency, middle_func.total_latency, 
                                  "outer_function latency should include middle_function latency")
            
            # Middle function should have latency at least as large as inner_function's
            self.assertGreaterEqual(middle_func.total_latency, inner_func.total_latency, 
                                  "middle_function latency should include inner_function latency")
        else:
            logger.warning("No function calls detected, can't verify latency propagation!")
            
        # Test passes if execution reaches here without exceptions
        self.assertTrue(True, "Nested loop and function latency calculation test passed")
    
    def _get_loop_body(self, header_block):
        """Get all blocks in a loop body (excluding the header)."""
        if not hasattr(header_block, 'loop_exit') or not header_block.loop_exit:
            return []
            
        body_blocks = []
        visited = set()
        
        def dfs(block):
            if block in visited or block == header_block.loop_exit:
                return
            visited.add(block)
            if block != header_block:  # Exclude header
                body_blocks.append(block)
            for succ in block.successors:
                dfs(succ)
        
        # Start from header's successors
        for succ in header_block.successors:
            if succ != header_block.loop_exit:  # Skip exit edge
                dfs(succ)
                
        return body_blocks

if __name__ == '__main__':
    unittest.main() 