import os
import sys
import time
import ast
import logging
import copy
import shutil
from pprint import pformat
import unittest

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fft_hls_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("fft_hls_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS
from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator

def analyze_fft_function(function_name, optimization_level=1):
    """Analyze a specific FFT function with HLS compilation"""
    logger.info(f"=" * 80)
    logger.info(f"Analyzing FFT function: {function_name}")
    logger.info(f"=" * 80)
    
    # Path to the FFT file
    fft_file_path = os.path.join("verification_workloads", "fft.py")
    
    # Check if the FFT file exists
    if not os.path.exists(fft_file_path):
        logger.error(f"FFT file not found at {fft_file_path}")
        # Try alternative path
        fft_file_path = "fft.py"
        if not os.path.exists(fft_file_path):
            logger.error(f"FFT file not found at {fft_file_path} either")
            raise FileNotFoundError("Could not find fft.py file")
    
    logger.info(f"Using FFT file: {fft_file_path}")
    
    try:
        # Create an HLS instance
        hls = HLS(optimization_level=optimization_level, tech_node=45)
        logger.info(f"Created HLS instance with optimization level {optimization_level}")
        
        # Hook into the compilation process to get more details
        original_parse_file = hls.parser.parse_file
        original_generate = hls.ir_generator.generate
        
        def parse_file_hook(filename):
            """Hook to track parsing details"""
            logger.info(f"Parsing source file: {filename}")
            result = original_parse_file(filename)
            logger.info(f"Parse result: {type(result)} with {len(result.body) if hasattr(result, 'body') else 'unknown'} top-level nodes")
            
            # Log all functions found in the AST
            if hasattr(result, 'body'):
                functions_found = []
                for node in result.body:
                    if hasattr(node, 'name') and hasattr(node, '__class__'):
                        if 'FunctionDef' in str(type(node)):
                            functions_found.append(node.name)
                logger.info(f"Functions found in AST: {functions_found}")
            
            return result
        
        def ir_generation_hook(ast_node):
            """Hook to track IR generation details"""
            logger.info(f"Generating IR from AST: {type(ast_node)}")
            result = original_generate(ast_node)
            if result:
                logger.info(f"Generated IR with {len(result.functions)} functions")
                for func_name, func in result.functions.items():
                    logger.info(f"  Function '{func_name}': {len(func.blocks)} blocks, {len(func.local_vars)} variables")
                    total_ops = sum(len(instr.operations) for block in func.blocks for instr in block.instructions)
                    logger.info(f"    Total operations: {total_ops}")
                    
                    if total_ops == 0:
                        logger.warning(f"    WARNING: Function {func_name} has no operations!")
                        # Log block details
                        for i, block in enumerate(func.blocks):
                            logger.info(f"      Block {i}: {len(block.instructions)} instructions")
                            for j, instr in enumerate(block.instructions):
                                logger.info(f"        Instruction {j}: {len(instr.operations)} operations")
            else:
                logger.warning("IR generation returned None")
            return result
        
        # Replace the methods with our hooks
        hls.parser.parse_file = parse_file_hook
        hls.ir_generator.generate = ir_generation_hook
        
        # Compile the FFT code
        logger.info(f"Compiling FFT function: {function_name}")
        
        # Set the function to compile if it's not the main function
        if function_name != "test_fft":
            hls.target_function = function_name
        
        # Perform the compilation
        netlist = hls.compile(fft_file_path, target="verilog")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        opt_report = hls.get_optimization_report()
        opt_summary = hls.get_optimization_summary()
        
        logger.info(f"RESULTS for {function_name}:")
        logger.info(f"  - Technology node: {metrics['technology_node']}")
        logger.info(f"  - Total area: {metrics['total_area']}")
        logger.info(f"  - Total power: {metrics['total_power']}")
        logger.info(f"  - Critical path: {metrics['critical_path']}")
        logger.info(f"  - Latency cycles: {metrics.get('latency_cycles', 'N/A')}")
        logger.info(f"  - Power breakdown: {metrics['power_breakdown']}")
        logger.info(f"  - Optimization summary: {opt_summary}")
        
        # Log detailed IR information if available
        if hasattr(hls, 'ir') and hls.ir:
            logger.info(f"IR Analysis:")
            for func_name, func in hls.ir.functions.items():
                logger.info(f"  Function {func_name}:")
                logger.info(f"    Blocks: {len(func.blocks)}")
                logger.info(f"    Variables: {len(func.local_vars)}")
                if hasattr(func, 'total_latency'):
                    logger.info(f"    Total latency: {func.total_latency} cycles")
                if hasattr(func, 'single_iter_latency'):
                    logger.info(f"    Single iteration latency: {func.single_iter_latency} cycles")
                
                # Count operations by type
                op_counts = {}
                for block in func.blocks:
                    for instr in block.instructions:
                        for op in instr.operations:
                            op_type = op.op_type.name
                            op_counts[op_type] = op_counts.get(op_type, 0) + 1
                
                if op_counts:
                    logger.info(f"    Operation counts: {op_counts}")
                else:
                    logger.warning(f"    No operations found in function {func_name}")
        
        return {
            "netlist": netlist,
            "metrics": metrics,
            "optimization_report": opt_report,
            "optimization_summary": opt_summary
        }
        
    except Exception as e:
        logger.error(f"Error during FFT analysis: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def analyze_all_fft_functions():
    """Analyze all FFT functions"""
    functions_to_test = [
        "fft_8_point",  # Small function for testing
        "fft_1024_point",  # Main FFT function
        "fft_optimized_1024_point",  # Optimized version
        "test_fft"  # Test function
    ]
    
    results = {}
    
    for func_name in functions_to_test:
        try:
            logger.info(f"Testing function: {func_name}")
            results[func_name] = analyze_fft_function(func_name)
            logger.info(f"Successfully analyzed {func_name}")
        except Exception as e:
            logger.error(f"Failed to analyze {func_name}: {e}")
            results[func_name] = {"error": str(e)}
    
    return results

def test_simple_fft_functions():
    """Test simple mathematical functions from FFT first"""
    logger.info("=" * 80)
    logger.info("Testing simple FFT helper functions")
    logger.info("=" * 80)
    
    simple_functions = [
        "log2_int",
        "sin_taylor", 
        "cos_taylor",
        "complex_exp",
        "complex_mult",
        "complex_add",
        "complex_sub"
    ]
    
    results = {}
    
    for func_name in simple_functions:
        try:
            logger.info(f"Testing simple function: {func_name}")
            results[func_name] = analyze_fft_function(func_name, optimization_level=0)
            logger.info(f"Successfully analyzed {func_name}")
        except Exception as e:
            logger.error(f"Failed to analyze {func_name}: {e}")
            results[func_name] = {"error": str(e)}
    
    return results

def inspect_fft_source():
    """Inspect the FFT source code to understand its structure"""
    logger.info("=" * 80)
    logger.info("Inspecting FFT source code")
    logger.info("=" * 80)
    
    fft_file_path = os.path.join("verification_workloads", "fft.py")
    if not os.path.exists(fft_file_path):
        fft_file_path = "fft.py"
    
    if not os.path.exists(fft_file_path):
        logger.error("Cannot find fft.py file")
        return
    
    with open(fft_file_path, 'r') as f:
        source_code = f.read()
    
    # Parse the AST to find function definitions
    try:
        tree = ast.parse(source_code)
        
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'has_return': any(isinstance(n, ast.Return) for n in ast.walk(node))
                })
        
        logger.info(f"Found {len(functions)} functions in FFT file:")
        for func in functions:
            logger.info(f"  {func['name']} (line {func['line']}): args={func['args']}, has_return={func['has_return']}")
        
        return functions
        
    except Exception as e:
        logger.error(f"Error parsing FFT source: {e}")
        return []

