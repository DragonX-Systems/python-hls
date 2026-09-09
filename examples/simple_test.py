#!/usr/bin/env python3
"""
Simple test script for the Python-HLS tool.
"""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS


def main():
    """Run a simple test of the HLS tool."""
    print("Python-HLS Simple Test")
    print("=====================")
    
    # Create GCD test function
    test_file = "gcd_test.py"
    with open(test_file, 'w') as f:
        f.write('''
def gcd(a, b):
    """
    Calculate the greatest common divisor of two integers.
    """
    while b:
        a, b = b, a % b
    return a
''')

    # Run HLS at different technology nodes
    tech_nodes = [45, 28, 16, 7]
    results = {}
    
    for node in tech_nodes:
        print(f"\nCompiling with {node}nm technology...")
        
        # Create HLS compiler
        hls = HLS(optimization_level=1, tech_node=node)
        
        # Compile to Verilog
        output_file = f"gcd_{node}nm.v"
        netlist = hls.compile(test_file, target="verilog", output_file=output_file)
        
        # Generate datapath visualization
        if node == 45:  # Only for first node to avoid too many files
            print("Generating visualizations...")
            datapath_file = hls.visualize_datapath()
            scheduled_file = hls.visualize_scheduled_datapath()
            control_file = hls.visualize_control_flow()
            netlist_file = hls.visualize_netlist()
            
            print(f"  Datapath visualization: {datapath_file}")
            print(f"  Scheduled datapath: {scheduled_file}")
            print(f"  Control flow: {control_file}")
            print(f"  Netlist visualization: {netlist_file}")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        results[node] = metrics
        
        # Print summary
        print(f"Performance at {node}nm:")
        print(f"  Area: {metrics['total_area']:.2f} μm²")
        print(f"  Power: {metrics['total_power']:.2f} mW")
        print(f"  Critical path: {metrics['critical_path']:.2f} ns")
        
        # Print module metrics
        for module_name, module_metrics in metrics.items():
            if isinstance(module_metrics, dict) and 'latency' in module_metrics:
                print(f"  Module '{module_name}':")
                print(f"    Latency: {module_metrics['latency']} cycles")
                print(f"    Energy per operation: {module_metrics['energy_per_operation']:.2f} pJ")
    
    # Save results to JSON
    with open("hls_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to hls_results.json")
    
    # Clean up
    os.remove(test_file)
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main() 