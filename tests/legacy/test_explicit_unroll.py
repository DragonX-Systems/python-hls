#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

def test_explicit_unroll():
    """Test that unroll naming is applied when explicit unroll pragmas are present"""
    
    # Create test code with explicit unroll pragma
    test_code = '''
def test_unroll_function(data, size):
    result = 0
    
    # pragma hls unroll factor=4
    for i in range(size):
        result += data[i] * 2
    
    return result
'''
    
    with open('test_explicit_unroll_code.py', 'w') as f:
        f.write(test_code)
    
    print("Testing compilation with explicit unroll pragma...")
    
    try:
        # Compile with optimization level 3 (which enables unrolling)
        hls = HLS(optimization_level=3)
        netlist = hls.compile('test_explicit_unroll_code.py')
        
        # Get the allocated resources
        if hasattr(hls, 'allocated_resources') and hls.allocated_resources:
            print(f"\nAllocated resource types:")
            for res_type, count in hls.allocated_resources.items():
                print(f"  {res_type}: {count}")
        
        # Check if unrolling was detected in the IR
        unroll_detected = False
        if hasattr(hls, 'ir') and hls.ir:
            for func_name, func in hls.ir.functions.items():
                for block in func.blocks:
                    if (hasattr(block, 'unroll') and block.unroll and 
                        hasattr(block, 'unroll_factor') and block.unroll_factor > 1):
                        unroll_detected = True
                        print(f"✅ Detected explicit unrolling in block {block.name} with factor {block.unroll_factor}")
                        break
        
        if unroll_detected:
            print("✅ PASS: Explicit unroll pragma was correctly detected")
        else:
            print("❌ FAIL: Explicit unroll pragma was not detected")
            
        return unroll_detected
            
    except Exception as e:
        print(f"❌ FAIL: Compilation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test file
        if os.path.exists('test_explicit_unroll_code.py'):
            os.remove('test_explicit_unroll_code.py')

if __name__ == "__main__":
    success = test_explicit_unroll()
    sys.exit(0 if success else 1) 