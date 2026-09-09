#!/usr/bin/env python3
"""
Debug script to examine generated testbench files for array interface timing issues.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging
import shutil

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_array_testbench():
    """Debug the array testbench generation and timing."""
    print("=" * 60)
    print("Debugging Array Testbench Generation")
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
        
        if "error" in result:
            print(f"❌ Compilation failed: {result['error']}")
            return False
        
        print("✅ Compilation successful")
        
        # Run verification with save_testbenches=True
        print("🔧 Running RTL verification...")
        verification_result = hls.verify_rtl(num_random_tests=3, save_testbenches=True)
        
        if "error" in verification_result:
            print(f"❌ Verification failed: {verification_result['error']}")
            return False
        
        # Copy testbench files to permanent location
        testbench_files = []
        for suffix in ["_tb.v", "_tb.cpp", "_verification_report.txt"]:
            src_file = f"test_array_function_array_sum{suffix}"
            if os.path.exists(src_file):
                dst_file = f"debug_array_sum{suffix}"
                shutil.copy2(src_file, dst_file)
                testbench_files.append(dst_file)
                print(f"📁 Copied {src_file} → {dst_file}")
        
        # Examine verification results
        if "verification_results" in verification_result:
            verification_results = verification_result["verification_results"]
            print(f"\n📋 Verification Results:")
            
            for module_name, result in verification_results.items():
                print(f"  Module {module_name}:")
                if "error" in result:
                    print(f"    ❌ Error: {result['error']}")
                else:
                    comparison = result.get("comparison", {})
                    total_tests = comparison.get("total_tests", 0)
                    passed = comparison.get("passed", 0)
                    failed = comparison.get("failed", 0)
                    
                    print(f"    Tests: {passed}/{total_tests} passed, {failed} failed")
                    
                    # Show detailed mismatches
                    if "mismatches" in comparison:
                        print(f"    Mismatches:")
                        for mismatch in comparison["mismatches"]:
                            test_idx = mismatch["test_index"]
                            test_vector = mismatch["test_vector"]
                            python_result = mismatch["python_result"]
                            rtl_result = mismatch["rtl_result"]
                            
                            data_array = test_vector.get("data", [])
                            print(f"      Test {test_idx}: {data_array}")
                            print(f"        Python: {python_result}, RTL: {rtl_result}")
                            
                            # Analyze the pattern
                            if len(data_array) > 1 and rtl_result == data_array[1]:
                                print(f"        🔍 RTL returns data[1] = {data_array[1]}")
                            elif len(data_array) == 1 and rtl_result == data_array[0]:
                                print(f"        ✅ RTL correctly returns data[0] = {data_array[0]}")
                            elif len(data_array) == 0:
                                print(f"        🔍 RTL returns {rtl_result} for empty array (should be 0)")
        
        print(f"\n📁 Generated testbench files: {testbench_files}")
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up source file
        if os.path.exists("test_array_function.py"):
            os.remove("test_array_function.py")

if __name__ == "__main__":
    success = debug_array_testbench()
    if success:
        print("\n🎉 Debug completed successfully!")
        print("📁 Check debug_array_sum_tb.v and debug_array_sum_tb.cpp for details")
    else:
        print("\n💥 Debug failed!") 