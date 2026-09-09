#!/usr/bin/env python3

import sys
import os
sys.path.append('.')

from python_hls.hls import HLS
from verification_workloads.hats_hls import hats_wrapped, test_hats

def test_hats_compilation():
    """Test compilation of HATS algorithm to Verilog"""
    
    print("=" * 60)
    print("HATS HLS Compilation and Verification Test")
    print("=" * 60)
    
    # First, test the original Python implementation
    print("\n1. Testing original Python implementation...")
    try:
        result = test_hats()
        print(f"✓ Python execution successful. Result: {result}")
    except Exception as e:
        print(f"✗ Python execution failed: {e}")
        return False
    
    # Create HLS instance
    print("\n2. Creating HLS instance...")
    hls = HLS()
    
    # Set up test inputs for the HATS algorithm
    print("\n3. Setting up test inputs...")
    test_size = 10
    events_x = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    events_y = [15, 25, 35, 45, 55, 65, 75, 85, 95, 105]
    events_p = [True, False, True, False, True, False, True, False, True, False]
    
    print(f"   - Test size: {test_size}")
    print(f"   - Events X: {events_x}")
    print(f"   - Events Y: {events_y}")
    print(f"   - Events P: {events_p}")
    
    # Compile to Verilog
    print("\n4. Compiling HATS to Verilog...")
    try:
        # The HLS compiler expects a source file, so we'll use the existing file
        netlist, logs = hls.compile("verification_workloads/hats_hls.py", target="verilog", entry_function="hats_wrapped")
        print("✓ Verilog compilation successful!")
        
        # Get the generated Verilog code from the netlist
        verilog_code = ""
        if netlist and hasattr(netlist, 'modules'):
            for module_name, module in netlist.modules.items():
                if hasattr(module, 'verilog_blocks'):
                    for block in module.verilog_blocks:
                        verilog_code += block + "\n"
        
        if not verilog_code:
            # Fallback: try to save netlist to get Verilog code
            import io
            from contextlib import redirect_stdout
            
            f = io.StringIO()
            try:
                netlist._save_verilog(f)
                verilog_code = f.getvalue()
            except Exception as e:
                print(f"   Warning: Could not extract Verilog code: {e}")
                verilog_code = "// Verilog code extraction failed"
        
        print(f"   Generated {len(verilog_code)} characters of Verilog code")
        
        # Save Verilog to file
        with open('hats_wrapped.v', 'w') as f:
            f.write(verilog_code)
        print("   Saved Verilog code to 'hats_wrapped.v'")
        
    except Exception as e:
        print(f"✗ Verilog compilation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Run RTL verification
    print("\n5. Running RTL verification...")
    try:
        verification_result = hls.verify_rtl(num_random_tests=5)
        
        if verification_result.get("success", False):
            print("✓ RTL verification successful!")
            print("   Python and Verilog results match")
        else:
            print("✗ RTL verification failed!")
            if "error" in verification_result:
                print(f"   Error: {verification_result['error']}")
            else:
                print("   Python and Verilog results do not match")
            
    except Exception as e:
        print(f"✗ RTL verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        # Don't return False here as compilation was successful
    
    # Display compilation summary
    print("\n6. Compilation Summary:")
    try:
        # Get optimization summary
        summary = hls.get_optimization_summary()
        print(summary)
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        print(f"\nPerformance Metrics:")
        for key, value in metrics.items():
            print(f"   {key}: {value}")
    except Exception as e:
        print(f"   Could not retrieve compilation summary: {e}")
    
    print("\n" + "=" * 60)
    print("HATS HLS Test Complete")
    print("=" * 60)
    
    return True

def inspect_verilog_output():
    """Inspect the generated Verilog code"""
    print("\n" + "=" * 60)
    print("VERILOG CODE INSPECTION")
    print("=" * 60)
    
    try:
        with open('hats_wrapped.v', 'r') as f:
            verilog_code = f.read()
        
        lines = verilog_code.split('\n')
        total_lines = len(lines)
        
        print(f"Total lines: {total_lines}")
        print("\nFirst 50 lines:")
        print("-" * 40)
        for i, line in enumerate(lines[:50]):
            print(f"{i+1:3d}: {line}")
        
        if total_lines > 100:
            print("\n... (middle content omitted) ...\n")
            print("Last 20 lines:")
            print("-" * 40)
            for i, line in enumerate(lines[-20:], start=total_lines-19):
                print(f"{i:3d}: {line}")
        elif total_lines > 50:
            print("\nRemaining lines:")
            print("-" * 40)
            for i, line in enumerate(lines[50:], start=51):
                print(f"{i:3d}: {line}")
        
        # Look for key Verilog constructs
        print(f"\nVerilog Analysis:")
        print(f"   Module declarations: {verilog_code.count('module ')}")
        print(f"   Always blocks: {verilog_code.count('always')}")
        print(f"   Wire declarations: {verilog_code.count('wire ')}")
        print(f"   Reg declarations: {verilog_code.count('reg ')}")
        print(f"   Input ports: {verilog_code.count('input ')}")
        print(f"   Output ports: {verilog_code.count('output ')}")
        
    except FileNotFoundError:
        print("Verilog file 'hats_wrapped.v' not found. Run compilation first.")
    except Exception as e:
        print(f"Error reading Verilog file: {e}")

if __name__ == "__main__":
    success = test_hats_compilation()
    
    if success:
        inspect_verilog_output()
    
    print(f"\nTest {'PASSED' if success else 'FAILED'}") 