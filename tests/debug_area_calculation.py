"""
Debug script to identify issues with resource allocation and area calculation.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("area_calculation_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("area_debug")

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS
from python_hls.tech import TechLibrary, ResourceModel
from python_hls.netlist.netlist import NetlistModule, NetlistResource

def create_test_file(test_dir):
    """Create a simple test file with the GCD algorithm"""
    test_file = os.path.join(test_dir, "test_gcd.py")
    
    with open(test_file, 'w') as f:
        f.write("""
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
""")
    
    return test_file

def debug_resource_allocation(tech_node):
    """Debug resource allocation for a specific technology node"""
    logger.info(f"Debugging resource allocation for {tech_node}nm technology")
    
    # Create temporary directory
    import tempfile
    import shutil
    test_dir = tempfile.mkdtemp()
    
    try:
        # Create test file
        test_file = create_test_file(test_dir)
        
        # Create HLS instance
        hls = HLS(optimization_level=1, tech_node=tech_node)
        
        # Parse Python source to AST
        hls.ast = hls.parser.parse_file(test_file)
        logger.info(f"AST created with {len(ast.dump(hls.ast)) if hls.ast else 0} bytes")
        
        # Generate IR from AST
        hls.ir = hls.ir_generator.generate(hls.ast)
        logger.info(f"IR generated with {len(hls.ir.functions)} function(s)")
        
        # Apply optimizations
        hls.optimized_ir = hls.optimizer.optimize(hls.ir)
        logger.info("Optimizations applied")
        
        # Schedule operations
        hls.scheduled_ir = hls.asap_scheduler.schedule(hls.optimized_ir)
        logger.info("Operations scheduled")
        
        # Allocate resources
        hls.scheduled_ir, hls.allocated_resources = hls.allocator.allocate(
            hls.scheduled_ir, optimization_target="area"
        )
        logger.info(f"Resources allocated: {hls.allocated_resources}")
        
        # Create netlist resources
        hls.netlist_resources = hls.allocator.create_netlist_resources(hls.allocated_resources)
        
        # Log netlist resources details
        logger.info(f"Created {len(hls.netlist_resources)} netlist resources:")
        for i, resource in enumerate(hls.netlist_resources):
            logger.info(f"  Resource {i+1}: {resource.name} ({resource.type})")
            logger.info(f"    Technology node: {resource.technology_node}nm")
            logger.info(f"    Area: {resource.area} μm²")
            logger.info(f"    Power: {resource.power} mW")
        
        # Bind operations to resources
        hls.scheduled_ir, hls.netlist_operations = hls.binder.bind(
            hls.scheduled_ir, hls.allocated_resources, hls.netlist_resources
        )
        logger.info(f"Operations bound to resources: {len(hls.netlist_operations)} operation(s)")
        
        # Generate Verilog
        hls.netlist = hls.verilog_generator.generate(hls.scheduled_ir)
        logger.info(f"Netlist generated with {len(hls.netlist.modules)} module(s)")
        
        # Update netlist technology info
        hls.netlist.technology_node = hls.tech_node
        logger.info(f"Netlist technology node set to {hls.netlist.technology_node}nm")
        
        # Log modules details
        logger.info("Modules details:")
        for module_name, module in hls.netlist.modules.items():
            logger.info(f"  Module: {module_name}")
            logger.info(f"    Resources: {len(module.resources)}")
            logger.info(f"    Area: {module.area} μm²")
            logger.info(f"    Power: {module.power} mW")
            
            # Log resources in module
            if module.resources:
                logger.info("    Resources details:")
                for i, resource in enumerate(module.resources):
                    logger.info(f"      Resource {i+1}: {resource.name} ({resource.type})")
                    logger.info(f"        Technology node: {resource.technology_node}nm")
                    logger.info(f"        Area: {resource.area} μm²")
            else:
                logger.info("    No resources in module!")
        
        # Apply resources manually
        logger.info("Applying resources manually to modules...")
        
        # Reset area and power
        hls.netlist.total_area = 0.0
        hls.netlist.total_power = 0.0
        
        for module_name, module in hls.netlist.modules.items():
            # Clear existing resources
            module.resources.clear()
            module.area = 0.0
            module.power = 0.0
            
            # Add resources explicitly
            for resource in hls.netlist_resources:
                # Get the resource model from the tech library to ensure correct scaling
                resource_model = hls.tech_library.get_resource(resource.type, tech_node=tech_node)
                
                # Create a new resource with correct technology node
                new_resource = NetlistResource(
                    name=resource.name,
                    type=resource.type,
                    bit_width=resource.bit_width,
                    latency=resource.latency,
                    area=resource_model.area,  # Use the area from the tech library
                    power=resource_model.energy_per_op * resource_model.frequency / 1000,
                    technology_node=tech_node,
                    supply_voltage=resource.supply_voltage
                )
                
                # Add the resource to the module
                module.resources.append(new_resource)
                
            # Update module area and power
            module.area = sum(r.area for r in module.resources)
            module.power = sum(r.power for r in module.resources)
            
            # Update netlist total area and power
            hls.netlist.total_area += module.area
            hls.netlist.total_power += module.power
            
            logger.info(f"  Updated module {module_name}:")
            logger.info(f"    Resources: {len(module.resources)}")
            logger.info(f"    Area: {module.area} μm²")
            logger.info(f"    Power: {module.power} mW")
        
        logger.info(f"Updated netlist area: {hls.netlist.total_area} μm²")
        logger.info(f"Updated netlist power: {hls.netlist.total_power} mW")
        
        # Get performance metrics
        metrics = hls.get_performance_metrics()
        
        logger.info("Final metrics:")
        logger.info(f"  Technology node: {metrics['technology_node']}nm")
        logger.info(f"  Total area: {metrics['total_area']} μm²")
        logger.info(f"  Total power: {metrics['total_power']} mW")
        
        return {
            "tech_node": tech_node,
            "allocated_resources": hls.allocated_resources,
            "netlist_resources_count": len(hls.netlist_resources),
            "module_resources": {name: len(module.resources) for name, module in hls.netlist.modules.items()},
            "module_areas": {name: module.area for name, module in hls.netlist.modules.items()},
            "total_area": hls.netlist.total_area,
            "total_power": hls.netlist.total_power,
            "metrics": metrics
        }
    
    finally:
        # Clean up
        shutil.rmtree(test_dir)

def main():
    """Main function to debug area calculation with different technology nodes"""
    # Debug with different technology nodes
    tech_nodes = [45, 28, 16, 7]
    results = {}
    
    for node in tech_nodes:
        results[node] = debug_resource_allocation(node)
    
    # Compare results
    logger.info("\nCOMPARISON OF RESULTS:")
    logger.info("=" * 80)
    
    for node in tech_nodes:
        logger.info(f"{node}nm technology:")
        logger.info(f"  Total area: {results[node]['total_area']} μm²")
        logger.info(f"  Resources: {results[node]['allocated_resources']}")
    
    # Save results to a JSON file
    with open("area_calculation_results.json", "w") as f:
        json.dump(results, f, indent=4, default=lambda x: str(x) if not isinstance(x, (int, float, str, list, dict, bool, type(None))) else x)
    
    logger.info("\nResults saved to area_calculation_results.json")
    
    # Test resource scaling directly
    logger.info("\nTESTING RESOURCE SCALING DIRECTLY:")
    logger.info("=" * 80)
    
    tech_lib = TechLibrary()
    
    for res_type in ["ALU_32bit", "Multiplier_32bit", "Register_32bit"]:
        logger.info(f"Resource: {res_type}")
        
        for node in tech_nodes:
            resource = tech_lib.get_resource(res_type, tech_node=node)
            logger.info(f"  {node}nm: Area = {resource.area} μm²")

if __name__ == "__main__":
    import ast  # Import here for debugging
    main() 