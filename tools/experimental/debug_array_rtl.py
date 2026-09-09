#!/usr/bin/env python3
"""
Debug script to test array RTL with simple cases
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging

def debug_simple_array():
    """Debug with a very simple array case."""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create a simple test function
    test_code = """
def array_sum(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
"""
    
    # Write test code to file
    with open("debug_array_function.py", "w") as f:
        f.write(test_code)
    
    try:
        # Create HLS instance and compile
        hls = HLS()
        result = hls.compile("debug_array_function.py", entry_function="array_sum")
        
        print("✅ Compilation successful")
        
        # Test with a very simple case: [1, 2] should return 3
        print("🔧 Testing with simple case: [1, 2]")
        
        # Manually create test vectors
        test_vectors = [{'data': [1, 2]}]
        
        # Run verification with our specific test vector
        verification_result = hls.verify_rtl(
            test_vectors=test_vectors,
            save_testbenches=True
        )
        
        if "error" in verification_result:
            print(f"❌ Verification failed: {verification_result['error']}")
            return False
        
        # Check results
        if "verification_results" in verification_result:
            for module_name, result in verification_result["verification_results"].items():
                print(f"\n📋 Results for {module_name}:")
                if "comparison" in result:
                    comparison = result["comparison"]
                    print(f"  Total tests: {comparison.get('total_tests', 0)}")
                    print(f"  Passed: {comparison.get('passed', 0)}")
                    print(f"  Failed: {comparison.get('failed', 0)}")
                    
                    if "mismatches" in comparison:
                        for mismatch in comparison["mismatches"]:
                            print(f"  ❌ Test {mismatch['test_index']}:")
                            print(f"     Input: {mismatch['test_vector']}")
                            print(f"     Python: {mismatch['python_result']}")
                            print(f"     RTL: {mismatch['rtl_result']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists("debug_array_function.py"):
            os.remove("debug_array_function.py")

if __name__ == "__main__":
    debug_simple_array()