#!/usr/bin/env python3
"""
Test that verify_rtl returns all generated testbench code.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_simple_function():
    """Test with a simple function to verify testbench code is returned."""
    print("=" * 60)
    print("Testing Testbench Code Return")
    print("=" * 60)
    
    # Create a simple test function
    test_code = """
def simple_add(a, b):
    return a + b
"""
    
    # Write test code to file
    with open("test_simple.py", "w") as f:
        f.write(test_code)
    
    try:
        # Create HLS instance and compile
        hls = HLS()
        result = hls.compile("test_simple.py", entry_function="simple_add")
        
        if "error" in result:
            print(f"❌ Compilation failed: {result['error']}")
            return False
        
        print("✅ Compilation successful")
        
        # Run verification with a small number of tests
        verification_result = hls.verify_rtl(num_random_tests=3, save_testbenches=True)
        
        if "error" in verification_result:
            print(f"❌ Verification failed: {verification_result['error']}")
            return False
        
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
            
            if "code" in testbench_info:
                code_info = testbench_info["code"]
                
                # Check Verilog testbench
                if "verilog_testbench" in code_info:
                    verilog_code = code_info["verilog_testbench"]
                    print(f"  ✅ Verilog testbench: {len(verilog_code)} characters")
                    print(f"     First 100 chars: {verilog_code[:100]}...")
                else:
                    print(f"  ❌ No Verilog testbench code")
                
                # Check C++ testbench
                if "cpp_testbench" in code_info:
                    cpp_code = code_info["cpp_testbench"]
                    print(f"  ✅ C++ testbench: {len(cpp_code)} characters")
                    print(f"     First 100 chars: {cpp_code[:100]}...")
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
            
            if "test_vectors_count" in testbench_info:
                count = testbench_info["test_vectors_count"]
                print(f"  🧪 Test vectors: {count}")
        
        print("\n✅ Testbench code return test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists("test_simple.py"):
            os.remove("test_simple.py")
        
        # Clean up any generated files
        for file_pattern in ["test_simple_*.v", "test_simple_*.cpp", "test_simple_*.txt"]:
            import glob
            for file_path in glob.glob(file_pattern):
                try:
                    os.remove(file_path)
                    print(f"🧹 Cleaned up: {file_path}")
                except:
                    pass

if __name__ == "__main__":
    success = test_simple_function()
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1) 