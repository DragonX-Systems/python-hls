#!/usr/bin/env python3
"""
Simple test to isolate the array sum timing issue.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import shutil

def test_simple_array():
    """Test with a simple 2-element array."""
    print("=" * 60)
    print("Simple Array Test: [5, 10]")
    print("Expected: 15, RTL should return: 15")
    print("=" * 60)
    
    # Create test function
    test_code = """
def array_sum(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
"""
    
    with open("test_array_function.py", "w") as f:
        f.write(test_code)
    
    try:
        # Compile
        hls = HLS()
        result = hls.compile("test_array_function.py", entry_function="array_sum")
        print("✅ Compilation successful")
        
        # Create a simple test with just [5, 10]
        simple_test_vectors = [
            {"data": [5, 10]},     # Expected: 15
            {"data": [100]},       # Expected: 100
            {"data": []},          # Expected: 0
        ]
        
        # Run verification
        verification_result = hls.verify_rtl(test_vectors=simple_test_vectors, save_testbenches=True)
        
        # Copy files for analysis
        for suffix in ["_tb.v", "_tb.cpp"]:
            src_file = f"test_array_function_array_sum{suffix}"
            if os.path.exists(src_file):
                dst_file = f"debug_simple{suffix}"
                shutil.copy2(src_file, dst_file)
                print(f"📁 Copied {src_file} → {dst_file}")
        
        # Show results
        if "verification_results" in verification_result:
            results = verification_result["verification_results"]["array_sum"]
            if "comparison" in results:
                comparison = results["comparison"]
                print(f"\n📋 Results:")
                print(f"  Total tests: {comparison['total_tests']}")
                print(f"  Passed: {comparison['passed']}")
                print(f"  Failed: {comparison['failed']}")
                
                if "mismatches" in comparison:
                    for mismatch in comparison["mismatches"]:
                        test_vector = mismatch["test_vector"]
                        python_result = mismatch["python_result"]
                        rtl_result = mismatch["rtl_result"]
                        data = test_vector["data"]
                        
                        print(f"\n  Test: {data}")
                        print(f"    Python: {python_result}")
                        print(f"    RTL: {rtl_result}")
                        
                        if len(data) > 1 and rtl_result == data[1]:
                            print(f"    🔍 RTL returns data[1] = {data[1]} (WRONG!)")
                        elif len(data) == 1 and rtl_result == data[0]:
                            print(f"    ✅ RTL correctly returns data[0] = {data[0]}")
                        elif len(data) == 0 and rtl_result == 0:
                            print(f"    ✅ RTL correctly returns 0 for empty array")
                        else:
                            print(f"    ❓ Unexpected RTL result")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if os.path.exists("test_array_function.py"):
            os.remove("test_array_function.py")

if __name__ == "__main__":
    success = test_simple_array()
    if success:
        print("\n✅ Simple test completed")
    else:
        print("\n❌ Simple test failed") 