#!/usr/bin/env python3
"""
Simple script to check for CALL operations in the compiled IR.
"""

import os
import sys
import logging

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from python_hls.hls import HLS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to the code to compile
FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'functions_to_compile.py'))

def main():
    """Check for CALL operations in the compiled IR."""
    logger.info(f"Compiling file: {FILE_PATH}")
    
    # Compile with optimization level 0
    hls = HLS(optimization_level=0, tech_node=45)
    hls.compile(source_file=FILE_PATH)
    
    # Get IR
    ir = hls.ir
    
    # Print all operations
    print("\n=== ALL OPERATIONS ===")
    for func_name, func in ir.functions.items():
        print(f"\nFunction: {func_name}")
        op_types = set()
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    if hasattr(op, 'op_type'):
                        op_types.add(op.op_type.name)
                        print(f"  Operation: {op.name} (type: {op.op_type.name})")
                    else:
                        print(f"  Operation: {op.name} (type: Unknown)")
        print(f"Operation types in {func_name}: {sorted(op_types)}")
    
    # Check for call operations
    print("\n=== CALL OPERATIONS ===")
    call_count = 0
    for func_name, func in ir.functions.items():
        func_call_count = 0
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    if hasattr(op, 'op_type') and op.op_type.name == 'CALL':
                        call_count += 1
                        func_call_count += 1
                        called_func_name = getattr(op, 'function_name', 'Unknown')
                        print(f"CALL in {func_name} to {called_func_name}")
                        
                        # Print all attributes of the operation
                        print(f"  Attributes of {op.name}:")
                        for attr_name in dir(op):
                            if not attr_name.startswith('__') and not callable(getattr(op, attr_name)):
                                attr_val = getattr(op, attr_name)
                                if not isinstance(attr_val, (list, dict, set)) or len(str(attr_val)) < 100:
                                    print(f"    {attr_name}: {attr_val}")
        
        if func_call_count > 0:
            print(f"{func_name} contains {func_call_count} CALL operations")
        else:
            print(f"{func_name} contains NO CALL operations")
    
    print(f"\nTotal CALL operations found: {call_count}")
    
    # Check function bodies for evidence of function calls
    print("\n=== FUNCTION BODY ANALYSIS ===")
    for func_name, func in ir.functions.items():
        # Look at code to check if there are function calls that were not converted to CALL operations
        print(f"\nAnalyzing function: {func_name}")
        
        # Print basic blocks with their instructions
        for block in func.blocks:
            print(f"  Block: {block.name}")
            for instr in block.instructions:
                print(f"    Instruction: {instr}")
                for op in instr.operations:
                    print(f"      Operation: {op}")

if __name__ == "__main__":
    main() 