def main():
    """Main function to run FFT tests"""
    logger.info("Starting FFT HLS analysis")
    
    # First, inspect the source code
    functions = inspect_fft_source()
    
    # Test simple functions first
    logger.info("Testing simple helper functions...")
    simple_results = test_simple_fft_functions()
    
    # Test main FFT functions
    logger.info("Testing main FFT functions...")
    main_results = analyze_all_fft_functions()
    
    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY OF RESULTS:")
    logger.info("=" * 80)
    
    logger.info("Simple functions:")
    for func_name, result in simple_results.items():
        if "error" in result:
            logger.info(f"  {func_name}: FAILED - {result['error']}")
        else:
            logger.info(f"  {func_name}: SUCCESS")
    
    logger.info("Main functions:")
    for func_name, result in main_results.items():
        if "error" in result:
            logger.info(f"  {func_name}: FAILED - {result['error']}")
        else:
            logger.info(f"  {func_name}: SUCCESS")
    
    return simple_results, main_results

class TestFFT(unittest.TestCase):
    """Test FFT HLS functionality"""
    
    def test_simple_fft_functions(self):
        """Test that simple FFT helper functions compile successfully"""
        simple_functions = ["log2_int", "sin_taylor", "cos_taylor"]
        
        for func_name in simple_functions:
            with self.subTest(function=func_name):
                try:
                    result = analyze_fft_function(func_name, optimization_level=0)
                    self.assertIsNotNone(result["netlist"], f"Netlist should not be None for {func_name}")
                    self.assertGreater(result["metrics"]["total_area"], 0, f"Area should be greater than 0 for {func_name}")
                except Exception as e:
                    self.fail(f"Function {func_name} failed to compile: {e}")
    
    def test_fft_1024_point(self):
        """Test that the main 1024-point FFT compiles"""
        try:
            result = analyze_fft_function("fft_1024_point")
            self.assertIsNotNone(result["netlist"], "Netlist should not be None for fft_1024_point")
            self.assertGreater(result["metrics"]["total_area"], 0, "Area should be greater than 0 for fft_1024_point")
        except Exception as e:
            self.fail(f"fft_1024_point failed to compile: {e}")

if __name__ == "__main__":
    # Run the main analysis
    simple_results, main_results = main()
    
    # Optionally run unit tests
    # unittest.main(argv=[''], exit=False, verbosity=2) 