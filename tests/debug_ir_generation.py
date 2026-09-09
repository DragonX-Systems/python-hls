import os
import sys
import ast
from pprint import pprint

# Add parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator

def debug_ast(code):
    """Parse the code and print the AST"""
    print("=" * 80)
    print("AST ANALYSIS")
    print("=" * 80)
    
    tree = ast.parse(code)
    print("AST node type:", type(tree))
    print("Contents:")
    
    # Get function definition
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            print(f"Function: {node.name}")
            print(f"Arguments: {[arg.arg for arg in node.args.args]}")
            
            # Count loop constructs
            for_loops = sum(1 for n in ast.walk(node) if isinstance(n, ast.For))
            while_loops = sum(1 for n in ast.walk(node) if isinstance(n, ast.While))
            if_stmts = sum(1 for n in ast.walk(node) if isinstance(n, ast.If))
            
            print(f"Contains {for_loops} 'for' loops, {while_loops} 'while' loops, {if_stmts} 'if' statements")
            
            # Check for return statement
            returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            print(f"Contains {len(returns)} return statements")
            
            # Count computations (Add, Mult, etc.)
            binops = [n for n in ast.walk(node) if isinstance(n, ast.BinOp)]
            print(f"Contains {len(binops)} binary operations")
            
            # Dump AST for visual inspection (limited to avoid overwhelming output)
            print("\nAST Dump (truncated):")
            dump = ast.dump(node)
            print(dump[:500] + ("..." if len(dump) > 500 else ""))

def debug_ir_generation(code):
    """Generate IR from code and examine its structure"""
    print("\n" + "=" * 80)
    print("IR GENERATION ANALYSIS")
    print("=" * 80)
    
    # Parse the code to AST
    parser = PythonParser()
    tree = ast.parse(code)  # Use Python's built-in ast module instead
    
    # Generate IR
    ir_generator = IRGenerator()
    ir = ir_generator.generate(tree)
    
    # Analyze IR
    print(f"IR contains {len(ir.functions)} functions")
    
    for func_name, func in ir.functions.items():
        print(f"\nFunction: {func_name}")
        print(f"Parameters: {[param.name for param in func.parameters]}")
        print(f"Return var: {func.return_var.name if func.return_var else 'None'}")
        print(f"Local variables: {list(func.local_vars.keys())}")
        
        # Count blocks
        print(f"Contains {len(func.blocks)} blocks")
        
        # Count operations
        op_count = 0
        op_types = {}
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    op_count += 1
                    op_type = op.op_type.name
                    op_types[op_type] = op_types.get(op_type, 0) + 1
        
        print(f"Contains {op_count} operations")
        print("Operation types:")
        for op_type, count in op_types.items():
            print(f"  {op_type}: {count}")

def main():
    # Create a simple test function
    simple_calc_code = """
def simple_calc(a, b):
    c = a + b
    d = a * b
    e = c - d
    return e
"""
    
    simple_loop_code = """
def simple_loop(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
    
    # Create a specialized SPMM code for testing
    spmm_tiny_code = """
def spmm_tiny(A, values, row_num, row_ptr, C):
    # Tiny SPMM with fixed size of 4
    for i in range(4):
        for j in range(4):
            sum_val = 0
            k_start = row_ptr[j]
            for k_idx in range(1):  # Just a single iteration for simplicity
                k_ptr = k_start + k_idx
                k = row_num[k_ptr]
                x = A[i][k]
                wt = values[k_ptr]
                sum_val += x * wt
            C[i][j] = sum_val
    return C
"""
    
    # Load the SPMM code files
    spmm_256_path = os.path.join(os.getcwd(), "spmm_simple_256.py")
    spmm_512_path = os.path.join(os.getcwd(), "spmm_simple_512.py")
    
    spmm_256_code = ""
    spmm_512_code = ""
    
    try:
        with open(spmm_256_path, 'r') as f:
            spmm_256_code = f.read()
        with open(spmm_512_path, 'r') as f:
            spmm_512_code = f.read()
    except FileNotFoundError:
        print(f"Warning: SPMM code files not found at {spmm_256_path} or {spmm_512_path}")
    
    # Debug simple calculation
    print("\n\n" + "=" * 80)
    print("DEBUGGING SIMPLE CALCULATION")
    print("=" * 80)
    debug_ast(simple_calc_code)
    debug_ir_generation(simple_calc_code)
    
    # Debug simple loop
    print("\n\n" + "=" * 80)
    print("DEBUGGING SIMPLE LOOP")
    print("=" * 80)
    debug_ast(simple_loop_code)
    debug_ir_generation(simple_loop_code)
    
    # Debug tiny SPMM
    print("\n\n" + "=" * 80)
    print("DEBUGGING TINY SPMM")
    print("=" * 80)
    debug_ast(spmm_tiny_code)
    debug_ir_generation(spmm_tiny_code)
    
    # Debug SPMM with size 256 if file exists
    if spmm_256_code:
        print("\n\n" + "=" * 80)
        print("DEBUGGING SPMM (SIZE 256)")
        print("=" * 80)
        debug_ast(spmm_256_code)
        debug_ir_generation(spmm_256_code)
    
    # Debug SPMM with size 512 if file exists
    if spmm_512_code:
        print("\n\n" + "=" * 80)
        print("DEBUGGING SPMM (SIZE 512)")
        print("=" * 80)
        debug_ast(spmm_512_code)
        debug_ir_generation(spmm_512_code)

if __name__ == "__main__":
    main() 