#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

def test_fft_no_unroll():
    """Test that FFT compilation doesn't apply unroll naming without explicit unroll pragmas"""
    
    print("Testing FFT compilation without explicit unroll pragmas...")
    
    try:
        # Compile the FFT with optimization level 0 (no automatic optimizations)
        hls = HLS(optimization_level=0)
        netlist = hls.compile('verification_workloads/fft.py')
        
        # Get the resource report
        resource_report = hls.get_resource_report()
        
        print(f"Compilation successful!")
        print(f"Total resources: {resource_report.get('total_resources', 'N/A')}")
        
        # Check if any resources have "unroll" in their names
        unroll_resources = []
        if 'netlist_resources' in resource_report:
            for resource in resource_report['netlist_resources']:
                if 'unroll' in resource.get('name', '').lower():
                    unroll_resources.append(resource['name'])
        
        if unroll_resources:
            print(f"❌ FAIL: Found {len(unroll_resources)} resources with 'unroll' naming:")
            for res_name in unroll_resources[:10]:  # Show first 10
                print(f"  - {res_name}")
            if len(unroll_resources) > 10:
                print(f"  ... and {len(unroll_resources) - 10} more")
            return False
        else:
            print("✅ PASS: No resources have 'unroll' naming patterns")
            
            # Show some example resource names
            if 'netlist_resources' in resource_report:
                print("Example resource names:")
                for i, resource in enumerate(resource_report['netlist_resources'][:5]):
                    print(f"  - {resource.get('name', 'unnamed')}")
            
            return True
            
    except Exception as e:
        print(f"❌ FAIL: Compilation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fft_no_unroll()
    sys.exit(0 if success else 1) 