#!/usr/bin/env python3
"""
Test script to verify that allocation properly updates execution time when resources are reduced.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
from python_hls.tech.tech_library import TechLibrary

def test_power_optimization_execution_time():
    """Test that power optimization correctly updates execution time when resources are reduced."""
    
    # Create a simple test function with multiple operations
    test_code = """
def matrix_multiply(a, b, c):
    for i in range(4):
        for j in range(4):
            c[i][j] = 0
            for k in range(4):
                c[i][j] += a[i][k] * b[k][j]
    return c
"""
    
    # Write test code to a temporary file
    test_file = "temp_matrix_multiply.py"
    with open(test_file, 'w') as f:
        f.write(test_code)
    
    print("Testing allocation execution time updates...")
    print("=" * 60)
    
    # Test with area optimization (baseline)
    print("\n1. Testing with AREA optimization (baseline):")
    hls_area = HLS()
    hls_area.compile(test_file, "verilog", entry_function="matrix_multiply")
    
    # Get initial execution time
    area_resources = hls_area.allocate_resources(optimization_target="area")
    area_func = hls_area.scheduled_ir.functions["matrix_multiply"]
    area_latency = getattr(area_func, 'total_latency', 0)
    
    print(f"Area optimization:")
    print(f"  Total latency: {area_latency} cycles")
    print(f"  Resources allocated: {sum(area_resources.values())} total")
    print(f"  Key resources: ALU={area_resources.get('ALU_32bit', 0)}, "
          f"Multiplier={area_resources.get('Multiplier_32bit', 0)}, "
          f"Adder={area_resources.get('Adder_32bit', 0)}")
    
    # Test with power optimization (should reduce resources and increase execution time)
    print("\n2. Testing with POWER optimization (should increase execution time):")
    hls_power = HLS()
    hls_power.compile(test_file, "verilog", entry_function="matrix_multiply")
    
    power_resources = hls_power.allocate_resources(optimization_target="power")
    power_func = hls_power.scheduled_ir.functions["matrix_multiply"]
    power_latency = getattr(power_func, 'total_latency', 0)
    
    print(f"Power optimization:")
    print(f"  Total latency: {power_latency} cycles")
    print(f"  Resources allocated: {sum(power_resources.values())} total")
    print(f"  Key resources: ALU={power_resources.get('ALU_32bit', 0)}, "
          f"Multiplier={power_resources.get('Multiplier_32bit', 0)}, "
          f"Adder={power_resources.get('Adder_32bit', 0)}")
    
    # Test with performance optimization (should increase resources and potentially decrease execution time)
    print("\n3. Testing with PERFORMANCE optimization (baseline for comparison):")
    hls_perf = HLS()
    hls_perf.compile(test_file, "verilog", entry_function="matrix_multiply")
    
    perf_resources = hls_perf.allocate_resources(optimization_target="performance")
    perf_func = hls_perf.scheduled_ir.functions["matrix_multiply"]
    perf_latency = getattr(perf_func, 'total_latency', 0)
    
    print(f"Performance optimization:")
    print(f"  Total latency: {perf_latency} cycles")
    print(f"  Resources allocated: {sum(perf_resources.values())} total")
    print(f"  Key resources: ALU={perf_resources.get('ALU_32bit', 0)}, "
          f"Multiplier={perf_resources.get('Multiplier_32bit', 0)}, "
          f"Adder={perf_resources.get('Adder_32bit', 0)}")
    
    # Analysis
    print("\n" + "=" * 60)
    print("ANALYSIS:")
    print("=" * 60)
    
    # Check if power optimization reduced resources
    power_total_compute = (power_resources.get('ALU_32bit', 0) + 
                          power_resources.get('Multiplier_32bit', 0) + 
                          power_resources.get('Adder_32bit', 0))
    area_total_compute = (area_resources.get('ALU_32bit', 0) + 
                         area_resources.get('Multiplier_32bit', 0) + 
                         area_resources.get('Adder_32bit', 0))
    
    print(f"Compute resources comparison:")
    print(f"  Area optimization: {area_total_compute} compute units")
    print(f"  Power optimization: {power_total_compute} compute units")
    
    if power_total_compute < area_total_compute:
        print(f"  ✓ Power optimization reduced compute resources by {area_total_compute - power_total_compute} units")
        
        # Check if execution time increased appropriately
        if power_latency > area_latency:
            latency_increase = (power_latency - area_latency) / area_latency * 100
            print(f"  ✓ Execution time increased by {latency_increase:.1f}% ({area_latency} → {power_latency} cycles)")
            print(f"  ✓ PASS: Power optimization correctly updated execution time!")
        else:
            print(f"  ✗ FAIL: Execution time should have increased but didn't ({area_latency} → {power_latency} cycles)")
    else:
        print(f"  ⚠ Power optimization didn't reduce compute resources significantly")
    
    # Check performance vs others
    print(f"\nLatency comparison:")
    print(f"  Performance: {perf_latency} cycles")
    print(f"  Area: {area_latency} cycles")
    print(f"  Power: {power_latency} cycles")
    
    if perf_latency <= area_latency <= power_latency:
        print(f"  ✓ Latency ordering is correct: Performance ≤ Area ≤ Power")
    else:
        print(f"  ⚠ Latency ordering may not be optimal")
    
    # Clean up temporary file
    os.remove(test_file)
    
    return power_latency > area_latency

def test_simple_function():
    """Test with a simpler function to see the effect more clearly."""
    
    print("\n" + "=" * 60)
    print("SIMPLE FUNCTION TEST:")
    print("=" * 60)
    
    simple_code = """
