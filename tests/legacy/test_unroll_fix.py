#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

def test_no_auto_unroll():
    """Test that loop_count pragma doesn't trigger automatic unrolling"""
    
    # Create test code with only loop_count pragma (no unroll pragma)
    test_code = '''
def simple_loop(data, size):
    result = 0
    
    # pragma loop_count 8
    for i in range(size):
        result += data[i] * 2
    
    return result
'''
    
    with open('test_simple_loop.py', 'w') as f:
        f.write(test_code)
    
    try:
        # Compile with optimization level 3 (which enables unrolling)
        hls = HLS(optimization_level=3)
        netlist = hls.compile('test_simple_loop.py')
        
        # Get unrolling report
        unroll_report = hls.get_loop_unrolling_report()
        
        print("Unroll report:", unroll_report)
        
        # Check that no loops were unrolled
        unrolled_count = unroll_report.get('unrolled_loops', 0)
        if unrolled_count == 0:
            print("✅ SUCCESS: No automatic unrolling occurred with loop_count pragma")
        else:
            print(f"❌ FAILED: {unrolled_count} loops were automatically unrolled")
            
        # Show details
        for loop in unroll_report.get('loops', []):
            print(f"Loop: {loop['loop_name']}, Unrolled: {loop['is_unrolled']}")
            
    finally:
        # Cleanup
        if os.path.exists('test_simple_loop.py'):
            os.remove('test_simple_loop.py')

if __name__ == "__main__":
    test_no_auto_unroll() 