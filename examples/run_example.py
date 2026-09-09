#!/usr/bin/env python3
"""
Example runner for Python-HLS.
"""

import os
import sys
import json
from tabulate import tabulate

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from python_hls import HLS

# Import example functions
from gcd import gcd
from fir_filter import fir_filter
from matrix_multiply import matrix_multiply


def print_separator():
    """Print a separator line."""
    print("\n" + "=" * 80 + "\n")


def run_gcd_example():
    """Run the GCD example."""
    print("Running GCD example...")
    
    # Create an HLS instance
    hls = HLS(optimization_level=1, tech_node=45)
    
    # Compile the GCD code
    gcd_file = os.path.join(current_dir, "gcd.py")
    netlist = hls.compile(gcd_file, target="verilog", output_file="gcd.v")
    
    # Get performance metrics
    metrics = hls.get_performance_metrics()
    print(f"Technology node: {metrics['technology_node']} nm")
    print(f"Area: {metrics['total_area']} μm²")
    print(f"Power: {metrics['total_power']} mW")
    print(f"Critical path: {metrics['critical_path']} ns")
    
    # Generate visualizations
    hls.visualize_datapath(output_file="gcd_datapath.png")
    hls.visualize_scheduled_datapath(output_file="gcd_scheduled_datapath.png")
    hls.visualize_control_flow(output_file="gcd_control.png")
    
    print("GCD example completed.")


def run_fir_filter_example():
    """Run the FIR filter example."""
    print("Running FIR filter example...")
    
    # Create an HLS instance
    hls = HLS(optimization_level=2, tech_node=45)
    
    # Compile the FIR filter code
    fir_file = os.path.join(current_dir, "fir_filter.py")
    netlist = hls.compile(fir_file, target="verilog", output_file="fir_filter.v")
    
    # Get performance metrics
    metrics = hls.get_performance_metrics()
    print(f"Technology node: {metrics['technology_node']} nm")
    print(f"Area: {metrics['total_area']} μm²")
    print(f"Power: {metrics['total_power']} mW")
    print(f"Critical path: {metrics['critical_path']} ns")
    
    # Generate visualizations
    hls.visualize_datapath(output_file="fir_filter_datapath.png")
    hls.visualize_scheduled_datapath(output_file="fir_filter_scheduled_datapath.png")
    hls.visualize_control_flow(output_file="fir_filter_control.png")
    
    print("FIR filter example completed.")


def run_matrix_multiply_example():
    """Run the matrix multiplication example."""
    print("Running matrix multiplication example with scratchpad memory...")
    
    # Create an HLS instance
    hls = HLS(optimization_level=3, tech_node=28)  # Use 28nm for better area/power
    
    # Compile the matrix multiplication code
    matrix_file = os.path.join(current_dir, "matrix_multiply.py")
    netlist = hls.compile(matrix_file, target="verilog", output_file="matrix_multiply.v")
    
    # Get performance metrics
    metrics = hls.get_performance_metrics()
    print(f"Technology node: {metrics['technology_node']} nm")
    print(f"Area: {metrics['total_area']} μm²")
    print(f"Power: {metrics['total_power']} mW")
    print(f"Critical path: {metrics['critical_path']} ns")
    
    # Print resource usage with memory breakdown
    print("\nResource Usage:")
    resources = netlist.get_resource_report()
    
    if "modules" in resources:
        for module_name, module_data in resources["modules"].items():
            print(f"\nModule: {module_name}")
            if "resources" in module_data:
                print("  Resources:")
                for res_type, count in module_data["resources"].items():
                    print(f"    {res_type}: {count}")
    
    # Generate visualizations
    hls.visualize_datapath(output_file="matrix_multiply_datapath.png")
    hls.visualize_scheduled_datapath(output_file="matrix_multiply_scheduled_datapath.png")
    hls.visualize_control_flow(output_file="matrix_multiply_control.png")
    
    print("Matrix multiplication example completed.")


def main():
    """Run all examples."""
    print("Running Python-HLS examples...\n")
    
    # Run GCD example
    run_gcd_example()
    print_separator()
    
    # Run FIR filter example
    run_fir_filter_example()
    print_separator()
    
    # Run matrix multiplication example
    run_matrix_multiply_example()
    print_separator()
    
    print("All examples completed.")


if __name__ == "__main__":
    main() 