#!/usr/bin/env python3
"""
RTL Verification Example for Python-HLS

This example demonstrates how to use the RTL verification framework to compare
generated Verilog RTL with the original Python source code execution.
"""

import os
import sys
import tempfile
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS

# Set up logging to see verification details
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_test_functions():
    """Create test Python files with various functions to verify."""
    
    # Simple arithmetic function
    simple_func = '''
def add_multiply(a, b, c):
    """Simple arithmetic function: (a + b) * c"""
    return (a + b) * c
'''
    
    # GCD function (more complex control flow)
    gcd_func = '''
def gcd(a, b):
    """Calculate greatest common divisor using Euclidean algorithm."""
    while b != 0:
        temp = b
        b = a % b
        a = temp
    return a
'''
    
    # Factorial function (recursive-like behavior)
    factorial_func = '''
def factorial_iterative(n):
    """Calculate factorial iteratively."""
    result = 1
    for i in range(1, n + 1):
        result = result * i
    return result
'''
    
    # FIR filter (array processing)
    fir_func = '''
def fir_filter_simple(x, h):
    """Simple FIR filter implementation."""
    # Simplified version for RTL verification
    # Assume fixed size arrays for HLS
    y = 0
    for i in range(4):  # Fixed size for HLS
        if i < len(x) and i < len(h):
            y += x[i] * h[i]
    return y
'''
    
    return {
        "simple_arithmetic": simple_func,
        "gcd_algorithm": gcd_func,
        "factorial": factorial_func,
        "fir_filter": fir_func
    }


def create_test_vectors():
    """Create test vectors for different functions."""
    
    test_vectors = {
        "add_multiply": [
            {"a": 1, "b": 2, "c": 3},
            {"a": 0, "b": 5, "c": 7},
            {"a": -2, "b": 4, "c": 1},
            {"a": 10, "b": -5, "c": 2},
            {"a": 255, "b": 1, "c": 1},  # Edge case for 8-bit
        ],
        
        "gcd": [
            {"a": 48, "b": 18},
            {"a": 17, "b": 13},
            {"a": 100, "b": 25},
            {"a": 7, "b": 3},
            {"a": 1024, "b": 256},
        ],
        
        "factorial_iterative": [
            {"n": 0},
            {"n": 1},
            {"n": 5},
            {"n": 7},
            {"n": 10},
        ],
        
        "fir_filter_simple": [
            {"x": [1, 2, 3, 4], "h": [0.5, 0.25, 0.125, 0.0625]},
            {"x": [0, 1, 0, 1], "h": [1, 1, 1, 1]},
            {"x": [5, -2, 3, 1], "h": [0.1, 0.2, 0.3, 0.4]},
        ]
    }
    
    return test_vectors


