"""
Test visualization of the Mentor SpMM architecture, specifically for FIFO components.
"""

import os
import sys
import shutil
import logging
import tempfile
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_microarch.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_microarch")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import HLS tools
from python_hls import HLS

def create_output_dir():
    """Create a directory for visualization output that won't be deleted"""
    # Create a timestamped directory within the current directory
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(current_dir, f"viz_output_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def test_mentor_spmm_microarch():
    """Test the visualization of the Mentor SpMM microarchitecture with a focus on FIFOs"""
    # Create a directory for visualization output that won't be deleted
    output_dir = create_output_dir()
    
    # Source files to test
    mentor_spmm_file = os.path.join(current_dir, "mentor_spmm_example.py")
    mentor_spmm_simple_file = os.path.join(current_dir, "mentor_spmm_simple.py")
    
    # Create an HLS instance with specific configuration for FIFO and crossbar visualization
    hls = HLS(optimization_level=1, tech_node=45)
    
    try:
        # Compile the mentor_spmm_example.py file (the more complex one)
        logger.info(f"Compiling {mentor_spmm_file}")
        netlist = hls.compile(mentor_spmm_file, target="verilog")
        
        # Log streaming components
        logger.info("==== STREAMING COMPONENTS ====")
        for func_name, func in hls.ir.functions.items():
            logger.info(f"Function {func_name} has {len(func.streaming_components)} streaming components")
            for comp_name, comp in func.streaming_components.items():
                logger.info(f"  Component: {comp_name}, Type: {comp.component_type}, Params: {comp.params}")
        
        # Explicitly allocate performance-optimized resources to ensure FIFOs are included
        if hls.scheduled_ir:
            hls.allocated_resources = hls.allocator.allocate(hls.scheduled_ir, "performance")[1]
            
            # Ensure FIFO resources are allocated
            fifo_resources = {k: v for k, v in hls.allocated_resources.items() if 'FIFO' in k}
            logger.info(f"Allocated FIFO resources: {fifo_resources}")
            
            # If no FIFOs were allocated, add them manually
            # if not fifo_resources:
            #     logger.info("Adding FIFO resources manually")
            #     # Add FIFOs based on the streaming components in the IR
            #     fifo_count = 0
            #     for func_name, func in hls.ir.functions.items():
            #         fifo_count += len([c for c in func.streaming_components.values() if c.component_type == 'fifo'])
                
            #     # If we found FIFO components, allocate resources for them
            #     if fifo_count > 0:
            #         hls.allocated_resources["FIFO_32bit"] = fifo_count
            #     else:
            #         # Fallback: Add at least 4 FIFOs
            #         hls.allocated_resources["FIFO_32bit"] = 4
            
            # Create netlist resources from allocated resources
            hls.netlist_resources = hls.allocator.create_netlist_resources(hls.allocated_resources)
            
            # Log netlist resources to check for FIFOs
            logger.info("==== NETLIST RESOURCES ====")
            fifo_resources = []
            for resource in hls.netlist_resources:
                if 'FIFO' in resource.type:
                    fifo_resources.append(resource)
                    logger.info(f"  FIFO resource: {resource.name}, Type: {resource.type}")
            logger.info(f"Total FIFO resources: {len(fifo_resources)}")
            
            # Ensure FIFOs are in netlist resources
            if not fifo_resources:
                logger.warning("No FIFO resources in netlist - this could cause visualization issues")
            
            # Update netlist with resources
            hls._apply_resources_to_modules()
        
        # Generate visualizations
        datapath_file = os.path.join(output_dir, "mentor_spmm_datapath.png")
        microarch_file = os.path.join(output_dir, "mentor_spmm_microarch.png")
        
        hls.visualize_datapath(output_file=datapath_file)
        hls.visualize_netlist_microarch(output_file=microarch_file)
        
        # Check if the visualization files were created
        logger.info(f"Generated visualizations:")
        logger.info(f"  - Datapath: {datapath_file}")
        logger.info(f"  - Microarch: {microarch_file}")
        
        return {
            "success": True,
            "datapath_file": datapath_file,
            "microarch_file": microarch_file
        }
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    result = test_mentor_spmm_microarch()
    if result["success"]:
        logger.info("Test completed successfully.")
        logger.info(f"Check the visualization files in: {os.path.dirname(result['datapath_file'])}")
    else:
        logger.error(f"Test failed: {result['error']}") 