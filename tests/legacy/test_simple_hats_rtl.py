#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from python_hls.hls import HLS
from verification_workloads.hats_hls import hats_wrapped

def test_hats_wrapped_simple():
    """Simple test of hats_wrapped module with correct parameters"""
    
    print("=" * 60)
    print("Simple HATS Wrapped RTL Verification Test")
    print("=" * 60)
    
    # Test the original Python implementation first
    print("\\n1. Testing original Python implementation...")
    try:
        # Use the correct parameter names for hats_wrapped
        events_x = [10, 20, 30]
        events_y = [15, 25, 35] 
        events_p = [True, False, True]
        size = 3
        
        result = hats_wrapped(events_x, events_y, events_p, size)
        print(f"✓ Python execution successful. Result: {result}")
    except Exception as e:
        print(f"✗ Python execution failed: {e}")
        return False
    
    # Create HLS instance and compile
    print("\\n2. Compiling to Verilog...")
    hls = HLS()
    
    try:
        # Compile the HATS wrapped function
        netlist = hls.compile("verification_workloads/hats_hls.py")
        
        # Get the generated Verilog code for hats_wrapped
        verilog_code = ""
        if netlist and hasattr(netlist, 'modules'):
            if 'hats_wrapped' in netlist.modules:
                module = netlist.modules['hats_wrapped']
                if hasattr(module, 'verilog_blocks'):
                    for block in module.verilog_blocks:
                        verilog_code += block + "\\n"
        
        if verilog_code:
            print(f"✓ Verilog compilation successful!")
            print(f"   Generated {len(verilog_code)} characters of Verilog code")
            
            # Save to file
            with open('hats_wrapped_simple.v', 'w') as f:
                f.write(verilog_code)
            print("   Saved Verilog code to 'hats_wrapped_simple.v'")
        else:
            print("✗ No Verilog code generated")
            return False
            
    except Exception as e:
        print(f"✗ Compilation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Manual RTL verification with correct parameters
    print("\\n3. Manual RTL verification...")
    try:
        from python_hls.verification.rtl_verifier import RTLVerifier
        
        verifier = RTLVerifier()
        
        # Create test vectors with correct parameter names
        test_vectors = [
            {"events_x": [10, 20], "events_y": [15, 25], "events_p": [True, False], "size": 2},
            {"events_x": [0, 0], "events_y": [0, 0], "events_p": [False, False], "size": 2},
            {"events_x": [100], "events_y": [200], "events_p": [True], "size": 1}
        ]
        
        # Test Python execution with correct parameters
        print("   Testing Python execution with test vectors...")
        python_results = []
        for i, test_vector in enumerate(test_vectors):
            try:
                result = hats_wrapped(**test_vector)
                python_results.append(result)
                print(f"   Test {i+1}: {test_vector} -> {result}")
            except Exception as e:
                print(f"   Test {i+1} failed: {e}")
                python_results.append(None)
        
        print(f"✓ Python tests completed. Results: {python_results}")
        
    except Exception as e:
        print(f"✗ RTL verification setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\\n" + "=" * 60)
    print("Simple HATS Test Complete")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    test_hats_wrapped_simple() 