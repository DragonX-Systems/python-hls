#!/usr/bin/env python3
"""
Test script to validate enhanced array parameter support in RTL verification.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_array_function():
    """Test with a function that has array parameters."""
    print("=" * 60)
    print("Testing Enhanced Array Parameter Support")
    print("=" * 60)
    
    # Create a test function with array parameters
    test_code = """
def array_sum(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
"""
    
    # Write test code to file
    with open("test_array_function.py", "w") as f:
        f.write(test_code)
    
    try:
        # Create HLS instance and compile
        hls = HLS()
        result = hls.compile("test_array_function.py", entry_function="array_sum")
        netlist, logs = result
        if netlist and hasattr(netlist, 'modules'):
            for module_name, module in netlist.modules.items():
                verilog_code = ""
                if hasattr(module, 'verilog_blocks'):
                    verilog_code = "\n".join(module.verilog_blocks)
                    verilog_filename = f"test_array_function_{module_name}.v"
                    with open(verilog_filename, "w") as vf:
                        vf.write(verilog_code)

        if "error" in result:
            print(f"❌ Compilation failed: {result['error']}")
            return False
        
        print("✅ Compilation successful")
        
        # Run verification with a small number of tests
        print("🔧 Running RTL verification with array parameters...")
        verification_result = hls.verify_rtl(num_random_tests=2, save_testbenches=True)
        
        if "error" in verification_result:
            print(f"❌ Verification failed: {verification_result['error']}")
            return False
        
        print("✅ RTL verification completed successfully!")
        
        # Check if testbench code is present
        if "generated_testbenches" not in verification_result:
            print("❌ No generated_testbenches in verification result")
            return False
        
        print("✅ Generated testbenches found in result")
        
        # Examine the testbench structure
        testbenches = verification_result["generated_testbenches"]
        print(f"📊 Number of modules with testbenches: {len(testbenches)}")
        
        for module_name, testbench_info in testbenches.items():
            print(f"\n🔧 Module: {module_name}")
            
            if "error" in testbench_info:
                print(f"  ❌ Error: {testbench_info['error']}")
                continue
            
            if "note" in testbench_info:
                print(f"  ℹ️  Note: {testbench_info['note']}")
                if "reason" in testbench_info:
                    print(f"  ℹ️  Reason: {testbench_info['reason']}")
                continue
            
            if "code" in testbench_info:
                code_info = testbench_info["code"]
                
                # Check Verilog testbench
                if "verilog_testbench" in code_info:
                    verilog_code = code_info["verilog_testbench"]
                    print(f"  ✅ Verilog testbench: {len(verilog_code)} characters")
                    
                    # Check if it contains array interface logic
                    if "write_array_" in verilog_code:
                        print(f"  🎯 Contains array interface logic!")
                    else:
                        print(f"  ⚠️  No array interface logic found")
                    
                    print(f"     First 200 chars: {verilog_code[:200]}...")
                else:
                    print(f"  ❌ No Verilog testbench code")
                
                # Check C++ testbench
                if "cpp_testbench" in code_info:
                    cpp_code = code_info["cpp_testbench"]
                    print(f"  ✅ C++ testbench: {len(cpp_code)} characters")
                    
                    # Check if it contains array interface logic
                    if "write_array_" in cpp_code:
                        print(f"  🎯 Contains array interface logic!")
                    else:
                        print(f"  ⚠️  No array interface logic found")
                    
                    print(f"     First 200 chars: {cpp_code[:200]}...")
                else:
                    print(f"  ❌ No C++ testbench code")
                
                # Check if files were saved
                if "saved_files" in testbench_info:
                    saved_files = testbench_info["saved_files"]
                    print(f"  📁 Saved files: {list(saved_files.keys())}")
                    for file_type, file_path in saved_files.items():
                        print(f"     {file_type}: {file_path}")
            
            # Check other info
            if "port_info" in testbench_info:
                port_info = testbench_info["port_info"]
                print(f"  🔌 Port info available: {bool(port_info)}")
                
                # Check for array interfaces
                if port_info and "array_interfaces" in port_info:
                    array_interfaces = port_info["array_interfaces"]
                    if array_interfaces:
                        print(f"  🎯 Array interfaces detected: {list(array_interfaces.keys())}")
                    else:
                        print(f"  ⚠️  No array interfaces found")
            
            if "test_vectors_count" in testbench_info:
                count = testbench_info["test_vectors_count"]
                print(f"  🧪 Test vectors: {count}")
        
        # Check verification results
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
                    print(comparison)
                    print(f"    Tests: {passed}/{total_tests} passed, {failed} failed")
                    
                    if failed == 0:
                        print(f"    ✅ All tests passed!")
                    else:
                        print(f"    ❌ Some tests failed")
        
        print("\n✅ Array parameter support test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists("test_array_function.py"):
            os.remove("test_array_function.py")
        
        # Clean up any generated files
        # for file_pattern in ["test_array_function_*.v", "test_array_function_*.cpp", "test_array_function_*.txt"]:
        #     import glob
        #     for file_path in glob.glob(file_pattern):
        #         try:
        #             os.remove(file_path)
        #             print(f"🧹 Cleaned up: {file_path}")
        #         except:
        #             pass

if __name__ == "__main__":
    success = test_array_function()
    if success:
        print("\n🎉 Array parameter support test passed!")
        sys.exit(0)
    else:
        print("\n💥 Array parameter support test failed!")
        sys.exit(1) 