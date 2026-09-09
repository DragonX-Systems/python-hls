#!/usr/bin/env python3
"""
Test script for complex programs to validate HLS compiler functionality.
Tests nested loops, matrix operations, and various algorithmic patterns.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complex_programs(test_indices=None):
    """Test various complex programs.
    
    Args:
        test_indices: Optional list of test indices to run (0-based)
    """
    print("=" * 80)
    print("Testing Complex Programs with HLS Compiler")
    print("=" * 80)
    
    test_cases = [
        {
            "name": "2D Matrix Sum",
            "description": "Sum all elements in a 2D matrix using nested loops",
            "code": """
def matrix_sum(matrix):
    total = 0
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            total += matrix[i][j]
    return total
""",
            "test_data": {"matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
            "expected": 45
        },
        
        {
            "name": "Matrix Multiplication",
            "description": "Multiply two 3x3 matrices",
            "code": """
def matrix_multiply(A, B):
    result = 0
    for i in range(3):
        for j in range(3):
            for k in range(3):
                result += A[i][k] * B[k][j]
    return result
""",
            "test_data": {"A": [[1, 2, 3], [4, 5, 6], [7, 8, 9]], 
                         "B": [[9, 8, 7], [6, 5, 4], [3, 2, 1]]},
            "expected": 900  # Sum of all products
        },
        
        {
            "name": "Bubble Sort",
            "description": "Sort array using bubble sort algorithm",
            "code": """
def bubble_sort_sum(data):
    n = len(data)
    # Create a copy for sorting
    arr = data[:]
    
    # Bubble sort with nested loops
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                # Swap elements
                temp = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
    
    # Return sum of sorted array
    total = 0
    for k in range(n):
        total += arr[k]
    return total
""",
            "test_data": {"data": [64, 34, 25, 12, 22, 11, 90]},
            "expected": 258
        },
        
        {
            "name": "Convolution 1D",
            "description": "1D convolution with nested loops",
            "code": """
def convolution_1d(signal, kernel):
    result_sum = 0
    signal_len = len(signal)
    kernel_len = len(kernel)
    
    # Convolution with nested loops
    for i in range(signal_len - kernel_len + 1):
        conv_value = 0
        for j in range(kernel_len):
            conv_value += signal[i + j] * kernel[j]
        result_sum += conv_value
    
    return result_sum
""",
            "test_data": {"signal": [1, 2, 3, 4, 5], "kernel": [1, 0, -1]},
            "expected": 12  # Sum of convolution results
        },
        
        {
            "name": "Fibonacci Sequence",
            "description": "Generate Fibonacci sequence and return sum",
            "code": """
def fibonacci_sum(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    
    fib = [0] * n
    fib[0] = 0
    fib[1] = 1
    
    for i in range(2, n):
        fib[i] = fib[i-1] + fib[i-2]
    
    total = 0
    for j in range(n):
        total += fib[j]
    
    return total
""",
            "test_data": {"n": 10},
            "expected": 88  # Sum of first 10 Fibonacci numbers
        },
        
        {
            "name": "Prime Sieve",
            "description": "Sieve of Eratosthenes to count primes",
            "code": """
def prime_count(n):
    if n < 2:
        return 0
    
    # Create boolean array
    is_prime = [True] * (n + 1)
    is_prime[0] = False
    is_prime[1] = False
    
    # Sieve algorithm
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n + 1, i):
                is_prime[j] = False
    
    # Count primes
    count = 0
    for k in range(2, n + 1):
        if is_prime[k]:
            count += 1
    
    return count
