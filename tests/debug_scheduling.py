import os
import sys
import ast
from pprint import pprint, pformat
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduling_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduling_debug")

# Add parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator
from python_hls.optimizer import Optimizer
from python_hls.hls_engine import ASAPScheduler
from python_hls.tech import TechLibrary

def debug_scheduling(code, name="test", enable_pipeline=False, pipeline_depth=1):
    """Debug the scheduling process for the given code"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(f"{name}_scheduling_debug.log"),
            logging.StreamHandler()
        ]
    )
    
    logger.info(f"Debugging scheduling for {name}")
    logger.info(f"Code:\n{code}")
    
    # Parse code to AST
    tree = ast.parse(code)
    
    # Generate IR
    ir_generator = IRGenerator()
    ir = ir_generator.generate(tree)
    
    # Print the IR function information
    func_name = name
    func = ir.get_function(func_name)
    if func:
        logger.info(f"Function {func_name} has {func.loop_count} loops with approximately {func.loop_iterations} total iterations")
    
    # Create tech library
    tech_library = TechLibrary(tech_node=14)
    
    # Create scheduler
    scheduler = ASAPScheduler(tech_library)
    
    # Enable pipelining if requested
    if enable_pipeline and func:
        logger.info(f"Enabling loop pipelining with depth {pipeline_depth}")
        func.enable_pipeline = True
        func.pipeline_depth = pipeline_depth
    
    # Schedule the IR
    scheduled_ir = scheduler.schedule(ir)
    
    # Log function information after scheduling
    for func_name, func in scheduled_ir.functions.items():
        logger.info(f"Function: {func_name}")
        logger.info(f"Max control step: {func.max_control_step}")
        logger.info(f"Single iteration latency: {func.single_iter_latency} cycles")
        logger.info(f"Total latency (including loops): {func.total_latency} cycles")
        
        # Calculate latency ratio to demonstrate impact of loop iterations
        if func.single_iter_latency > 0:
            ratio = func.total_latency / func.single_iter_latency
            logger.info(f"Latency ratio (total/single): {ratio:.2f}x")
        
        op_by_step = {}
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    step = op.control_step
                    if step not in op_by_step:
                        op_by_step[step] = []
                    op_by_step[step].append(op)
        
        # Print operations by control step
        logger.info(f"Operations by control step:")
        for step in sorted(op_by_step.keys()):
            logger.info(f"  Step {step}:")
            for op in op_by_step[step]:
                operand_str = ", ".join([
                    str(operand.name) if hasattr(operand, 'name') else str(operand)
                    for operand in op.operands
                ])
                result_str = op.result.name if op.result else "None"
                logger.info(f"    {op.op_type.name}: {operand_str} -> {result_str}")
    
    # Count operations in DFG
    operation_count = 0
    for func in scheduled_ir.functions.values():
        for block in func.blocks:
            for instr in block.instructions:
                operation_count += len(instr.operations)
    
    logger.info(f"Total operations in scheduled IR: {operation_count}")
    
    return scheduled_ir

def main():
    # Create a simple test function
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
    
    # Debug simple loop without pipelining
    logger.info("=" * 80)
    logger.info("DEBUGGING SIMPLE LOOP WITHOUT PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(simple_loop_code, "simple_loop")
    
    # Debug simple loop with pipelining
    logger.info("\n" + "=" * 80)
    logger.info("DEBUGGING SIMPLE LOOP WITH PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(simple_loop_code, "simple_loop_pipelined", enable_pipeline=True, pipeline_depth=1)
    
    # Debug tiny SPMM without pipelining
    logger.info("\n" + "=" * 80)
    logger.info("DEBUGGING TINY SPMM WITHOUT PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(spmm_tiny_code, "spmm_tiny")
    
    # Debug tiny SPMM with pipelining
    logger.info("\n" + "=" * 80)
    logger.info("DEBUGGING TINY SPMM WITH PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(spmm_tiny_code, "spmm_tiny_pipelined", enable_pipeline=True, pipeline_depth=1)
    
    # Debug the fixed size implementations
    fixed_256_code = """
def spmm_fixed_256(A, values, row_num, row_ptr, C):
    # Hardcoded size = 256
    
    # Completely unrolled outer loops
    for i in range(256):
        for j in range(256):
            sum_val = 0
            k_start = row_ptr[j]
            
            # Inner loop with fixed iteration count
            for k_idx in range(64):
                k_ptr = k_start + k_idx
                k = row_num[k_ptr]
                x = A[i][k]
                wt = values[k_ptr]
                sum_val += x * wt
            
            C[i][j] = sum_val
    
    return C
"""
    
    # Debug fixed size 256 without pipelining
    logger.info("\n" + "=" * 80)
    logger.info("DEBUGGING FIXED SIZE 256 WITHOUT PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(fixed_256_code, "spmm_fixed_256")
    
    # Debug fixed size 256 with pipelining
    logger.info("\n" + "=" * 80)
    logger.info("DEBUGGING FIXED SIZE 256 WITH PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(fixed_256_code, "spmm_fixed_256_pipelined", enable_pipeline=True, pipeline_depth=2)
    
    # Debug a more complex example with different pipeline depths
    matrix_mul_code = """
def matrix_multiply(A, B, C, N):
    for i in range(N):
        for j in range(N):
            sum_val = 0
            for k in range(N):
                sum_val += A[i][k] * B[k][j]
            C[i][j] = sum_val
    return C
"""
    
    # Debug matrix multiply without pipelining
    logger.info("\n" + "=" * 80)
    logger.info("DEBUGGING MATRIX MULTIPLY WITHOUT PIPELINING")
    logger.info("=" * 80)
    debug_scheduling(matrix_mul_code, "matrix_multiply")
    
    # Debug matrix multiply with different pipeline depths
    for depth in [1, 2, 4]:
        logger.info("\n" + "=" * 80)
        logger.info(f"DEBUGGING MATRIX MULTIPLY WITH PIPELINE DEPTH {depth}")
        logger.info("=" * 80)
        debug_scheduling(matrix_mul_code, f"matrix_multiply_pipe_{depth}", 
                        enable_pipeline=True, pipeline_depth=depth)
    
    logger.info("\n" + "=" * 80)
    logger.info("SCHEDULING DEBUG COMPLETE")
    logger.info("=" * 80)

if __name__ == "__main__":
    main() 