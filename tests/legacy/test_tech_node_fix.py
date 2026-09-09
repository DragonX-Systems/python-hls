#!/usr/bin/env python3
"""
Test script to verify that technology node changes affect critical path calculation.
"""

import sys
import os

# Add the python_hls directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

def test_gcd_function():
    """Test GCD function with different technology nodes."""
    
    # Create a simple test Python code
    test_code = """
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
"""
    
    # Write test code to a temporary file
    with open('test_gcd.py', 'w') as f:
        f.write(test_code)
    
    print("Testing technology node impact on critical path...")
    print("=" * 60)
    
    # Test different technology nodes
    tech_nodes = [45, 28, 16, 7]
    results = {}
    
    for tech_node in tech_nodes:
        print(f"\nTesting technology node: {tech_node} nm")
        print("-" * 40)
        
        try:
            # Create HLS instance with specific technology node
            hls = HLS(optimization_level=1, tech_node=tech_node)
            
            # Compile the code
            netlist = hls.compile('test_gcd.py', target="verilog", debug=False)
            
            # Get performance metrics
            metrics = hls.get_performance_metrics()
            
            results[tech_node] = {
                'area': metrics['total_area'],
                'power': metrics['total_power'],
                'critical_path': metrics['critical_path'],
                'frequency': metrics['clock_frequency_mhz'],
                'latency_ns': metrics['latency_ns']
            }
            
            print(f"  Area: {metrics['total_area']:.2f} μm²")
            print(f"  Power: {metrics['total_power']:.2f} mW")
            print(f"  Critical path: {metrics['critical_path']:.2f} ns")
            print(f"  Clock frequency: {metrics['clock_frequency_mhz']:.2f} MHz")
            print(f"  Latency: {metrics['latency_ns']:.2f} ns")
            
        except Exception as e:
            print(f"  Error: {e}")
            results[tech_node] = None
    
    # Clean up
    if os.path.exists('test_gcd.py'):
        os.remove('test_gcd.py')
    if os.path.exists('gcd.v'):
        os.remove('gcd.v')
    
    # Analyze results
    print("\n" + "=" * 60)
    print("ANALYSIS:")
    print("=" * 60)
    
    valid_results = {k: v for k, v in results.items() if v is not None}
    
    if len(valid_results) > 1:
        # Check if critical path changes
        critical_paths = [v['critical_path'] for v in valid_results.values()]
        frequencies = [v['frequency'] for v in valid_results.values()]
        
        if len(set(critical_paths)) > 1:
            print("✅ SUCCESS: Critical path varies with technology node!")
            for tech_node, result in valid_results.items():
                print(f"  {tech_node} nm: {result['critical_path']:.2f} ns ({result['frequency']:.2f} MHz)")
        else:
            print("❌ ISSUE: Critical path is the same across all technology nodes")
            print(f"  All nodes have critical path: {critical_paths[0]:.2f} ns")
            
        if len(set(frequencies)) > 1:
            print("✅ SUCCESS: Clock frequency varies with technology node!")
        else:
            print("❌ ISSUE: Clock frequency is the same across all technology nodes")
    else:
        print("❌ Could not get valid results for comparison")
    
    print("\nExpected behavior:")
    print("- Smaller technology nodes should have higher frequencies")
    print("- Smaller technology nodes should have shorter critical paths")
    print("- Area and power should generally decrease with smaller nodes")

if __name__ == "__main__":
    test_gcd_function() 