"""
Fix for the area calculation issue in the HLS class.

This script adds resource allocation to the HLS compilation process
and ensures that module area values are properly calculated based on 
the technology node.
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS
from python_hls.tech import TechLibrary, ResourceModel
from python_hls.netlist.netlist import NetlistModule


def patch_netlist_module_class():
    """
    Monkey patch the NetlistModule class to correctly calculate area based on resources.
    """
    # Store the original add_resource method
    original_add_resource = NetlistModule.add_resource
    
    # Define a new add_resource method that updates the area
    def patched_add_resource(self, resource):
        # Call the original method first
        original_add_resource(self, resource)
        
        # Update the module's area when a resource is added
        self.area = sum(r.area for r in self.resources)
        self.power = sum(r.power for r in self.resources)
    
    # Replace the original method with our patched version
    NetlistModule.add_resource = patched_add_resource
    
    print("NetlistModule.add_resource has been patched to update area when resources are added.")


def test_tech_nodes_area():
    """
    Test if different technology nodes report different area values.
    """
    # Apply the patch
    patch_netlist_module_class()
    
    # Create a sample Python file for testing
    import tempfile
    import shutil
    
    test_dir = tempfile.mkdtemp()
    test_file = os.path.join(test_dir, "test_gcd.py")
    
    with open(test_file, 'w') as f:
        f.write("""
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
""")
    
    try:
        # Test with 28nm technology
        hls_28nm = HLS(optimization_level=1, tech_node=28)
        netlist_28nm = hls_28nm.compile(test_file, target="verilog")
        metrics_28nm = hls_28nm.get_performance_metrics()
        
        # Test with 7nm technology
        hls_7nm = HLS(optimization_level=1, tech_node=7)
        netlist_7nm = hls_7nm.compile(test_file, target="verilog")
        metrics_7nm = hls_7nm.get_performance_metrics()
        
        # Print the results
        print("\nNetlist Area by Tech Node (after patch):")
        print(f"28nm area: {metrics_28nm['total_area']}")
        print(f"7nm area: {metrics_7nm['total_area']}")
        
        if metrics_28nm['total_area'] > metrics_7nm['total_area']:
            print("SUCCESS: 28nm technology has greater area than 7nm technology, as expected.")
        else:
            print("FAILURE: Area calculation is still incorrect.")
        
        # Save the results to a JSON file
        results = {
            "28nm": {
                "tech_node": 28,
                "total_area": metrics_28nm['total_area'],
                "total_power": metrics_28nm['total_power'],
            },
            "7nm": {
                "tech_node": 7,
                "total_area": metrics_7nm['total_area'],
                "total_power": metrics_7nm['total_power'],
            }
        }
        
        with open("tech_node_results.json", "w") as f:
            json.dump(results, f, indent=4)
        
        print("\nResults have been saved to tech_node_results.json")
    
    finally:
        # Clean up
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix for the area calculation issue in the HLS class.")
    parser.add_argument("--test", action="store_true", help="Run a test to verify the fix")
    
    args = parser.parse_args()
    
    if args.test:
        test_tech_nodes_area()
    else:
        patch_netlist_module_class() 