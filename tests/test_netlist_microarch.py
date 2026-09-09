"""
Test script for netlist microarchitecture visualization.
"""

import os
import sys
import tempfile
import shutil
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS


def create_gcd_program():
    """Create a simple GCD program for testing."""
    code = """
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
"""
    return code


def create_complex_program():
    """Create a more complex program for testing with arithmetic operations."""
    code = """
def arithmetic_ops(a, b, c):
    # Simple arithmetic operations to generate ALU usage
    x = a + b
    y = a * b
    z = x - y
    result = z / c
    return result
"""
    return code


class TestNetlistMicroarch(unittest.TestCase):
    """Test case for netlist microarchitecture visualization."""
    
    def setUp(self):
        """Set up the test case."""
        # Create a temporary directory for test output
        self.test_dir = tempfile.mkdtemp()
        
        # Create a test source file with GCD program
        self.gcd_file = os.path.join(self.test_dir, "test_gcd.py")
        with open(self.gcd_file, 'w') as f:
            f.write(create_gcd_program())
        
        # Create a test source file with complex program
        self.complex_file = os.path.join(self.test_dir, "test_complex.py")
        with open(self.complex_file, 'w') as f:
            f.write(create_complex_program())
        self.spmd_file = os.path.join(os.path.dirname(__file__), "spmm_512_code.py")
        # Create a directory for visualization output that won't be deleted
        self.output_dir = "visualization_output"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def tearDown(self):
        """Clean up after the test case."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
        # Note: We do NOT delete self.output_dir so the files remain accessible
    
    def test_visualize_gcd_microarch(self):
        """Test the netlist microarchitecture visualization for GCD."""
        # Create an HLS instance
        hls = HLS(optimization_level=0, tech_node=45)  # Use optimization_level=0 to prevent removal of operations
        
        # Compile the GCD program
        netlist = hls.compile(self.gcd_file, target="verilog")
        
        # Generate visualizations with permanent output paths
        datapath_file = hls.visualize_datapath(output_file=os.path.join(self.output_dir, "gcd_datapath.png"))
        scheduled_file = hls.visualize_scheduled_datapath(output_file=os.path.join(self.output_dir, "gcd_scheduled.png"))
        netlist_file = hls.visualize_netlist(output_file=os.path.join(self.output_dir, "gcd_netlist.png"))
        microarch_file = hls.visualize_netlist_microarch(output_file=os.path.join(self.output_dir, "gcd_microarch.png"))
        
        # Check if the visualization files were created
        self.assertTrue(os.path.exists(datapath_file), "Datapath visualization file should exist")
        self.assertTrue(os.path.exists(scheduled_file), "Scheduled datapath visualization file should exist")
        self.assertTrue(os.path.exists(netlist_file), "Netlist visualization file should exist")
        self.assertTrue(os.path.exists(microarch_file), "Microarchitecture visualization file should exist")
        
        print(f"\nGenerated GCD visualization files:")
        print(f"  Datapath:        {datapath_file}")
        print(f"  Scheduled:       {scheduled_file}")
        print(f"  Netlist:         {netlist_file}")
        print(f"  Microarch:       {microarch_file}")
    
    def test_visualize_complex_microarch(self):
        """Test the netlist microarchitecture visualization for the complex example."""
        # Create an HLS instance
        hls = HLS(optimization_level=0, tech_node=45)  # Use optimization_level=0 to prevent removal of operations
        
        # Compile the complex program
        netlist = hls.compile(self.complex_file, target="verilog")
        
        # Generate visualizations with permanent output paths
        datapath_file = hls.visualize_datapath(output_file=os.path.join(self.output_dir, "complex_datapath.png"))
        scheduled_file = hls.visualize_scheduled_datapath(output_file=os.path.join(self.output_dir, "complex_scheduled.png"))
        netlist_file = hls.visualize_netlist(output_file=os.path.join(self.output_dir, "complex_netlist.png"))
        microarch_file = hls.visualize_netlist_microarch(output_file=os.path.join(self.output_dir, "complex_microarch.png"))
        
        # Check if the visualization files were created
        self.assertTrue(os.path.exists(datapath_file), "Datapath visualization file should exist")
        self.assertTrue(os.path.exists(scheduled_file), "Scheduled datapath visualization file should exist")
        self.assertTrue(os.path.exists(netlist_file), "Netlist visualization file should exist")
        self.assertTrue(os.path.exists(microarch_file), "Microarchitecture visualization file should exist")
        
        print(f"\nGenerated complex visualization files:")
        print(f"  Datapath:        {datapath_file}")
        print(f"  Scheduled:       {scheduled_file}")
        print(f"  Netlist:         {netlist_file}")
        print(f"  Microarch:       {microarch_file}")
        
        # Also print the absolute paths for easier access
        print(f"\nAbsolute paths:")
        for file_path in [microarch_file]:
            abs_path = os.path.abspath(file_path)
            print(f"  {os.path.basename(file_path)}: {abs_path}")
    
    def test_visualize_spmm_microarch(self):
        """Test the netlist microarchitecture visualization for the SPMD example."""
        # Create an HLS instance
        hls = HLS(optimization_level=0, tech_node=45)  # Use optimization_level=0 to prevent removal of operations
        
        # Compile the SPMD program  
        netlist = hls.compile(self.spmd_file, target="verilog")
        if hasattr(hls, 'scheduled_ir') and hls.scheduled_ir:
                    # The bigger the matrix, the more resources needed
                    optimization_target = "performance" 
                    # if size >= 512 else "area"
                    hls.allocated_resources = hls.allocator.allocate(
                        hls.scheduled_ir, optimization_target
                    )[1]
                    hls.netlist_resources = hls.allocator.create_netlist_resources(hls.allocated_resources)
                    
                    # Update the netlist resources
                    hls._apply_resources_to_modules()
        # Generate visualizations with permanent output paths
        datapath_file = hls.visualize_datapath(output_file=os.path.join(self.output_dir, "spmd_datapath.png"))
        scheduled_file = hls.visualize_scheduled_datapath(output_file=os.path.join(self.output_dir, "spmd_scheduled.png"))
        netlist_file = hls.visualize_netlist(output_file=os.path.join(self.output_dir, "spmd_netlist.png"))
        microarch_file = hls.visualize_netlist_microarch(output_file=os.path.join(self.output_dir, "spmd_microarch.png"))   
         # Check if the visualization files were created
        self.assertTrue(os.path.exists(datapath_file), "Datapath visualization file should exist")
        self.assertTrue(os.path.exists(scheduled_file), "Scheduled datapath visualization file should exist")
        self.assertTrue(os.path.exists(netlist_file), "Netlist visualization file should exist")
        self.assertTrue(os.path.exists(microarch_file), "Microarchitecture visualization file should exist")
        
        print(f"\nGenerated complex visualization files:")
        print(f"  Datapath:        {datapath_file}")
        print(f"  Scheduled:       {scheduled_file}")
        print(f"  Netlist:         {netlist_file}")
        print(f"  Microarch:       {microarch_file}")
        
        # Also print the absolute paths for easier access
        print(f"\nAbsolute paths:")
        for file_path in [microarch_file]:
            abs_path = os.path.abspath(file_path)
            print(f"  {os.path.basename(file_path)}: {abs_path}")
    

def main():
    """Run the test and keep the visualization files."""
    unittest.main()


if __name__ == "__main__":
    main() 