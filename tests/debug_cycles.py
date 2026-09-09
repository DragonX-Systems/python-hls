import os
import sys
import ast
import logging
import networkx as nx
import matplotlib.pyplot as plt

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dfg_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dfg_debug")

# Add parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator
from python_hls.optimizer import Optimizer
from python_hls.hls_engine import ASAPScheduler
from python_hls.tech import TechLibrary

def debug_dfg_construction(code, name="test"):
    """Debug the DFG construction process for the given code"""
    logger.info(f"Debugging DFG construction for: {name}")
    
    # Parse the code to AST
    tree = ast.parse(code)
    
    # Generate IR
    ir_generator = IRGenerator()
    ir = ir_generator.generate(tree)
    logger.info(f"IR generated with {len(ir.functions)} functions")
    
    # Apply optimizations
    optimizer = Optimizer(optimization_level=1)
    optimized_ir = optimizer.optimize(ir)
    logger.info("IR optimized")
    
    # Create technology library
    tech_library = TechLibrary(tech_node=45)
    
    # Create ASAP scheduler with verbose logging
    scheduler = ASAPScheduler(tech_library)
    scheduler.verbose = True
    
    # For each function in the IR
    for func_name, func in optimized_ir.functions.items():
        logger.info(f"Analyzing function: {func_name}")
        
        # Manually construct DFG 
        dfg = nx.DiGraph()
        
        # Track all operations
        all_ops = []
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    all_ops.append(op)
                    dfg.add_node(op.node_id, op=op)
        
        # Now add edges based on data dependencies
        for op in all_ops:
            logger.info(f"Operation: {op.op_type.name} (ID: {op.node_id})")
            
            # Print operands
            for operand in op.operands:
                if hasattr(operand, 'node_id'):
                    logger.info(f"  Operand: {operand.name} (ID: {operand.node_id})")
                else:
                    logger.info(f"  Operand: {operand} (constant)")
            
            # Check dependencies (variables defined by other operations)
            for op2 in all_ops:
                if op != op2 and op2.result:  # Skip self and ops with no result
                    # If op2 produces a result that op uses as an operand
                    for operand in op.operands:
                        if hasattr(operand, 'node_id') and operand.node_id == op2.result.node_id:
                            dfg.add_edge(op2.node_id, op.node_id)
                            logger.info(f"  Depends on: {op2.op_type.name} (ID: {op2.node_id})")
        
        # Check for cycles
        logger.info("Checking for cycles in the DFG...")
        cycles = list(nx.simple_cycles(dfg))
        if cycles:
            logger.info(f"Found {len(cycles)} cycles in the DFG")
            for i, cycle in enumerate(cycles):
                logger.info(f"Cycle {i+1}: {cycle}")
                # Print operations in the cycle
                logger.info("Operations in the cycle:")
                for node_id in cycle:
                    op = dfg.nodes[node_id]['op']
                    logger.info(f"  {op.op_type.name} (ID: {node_id})")
                    if op.result:
                        logger.info(f"    Result: {op.result.name}")
                    logger.info(f"    Operands: {[operand.name if hasattr(operand, 'name') else str(operand) for operand in op.operands]}")
        else:
            logger.info("No cycles found in the DFG")
            
            # Try to run the scheduler
            logger.info("Attempting to schedule operations...")
            try:
                # Schedule only this function
                func.max_control_step = scheduler._schedule_function(func)
                logger.info(f"Scheduling successful. Max control step: {func.max_control_step}")
                
                # Print operations by control step
                op_by_step = {}
                for block in func.blocks:
                    for instr in block.instructions:
                        for op in instr.operations:
                            step = op.control_step
                            if step not in op_by_step:
                                op_by_step[step] = []
                            op_by_step[step].append(op)
                
                logger.info("Operations by control step:")
                for step in sorted(op_by_step.keys()):
                    logger.info(f"  Step {step}:")
                    for op in op_by_step[step]:
                        operand_str = ", ".join([
                            str(operand.name) if hasattr(operand, 'name') else str(operand)
                            for operand in op.operands
                        ])
                        result_str = op.result.name if op.result else "None"
                        logger.info(f"    {op.op_type.name}: {operand_str} -> {result_str}")
            except Exception as e:
                logger.error(f"Scheduling failed: {e}")
        
        # Visualize the DFG
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(dfg)
        nx.draw(dfg, pos, with_labels=True, node_color='lightblue', node_size=500, arrows=True)
        labels = {node: data['op'].op_type.name for node, data in dfg.nodes(data=True)}
        nx.draw_networkx_labels(dfg, pos, labels=labels)
        plt.title(f"Data Flow Graph for {func_name}")
        plt.savefig(f"{name}_dfg.png")
        logger.info(f"DFG visualization saved to {name}_dfg.png")

def main():
    # First, let's analyze a simple function to make sure our debugger works
    simple_code = """
def simple_add(a, b):
    c = a + b
    return c
"""
    debug_dfg_construction(simple_code, "simple_add")
    
    # Then analyze a function with a simple loop
    simple_loop_code = """
def simple_loop(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
    debug_dfg_construction(simple_loop_code, "simple_loop")
    
    # Now let's make a simplified version of our SPMM code
    spmm_mini_code = """
def spmm_mini(A, values, row_num, row_ptr, C):
    # Mini SPMM with just a single element computation
    i = 0
    j = 0
    sum_val = 0
    k_start = row_ptr[j]
    
    # Just one iteration
    k_ptr = k_start
    k = row_num[k_ptr]
    x = A[i][k]
    wt = values[k_ptr]
    sum_val = x * wt
    
    # Store the result
    C[i][j] = sum_val
    return C
"""
    debug_dfg_construction(spmm_mini_code, "spmm_mini")
    
    # Finally, analyze a version with a small loop
    spmm_loop_code = """
def spmm_loop(A, values, row_num, row_ptr, C):
    i = 0  # Fix row index
    j = 0  # Fix column index
    sum_val = 0
    k_start = row_ptr[j]
    
    # Simple loop with fixed bounds
    for k_idx in range(3):  # Just 3 iterations
        k_ptr = k_start + k_idx
        k = row_num[k_ptr]
        x = A[i][k]
        wt = values[k_ptr]
        sum_val += x * wt
    
    # Store the result
    C[i][j] = sum_val
    return C
"""
    debug_dfg_construction(spmm_loop_code, "spmm_loop")

if __name__ == "__main__":
    main() 