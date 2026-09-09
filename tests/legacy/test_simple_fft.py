#!/usr/bin/env python3
"""
Simple test script to verify the infinite loop fix in the scheduler.
"""

import sys
import os
import logging

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from python_hls import HLS

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_simple_function():
    """Test a simple function to verify no infinite loops"""
    print("Testing simple log2_int function...")
    
    try:
        # Create HLS instance
        hls = HLS(optimization_level=0, tech_node=45)
        
        # Set target function
        hls.target_function = "log2_int"
        
        # Try to compile
        netlist = hls.compile("verification_workloads/fft.py", target="verilog")
        
        if netlist:
            print("✅ SUCCESS: Function compiled without infinite loop!")
            
            # Get metrics
            metrics = hls.get_performance_metrics()
            print(f"   Area: {metrics['total_area']}")
            print(f"   Power: {metrics['total_power']}")
            print(f"   Critical path: {metrics['critical_path']}")
            
            return True
        else:
            print("❌ FAILED: Compilation returned None")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_simple_function()
    if success:
        print("\n🎉 Test passed - no infinite loop detected!")
        sys.exit(0)
    else:
        print("\n💥 Test failed")
        sys.exit(1) 