""",
            "test_data": {"n": 20},
            "expected": 8  # Number of primes up to 20
        }
    ]
    
    # If test_indices is provided, filter the test cases
    if test_indices is not None:
        filtered_test_cases = []
        for idx in test_indices:
            if 0 <= idx < len(test_cases):
                filtered_test_cases.append(test_cases[idx])
        test_cases = filtered_test_cases
    
    results = []
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{i+1}. Testing: {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        print("-" * 60)
        
        # Write test code to file
        filename = f"test_complex_{i+1}.py"
        with open(filename, "w") as f:
            f.write(test_case["code"])
        
        try:
            # Create HLS instance and compile
            hls = HLS()
            print("   🔧 Compiling...")
            
            # Extract function name from code
            lines = test_case["code"].strip().split('\n')
            func_name = None
            for line in lines:
                if line.strip().startswith('def '):
                    func_name = line.strip().split('def ')[1].split('(')[0]
                    break
            
            if not func_name:
                print("   ❌ Could not extract function name")
                continue
            
            result = hls.compile(filename, entry_function=func_name)
            netlist, logs = result
            if netlist and hasattr(netlist, 'modules'):
                for module_name, module in netlist.modules.items():
                    verilog_code = ""
                    if hasattr(module, 'verilog_blocks'):
                        verilog_code = "\n".join(module.verilog_blocks)

                        # Write Verilog code to file
                    verilog_filename = f"test_complex_{i+1}_{module_name}.v"
                    with open(verilog_filename, "w") as vf:
                        vf.write(verilog_code)
            
            if isinstance(result, tuple) and len(result) == 2:
                netlist, logs = result
                print("   ✅ Compilation successful")
                
                # Run RTL verification
                print("   🔧 Running RTL verification...")
                verification_result = hls.verify_rtl(
                    test_vectors=[test_case["test_data"]],
                    num_random_tests=1,
                    save_testbenches=False
                )
                print(verification_result)
                if "verification_results" in verification_result:
                    ver_results = verification_result["verification_results"]
                    module_name = list(ver_results.keys())[0]
                    module_result = ver_results[module_name]
                    
                    if "comparison" in module_result:
                        comparison = module_result["comparison"]
                        total_tests = comparison.get("total_tests", 0)
                        passed = comparison.get("passed", 0)
                        failed = comparison.get("failed", 0)
                        
                        print(f"   📊 Tests: {passed}/{total_tests} passed")
                        
                        # Initialize default values
                        python_result = "N/A"
                        rtl_result = "N/A"
                        expected = test_case["expected"]
                        
                        # Extract results from comparison data
                        if "mismatches" in comparison and comparison["mismatches"]:
                            # Get results from first mismatch
                            mismatch = comparison["mismatches"][0]
                            python_result = mismatch.get("python_result", "N/A")
                            rtl_result = mismatch.get("rtl_result", "N/A")
                            status = "FAIL"
                        elif "test_details" in comparison and comparison["test_details"]:
                            # Get results from test details if available
                            test_detail = comparison["test_details"][0]
                            python_result = test_detail.get("python_result", "N/A")
                            rtl_result = test_detail.get("rtl_result", "N/A")
                            status = "PASS" if passed == total_tests else "FAIL"
                        else:
                            # No detailed results available
                            status = "PASS" if passed == total_tests else "FAIL"
                        
                        # Always save results to file
                        results_filename = f"test_complex_{i+1}_results.txt"
                        with open(results_filename, 'w') as f:
                            f.write(f"TEST RESULTS\n")
                            f.write(f"============\n\n")
                            f.write(f"Test: {test_case['name']}\n")
                            f.write(f"Description: {test_case['description']}\n\n")
                            f.write(f"Test Summary:\n")
                            f.write(f"  Total Tests: {total_tests}\n")
                            f.write(f"  Passed: {passed}\n")
                            f.write(f"  Failed: {failed}\n\n")
                            f.write(f"Results:\n")
                            f.write(f"  Python Result: {python_result}\n")
                            f.write(f"  RTL Result: {rtl_result}\n")
                            f.write(f"  Expected: {expected}\n\n")
                            f.write(f"Status: {status}\n")
                            
                            if "mismatches" in comparison and comparison["mismatches"]:
                                f.write(f"\nMismatch Details:\n")
                                for idx, mismatch in enumerate(comparison["mismatches"]):
                                    f.write(f"  Mismatch {idx+1}:\n")
                                    f.write(f"    Test Vector: {mismatch.get('test_vector', 'N/A')}\n")
                                    f.write(f"    Python: {mismatch.get('python_result', 'N/A')}\n")
                                    f.write(f"    RTL: {mismatch.get('rtl_result', 'N/A')}\n")
                        
                        # Display results
                        print(f"   📋 Results:")
                        print(f"      Python: {python_result}")
                        print(f"      RTL: {rtl_result}")
                        print(f"      Expected: {expected}")
                        print(f"      Results saved to: {results_filename}")
                        
                        if python_result == expected or str(python_result) == str(expected):
                            print("   ✅ Python result matches expected")
                        else:
                            print("   ⚠️  Python result differs from expected")
                        
                        if str(rtl_result) == str(expected):
                            print("   ✅ RTL result matches expected")
                        else:
                            print("   ❌ RTL result differs from expected")
                    else:
                        print("   ❌ No comparison results available")
                        status = "ERROR"
                else:
                    print("   ❌ No verification results available")
                    status = "ERROR"
            else:
                print("   ❌ Compilation failed")
                status = "COMPILE_ERROR"
        
        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")
            status = "EXCEPTION"
        
        finally:
            # Clean up
            if os.path.exists(filename):
                os.remove(filename)
            
            # Clean up generated files
            import glob
            for pattern in [ f"test_complex_{i+1}_*.cpp"]:
                for file_path in glob.glob(pattern):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        results.append({
            "name": test_case["name"],
            "status": status,
            "description": test_case["description"]
        })
    
    # Summary
    print("\n" + "=" * 80)
    print("COMPLEX PROGRAMS TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = len(results)
    
    for i, result in enumerate(results):
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        print(f"{i+1}. {status_icon} {result['name']} - {result['status']}")
    
    print(f"\nOverall Result: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("🎉 All complex programs compiled and verified successfully!")
        return True
    else:
        print("⚠️  Some complex programs had issues")
        return False

if __name__ == "__main__":
    # Check for command-line argument to run a specific test
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        test_index = int(sys.argv[1]) - 1  # Convert to 0-based index
        success = test_complex_programs([test_index])
    else:
        # Run all tests
        success = test_complex_programs()
    
    sys.exit(0 if success else 1) 