def run_verification_example(function_name: str, function_code: str, test_vectors: list):
    """Run RTL verification for a specific function."""
    
    print(f"\n{'='*60}")
    print(f"RTL VERIFICATION: {function_name}")
    print(f"{'='*60}")
    
    # Create temporary file with the function
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(function_code)
        temp_file = f.name
    
    try:
        # Create HLS instance
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile to Verilog
        print("1. Compiling Python to Verilog...")
        netlist = hls.compile(temp_file, target="verilog")
        
        if netlist:
            print("   ✓ Compilation successful")
            
            # Get performance metrics
            metrics = hls.get_performance_metrics()
            print(f"   - Area: {metrics.get('total_area', 0):.2f} μm²")
            print(f"   - Power: {metrics.get('total_power', 0):.2f} mW")
            print(f"   - Latency: {metrics.get('latency_cycles', 0)} cycles")
        else:
            print("   ✗ Compilation failed")
            return
        
        # Check if Verilator is available
        print("\n2. Checking Verilator availability...")
        if hls.rtl_verifier.verilator_available:
            print("   ✓ Verilator found - RTL verification enabled")
            
            # Run RTL verification
            print("\n3. Running RTL verification...")
            verification_results = hls.verify_rtl(
                test_vectors=test_vectors,
                num_random_tests=0,  # Use only provided test vectors
                save_report=True
            )
            
            # Display results
            if "error" in verification_results:
                print(f"   ✗ Verification failed: {verification_results['error']}")
            else:
                print("   ✓ Verification completed")
                
                # Show summary
                if "report" in verification_results:
                    print("\n4. Verification Results:")
                    print("-" * 40)
                    
                    # Extract key results from the report
                    report_lines = verification_results["report"].split('\n')
                    in_summary = False
                    
                    for line in report_lines:
                        if "SUMMARY" in line:
                            in_summary = True
                        elif in_summary and line.strip():
                            print(f"   {line}")
                        elif line.strip().startswith("✓") or line.strip().startswith("✗"):
                            print(f"   {line}")
                
                # Show detailed results for verification_results
                if "verification_results" in verification_results:
                    for module_name, module_result in verification_results["verification_results"].items():
                        if "comparison" in module_result:
                            comparison = module_result["comparison"]
                            total_tests = comparison.get("total_tests", 0)
                            passed = comparison.get("passed", 0)
                            failed = comparison.get("failed", 0)
                            
                            print(f"\n   Module '{module_name}':")
                            print(f"     Tests: {passed}/{total_tests} passed")
                            
                            if failed > 0:
                                print(f"     ⚠ {failed} tests failed")
                                # Show first mismatch
                                mismatches = comparison.get("mismatches", [])
                                if mismatches:
                                    mismatch = mismatches[0]
                                    print(f"     Example mismatch:")
                                    print(f"       Input: {mismatch['test_vector']}")
                                    print(f"       Python: {mismatch['python_result']}")
                                    print(f"       RTL: {mismatch['rtl_result']}")
                            else:
                                print(f"     ✓ All tests passed!")
        else:
            print("   ⚠ Verilator not found - RTL verification disabled")
            print("   Install Verilator to enable RTL verification:")
            print("   - Ubuntu/Debian: sudo apt-get install verilator")
            print("   - macOS: brew install verilator")
            print("   - Or build from source: https://verilator.org/guide/latest/install.html")
            
            # Still show Python execution results
            print("\n3. Running Python reference execution...")
            python_results = hls.rtl_verifier.python_executor.execute_function(
                temp_file, function_name.split('_')[0] if '_' in function_name else function_name, test_vectors
            )
            
            if "results" in python_results:
                print("   ✓ Python execution completed")
                print("   Reference results:")
                for i, (test_vector, result) in enumerate(zip(test_vectors, python_results["results"])):
                    print(f"     Test {i+1}: {test_vector} -> {result}")
            else:
                print(f"   ✗ Python execution failed: {python_results.get('error', 'Unknown error')}")
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def main():
    """Main function to run RTL verification examples."""
    
    print("Python-HLS RTL Verification Example")
    print("=" * 40)
    print()
    print("This example demonstrates RTL verification by comparing")
    print("generated Verilog simulation results with Python execution.")
    print()
    
    # Create test functions and vectors
    functions = create_test_functions()
    test_vectors = create_test_vectors()
    
    # Run verification for each function
    for func_name, func_code in functions.items():
        if func_name in test_vectors:
            run_verification_example(func_name, func_code, test_vectors[func_name])
    
    print(f"\n{'='*60}")
    print("RTL VERIFICATION EXAMPLES COMPLETED")
    print(f"{'='*60}")
    print()
    print("Summary:")
    print("- RTL verification compares generated Verilog with Python execution")
    print("- Uses Verilator for RTL simulation")
    print("- Automatically generates test vectors and testbenches")
    print("- Provides detailed verification reports")
    print()
    print("To enable full RTL verification, ensure Verilator is installed:")
    print("  Ubuntu/Debian: sudo apt-get install verilator")
    print("  macOS: brew install verilator")
    print("  From source: https://verilator.org/guide/latest/install.html")


if __name__ == "__main__":
    main() 