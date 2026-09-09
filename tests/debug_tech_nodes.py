"""
Test to verify that different technology nodes report different area values.
This includes a debugging function to trace the fix for the technology node scaling issues.
"""

import os
import sys
import unittest
import tempfile
import shutil
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS
from python_hls.tech import TechLibrary, ResourceModel

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tech_nodes_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("tech_nodes_test")

def debug_tech_node_fix():
    """Debug function to verify the technology node area calculation fix"""
    logger.info("Debugging technology node area calculation fix")
    
    # Create temporary directory
    test_dir = tempfile.mkdtemp()
    
    try:
        # Create a more complex test file to ensure operations are generated
        test_file = os.path.join(test_dir, "simple.py")
        with open(test_file, 'w') as f:
            f.write("""
def gcd(a, b):
    # Use Euclidean algorithm which will generate multiple operations
    while b:
        a, b = b, a % b
    return a
""")
        
        # Test with 28nm
        logger.info("Testing with 28nm technology node")
        hls_28nm = HLS(optimization_level=1, tech_node=28)
        netlist_28nm = hls_28nm.compile(test_file, target="verilog")
        metrics_28nm = hls_28nm.get_performance_metrics()
        
        logger.info(f"28nm technology node report:")
        logger.info(f"  Total area: {metrics_28nm['total_area']} μm²")
        logger.info(f"  Technology node: {metrics_28nm['technology_node']} nm")
        
        # List resources in the netlist
        logger.info("Resources in 28nm netlist:")
        for module_name, module in netlist_28nm.modules.items():
            logger.info(f"  Module: {module_name}")
            logger.info(f"  Area: {module.area} μm²")
            
            for i, resource in enumerate(module.resources):
                logger.info(f"    Resource {i+1}: {resource.name} ({resource.type})")
                logger.info(f"      Technology node: {resource.technology_node} nm")
                logger.info(f"      Area: {resource.area} μm²")
        
        # Test with 7nm
        logger.info("Testing with 7nm technology node")
        hls_7nm = HLS(optimization_level=1, tech_node=7)
        netlist_7nm = hls_7nm.compile(test_file, target="verilog")
        metrics_7nm = hls_7nm.get_performance_metrics()
        
        logger.info(f"7nm technology node report:")
        logger.info(f"  Total area: {metrics_7nm['total_area']} μm²")
        logger.info(f"  Technology node: {metrics_7nm['technology_node']} nm")
        
        # List resources in the netlist
        logger.info("Resources in 7nm netlist:")
        for module_name, module in netlist_7nm.modules.items():
            logger.info(f"  Module: {module_name}")
            logger.info(f"  Area: {module.area} μm²")
            
            for i, resource in enumerate(module.resources):
                logger.info(f"    Resource {i+1}: {resource.name} ({resource.type})")
                logger.info(f"      Technology node: {resource.technology_node} nm")
                logger.info(f"      Area: {resource.area} μm²")
        
        # Compare results
        ratio = metrics_28nm['total_area'] / metrics_7nm['total_area'] if metrics_7nm['total_area'] > 0 else "N/A"
        logger.info(f"Area comparison:")
        logger.info(f"  28nm area: {metrics_28nm['total_area']} μm²")
        logger.info(f"  7nm area: {metrics_7nm['total_area']} μm²")
        logger.info(f"  Ratio (28nm/7nm): {ratio}")
        
        # Theoretical ratio based on scaling law: (28/7)²
        theoretical_ratio = (28/7)**2
        logger.info(f"  Theoretical ratio (28/7)²: {theoretical_ratio}")
        
        if metrics_28nm['total_area'] > 0 and metrics_7nm['total_area'] > 0:
            logger.info("✅ Both area values are non-zero")
            if metrics_28nm['total_area'] > metrics_7nm['total_area']:
                logger.info("✅ 28nm area is greater than 7nm area, as expected")
            else:
                logger.info("❌ 28nm area is NOT greater than 7nm area - scaling may still be incorrect")
        else:
            logger.info("❌ At least one area value is zero - scaling is not working")
        
    finally:
        # Clean up
        shutil.rmtree(test_dir)
    
    return metrics_28nm, metrics_7nm

if __name__ == "__main__":
    debug_tech_node_fix() 