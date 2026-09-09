#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

def test_fft_detailed():
    """Test FFT compilation and show detailed resource allocation"""
    
    print("Testing FFT compilation with detailed resource analysis...")
    
    try:
        # Compile the FFT with optimization level 0 (no automatic optimizations)
        hls = HLS(optimization_level=0)
        netlist = hls.compile('verification_workloads/fft.py')
        
        # Get the allocated resources directly from the allocator
        if hasattr(hls, 'allocated_resources') and hls.allocated_resources:
            print(f"\nAllocated resource types:")
            for res_type, count in hls.allocated_resources.items():
                print(f"  {res_type}: {count}")
        
        # Get the netlist resources
        if hasattr(hls, 'netlist') and hls.netlist and hasattr(hls.netlist, 'resources'):
            print(f"\nNetlist resources ({len(hls.netlist.resources)} total):")
            
            # Group by type for cleaner output
            resource_groups = {}
            unroll_resources = []
            
            for resource in hls.netlist.resources:
                res_type = resource.type
                if res_type not in resource_groups:
                    resource_groups[res_type] = []
                resource_groups[res_type].append(resource.name)
                
                # Check for unroll naming
                if 'unroll' in resource.name.lower():
                    unroll_resources.append(resource.name)
            
            # Show resource groups
            for res_type, names in resource_groups.items():
                print(f"  {res_type} ({len(names)}): {names[:3]}{'...' if len(names) > 3 else ''}")
            
            # Check for unroll naming
            if unroll_resources:
                print(f"\n❌ FAIL: Found {len(unroll_resources)} resources with 'unroll' naming:")
                for res_name in unroll_resources[:10]:
                    print(f"  - {res_name}")
                return False
            else:
                print(f"\n✅ PASS: No resources have 'unroll' naming patterns")
                return True
        else:
            print("No netlist resources found")
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Compilation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fft_detailed()
    sys.exit(0 if success else 1) 