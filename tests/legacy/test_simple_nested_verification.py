#!/usr/bin/env python3
"""
Simple test to verify basic nested loop functionality with detailed RTL verification.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_simple_nested_loops():
    """Test simple nested loop functionality."""
    print("=" * 60)
    print("Testing Simple Nested Loop Functionality")
    print("=" * 60)
    
    # Simple 2D array sum test
    test_code = """
def matrix_sum(matrix):
    total = 0
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            total += matrix[i][j]
    return total
"""
    
    # Write test code to file
    with open("test_matrix_sum.py", "w") as f:
        f.write(test_code)
    
    try:
        # Create HLS instance and compile
        hls = HLS()
        result = hls.compile("test_matrix_sum.py", entry_function="matrix_sum")
        
        if "error" in result:
            print(f"❌ Compilation failed: {result['error']}")
            return False
        
        print("✅ Compilation successful")
        
        # Run verification with detailed output
        print("🔧 Running RTL verification...")
        verification_result = hls.verify_rtl(num_random_tests=3, save_testbenches=True)
        
        if "error" in verification_result:
            print(f"❌ Verification failed: {verification_result['error']}")
            return False
        
        print("✅ RTL verification completed!")
        
        # Show detailed results
        if "verification_results" in verification_result:
            verification_results = verification_result["verification_results"]
            
            for module_name, result in verification_results.items():
                print(f"\n📋 Module: {module_name}")
                
                if "error" in result:
                    print(f"  ❌ Error: {result['error']}")
                    return False
                
                if "comparison" in result:
                    comparison = result["comparison"]
                    total_tests = comparison.get("total_tests", 0)
                    passed = comparison.get("passed", 0)
                    failed = comparison.get("failed", 0)
                    
                    print(f"  📊 Test Results:")
                    print(f"    Total tests: {total_tests}")
                    print(f"    Passed: {passed}")
                    print(f"    Failed: {failed}")
                    
                    if failed == 0:
                        print(f"    ✅ All tests passed!")
                    else:
                        print(f"    ❌ {failed} tests failed")
                        
                        # Show failure details
                        if "failed_tests" in comparison:
                            for i, failure in enumerate(comparison["failed_tests"][:2]):
                                print(f"      Test {i+1} failure:")
                                print(f"        Input: {failure.get('input', 'N/A')}")
                                print(f"        Expected: {failure.get('expected', 'N/A')}")
                                print(f"        Got: {failure.get('actual', 'N/A')}")
                        
                        return False
                
                # Show successful test examples
                if "successful_tests" in result:
                    successful_tests = result["successful_tests"]
                    print(f"  ✅ Example successful tests:")
                    for i, test in enumerate(successful_tests[:2]):
                        print(f"    Test {i+1}:")
                        print(f"      Input: {test.get('input', 'N/A')}")
                        print(f"      Expected: {test.get('expected', 'N/A')}")
                        print(f"      Got: {test.get('actual', 'N/A')}")
        
        # Check generated code complexity
        if "generated_code" in result:
            verilog_code = result["generated_code"].get("verilog", "")
            if verilog_code:
                # Count FSM states and other complexity metrics
                fsm_states = verilog_code.count("FSM_")
                always_blocks = verilog_code.count("always @")
                loop_counters = verilog_code.count("loop_counter")
                
                print(f"\n📊 Generated Verilog Analysis:")
                print(f"  FSM states: {fsm_states}")
                print(f"  Always blocks: {always_blocks}")
                print(f"  Loop counters: {loop_counters}")
                print(f"  Total lines: {len(verilog_code.splitlines())}")
                
                # Check for our FSM timing fix
                if "FSM_LOOP_BODY" in verilog_code and "FSM_LOOP_UPDATE" in verilog_code:
                    print(f"  ✅ Contains proper FSM loop structure")
                else:
                    print(f"  ⚠️  May not have proper FSM loop structure")
        
        print("\n🎉 Simple nested loop test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists("test_matrix_sum.py"):
            os.remove("test_matrix_sum.py")

if __name__ == "__main__":
    success = test_simple_nested_loops()
    if success:
        print("\n✅ Nested loop verification test passed!")
        sys.exit(0)
    else:
        print("\n❌ Nested loop verification test failed!")
        sys.exit(1) 