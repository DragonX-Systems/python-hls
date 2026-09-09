"""
Integration tests for the HLS class.
"""

import os
import sys
import unittest
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS


class TestHLS(unittest.TestCase):
    """Integration test cases for the HLS class."""
    
    def setUp(self):
        """Set up the test case."""
        # Create a temporary directory for test output
        self.test_dir = tempfile.mkdtemp()
        
        # Sample Python file for testing
        self.test_file = os.path.join(self.test_dir, "test_gcd.py")
        with open(self.test_file, 'w') as f:
            f.write("""
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
""")
    
    def tearDown(self):
        """Clean up after the test case."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_compile_verilog(self):
        """Test compiling to Verilog."""
        hls = HLS(optimization_level=1, tech_node=45)
        output_file = os.path.join(self.test_dir, "gcd.v")
        
        # Compile to Verilog (returns tuple of netlist, logs)
        result = hls.compile(self.test_file, target="verilog", output_file=output_file)
        netlist = result[0] if isinstance(result, tuple) else result
        
        # Check that the netlist was created
        self.assertIsNotNone(netlist)
        
        # Check that the output file was created
        self.assertTrue(os.path.exists(output_file), f"Expected {output_file} to exist")
        
        # Check that the file has content
        with open(output_file, 'r') as f:
            content = f.read()
        self.assertGreater(len(content), 0)
    
    def test_compile_vhdl(self):
        """Test compiling to VHDL."""
        hls = HLS(optimization_level=1, tech_node=45)
        output_file = os.path.join(self.test_dir, "gcd.vhd")
        
        # Compile to VHDL (returns tuple of netlist, logs)
        result = hls.compile(self.test_file, target="vhdl", output_file=output_file)
        netlist = result[0] if isinstance(result, tuple) else result
        
        # Check that the netlist was created
        self.assertIsNotNone(netlist)
        
        # Check that the output file was created
        self.assertTrue(os.path.exists(output_file), f"Expected {output_file} to exist")
        
        # Check that the file has content
        with open(output_file, 'r') as f:
            content = f.read()
        self.assertGreater(len(content), 0)
    
    def test_visualization(self):
        """Test visualization generation."""
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile to Verilog first (returns tuple)
        result = hls.compile(self.test_file, target="verilog")
        netlist = result[0] if isinstance(result, tuple) else result
        
        # Generate visualizations
        datapath_file = hls.visualize_datapath()
        scheduled_file = hls.visualize_scheduled_datapath()
        control_file = hls.visualize_control_flow()
        netlist_file = hls.visualize_netlist()
        
        # For this test, we'll just check if the paths are returned,
        # not if the files actually exist, since they might need graphviz to be installed
        self.assertIsNotNone(datapath_file)
        self.assertIsNotNone(scheduled_file)
        self.assertIsNotNone(control_file)
        self.assertIsNotNone(netlist_file)
    
    def test_different_tech_nodes(self):
        """Test compiling with different technology nodes."""
        # Test with 28nm technology
        hls_28nm = HLS(optimization_level=1, tech_node=28)
        result_28 = hls_28nm.compile(self.test_file, target="verilog")
        netlist_28nm = result_28[0] if isinstance(result_28, tuple) else result_28
        metrics_28nm = hls_28nm.get_performance_metrics()
        
        # Test with 7nm technology
        hls_7nm = HLS(optimization_level=1, tech_node=7)
        result_7 = hls_7nm.compile(self.test_file, target="verilog")
        netlist_7nm = result_7[0] if isinstance(result_7, tuple) else result_7
        metrics_7nm = hls_7nm.get_performance_metrics()
        
        # Both netlists should be created
        self.assertIsNotNone(netlist_28nm)
        self.assertIsNotNone(netlist_7nm)
        
        # Metrics should be valid (latency in cycles)
        self.assertIn("latency_cycles", metrics_28nm)
        self.assertIn("latency_cycles", metrics_7nm)
        
        # Area scaling: 28nm typically has larger area than 7nm (when area > 0)
        if metrics_28nm["total_area"] > 0 and metrics_7nm["total_area"] > 0:
            self.assertGreater(metrics_28nm["total_area"], metrics_7nm["total_area"])


if __name__ == '__main__':
    unittest.main() 