def simple_compute(x, y, z):
    a = x * y
    b = a + z
    c = b * x
    d = c + y
    e = d * z
    return e
"""
    
    # Write test code to a temporary file
    simple_file = "temp_simple_compute.py"
    with open(simple_file, 'w') as f:
        f.write(simple_code)
    
    print("\nTesting simple function with different optimization targets:")
    
    results = {}
    
    for target in ["area", "power", "performance"]:
        hls = HLS()
        hls.compile(simple_file, "verilog")
        hls.schedule_asap()
        
        resources = hls.allocate_resources(optimization_target=target)
        func = hls.scheduled_ir.functions["simple_compute"]
        latency = getattr(func, 'total_latency', 0)
        
        results[target] = {
            'latency': latency,
            'resources': resources,
            'total_resources': sum(resources.values())
        }
        
        print(f"\n{target.upper()} optimization:")
        print(f"  Latency: {latency} cycles")
        print(f"  Total resources: {sum(resources.values())}")
        print(f"  ALU: {resources.get('ALU_32bit', 0)}, "
              f"Multiplier: {resources.get('Multiplier_32bit', 0)}, "
              f"Adder: {resources.get('Adder_32bit', 0)}")
    
    print(f"\nSimple function analysis:")
    if results['power']['latency'] >= results['area']['latency']:
        print(f"  ✓ Power latency ({results['power']['latency']}) ≥ Area latency ({results['area']['latency']})")
    else:
        print(f"  ✗ Power latency ({results['power']['latency']}) < Area latency ({results['area']['latency']})")
    
    # Clean up temporary file
    os.remove(simple_file)
    
    return results

if __name__ == "__main__":
    print("Testing Allocation Execution Time Updates")
    print("=" * 60)
    
    try:
        # Test the main functionality
        success = test_power_optimization_execution_time()
        
        # Test with simpler function
        simple_results = test_simple_function()
        
        print("\n" + "=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        
        if success:
            print("✓ Main test PASSED: Power optimization correctly updates execution time")
        else:
            print("✗ Main test FAILED: Power optimization did not update execution time correctly")
        
        print("\nThis test verifies that when the allocator reduces resources")
        print("(like in power optimization mode), it properly updates the execution")
        print("time to reflect the increased latency due to resource constraints.")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc() 