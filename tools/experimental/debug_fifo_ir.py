#!/usr/bin/env python
"""
Debug script to trace FIFO and crossbar creation in the IR generator.

This script compiles the mentor_spmm_simple.py file with detailed logging
to debug why FIFOs and crossbars aren't showing up in the microarchitecture.
"""

import os
import sys
import logging
import inspect
import ast
from pprint import pformat

# Set up more verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug_fifo_ir.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("debug_fifo_ir")

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    # Import HLS tools
    from python_hls import HLS
    from python_hls.ir.ir_generator import IRGenerator
    
    # Enhanced pragma debugging - extract all pragmas from the source code
    def extract_pragmas_from_file(filepath):
        """Extract and log all pragmas from the source file"""
        logger.info(f"Extracting pragmas from {filepath}")
        with open(filepath, 'r') as f:
            source = f.read()
        
        # Parse the source code
        tree = ast.parse(source)
        
        # Look for comments that might be pragmas
        pragma_lines = []
        for line in source.split('\n'):
            line = line.strip()
            if line.startswith('#pragma hls'):
                pragma_lines.append(line)
        
        logger.info(f"Found {len(pragma_lines)} pragmas in source code")
        for i, pragma in enumerate(pragma_lines):
            logger.info(f"Pragma {i+1}: {pragma}")
        
        return pragma_lines
    
    # Define a special debug handler for tracking FIFO and crossbar creation
    original_parse_pragma = IRGenerator._parse_pragma if hasattr(IRGenerator, '_parse_pragma') else None
    original_add_streaming_component = IRGenerator.add_streaming_component if hasattr(IRGenerator, 'add_streaming_component') else None
    
    # Track pragma parsing in more detail
    all_pragmas_seen = []
    
    # Patch IRGenerator methods to add more detailed logging
    if original_parse_pragma:
        def debug_parse_pragma(self, node):
            """Enhanced logging for pragma parsing"""
            pragma_text = getattr(node, 'value', '')
            if isinstance(pragma_text, str):
                all_pragmas_seen.append(pragma_text)
                
            logger.debug(f"Parsing pragma: '{pragma_text}'")
            
            # Check if this is a FIFO or crossbar pragma
            if 'fifo' in str(pragma_text).lower():
                logger.info(f"Found FIFO pragma: '{pragma_text}'")
            elif 'crossbar' in str(pragma_text).lower():
                logger.info(f"Found crossbar pragma: '{pragma_text}'")
            
            result = original_parse_pragma(self, node)
            logger.debug(f"Pragma parsing result: {result}")
            return result
        
        IRGenerator._parse_pragma = debug_parse_pragma
    
    if original_add_streaming_component:
        def debug_add_streaming_component(self, comp_type, comp_name, attributes=None):
            """Enhanced logging for streaming component addition"""
            logger.info(f"Adding streaming component: {comp_type} '{comp_name}' with attributes {attributes}")
            caller_frame = inspect.currentframe().f_back
            if caller_frame:
                caller_info = inspect.getframeinfo(caller_frame)
                logger.debug(f"Called from: {caller_info.filename}:{caller_info.lineno}")
            
            result = original_add_streaming_component(self, comp_type, comp_name, attributes)
            logger.info(f"Added streaming component result: {result}")
            
            # Log the current state of streaming_components
            if hasattr(self, 'streaming_components'):
                logger.debug(f"Current streaming components: {pformat(self.streaming_components)}")
            
            return result
        
        IRGenerator.add_streaming_component = debug_add_streaming_component
    
    # Debug the allocation of resources from streaming components
    if hasattr(HLS, 'allocator') and hasattr(HLS.allocator, 'allocate'):
        original_allocate = HLS.allocator.allocate
        
        def debug_allocate(self, *args, **kwargs):
            """Enhanced logging for resource allocation"""
            logger.debug(f"Allocating resources with args: {args} and kwargs: {kwargs}")
            result = original_allocate(self, *args, **kwargs)
            logger.debug(f"Allocation result summary: {result[0]}")
            return result
        
        HLS.allocator.allocate = debug_allocate
    
    # Run the compilation with detailed logging
    logger.info("=" * 80)
    logger.info("Starting debug compilation of mentor_spmm_simple.py")
    logger.info("=" * 80)
    
    # Extract and log all pragmas from the source file first
    filepath = os.path.join(current_dir, "mentor_spmm_simple.py")
    extract_pragmas_from_file(filepath)
    
    # Create an HLS instance with optimization_level=0 to prevent removal of operations
    hls = HLS(optimization_level=0, tech_node=45)
    
    # Set configuration to emphasize FIFOs and crossbars
    hls.config = {
        "visualize": {
            "show_fifos": True,
            "show_crossbars": True,
            "highlight_communication": True
        },
        "ir_generator": {
            "debug_streaming": True,
            "trace_streaming_components": True,
            "detect_pragmas": True,  # Make sure pragma detection is enabled
            "log_all_pragmas": True  # Extra pragma logging
        }
    }
    
    # Compile the mentor_spmm_simple.py file
    netlist = hls.compile(filepath, target="verilog")
    
    # Log all pragmas that were seen during parsing
    logger.info(f"Total pragmas processed during compilation: {len(all_pragmas_seen)}")
    for i, pragma in enumerate(all_pragmas_seen):
        logger.info(f"Processed pragma {i+1}: {pragma}")
    
    # Print streaming components from IR
    if hasattr(hls, 'ir_generator') and hasattr(hls.ir_generator, 'streaming_components'):
        logger.info(f"IR Generator streaming components: {pformat(hls.ir_generator.streaming_components)}")
    
    # Log allocated resources
    if hasattr(hls, 'allocated_resources'):
        logger.info(f"Allocated resources count: {len(hls.allocated_resources)}")
        
        # Count resources by type
        resource_types = {}
        for resource in hls.allocated_resources:
            resource_type = getattr(resource, 'type', None) or getattr(resource, 'resource_type', 'unknown')
            if resource_type not in resource_types:
                resource_types[resource_type] = 0
            resource_types[resource_type] += 1
        
        logger.info(f"Resource types: {pformat(resource_types)}")
        
        # Specifically check for FIFO and crossbar resources
        fifo_resources = [r for r in hls.allocated_resources if 'fifo' in str(r).lower()]
        crossbar_resources = [r for r in hls.allocated_resources if 'crossbar' in str(r).lower()]
        
        logger.info(f"FIFO resources count: {len(fifo_resources)}")
        logger.info(f"Crossbar resources count: {len(crossbar_resources)}")
        
        if fifo_resources:
            logger.info(f"FIFO resources: {pformat(fifo_resources)}")
        
        if crossbar_resources:
            logger.info(f"Crossbar resources: {pformat(crossbar_resources)}")
    
    # Examine netlist resources
    if hasattr(hls, 'netlist_resources'):
        logger.info(f"Netlist resources count: {len(hls.netlist_resources)}")
        
        # Group by type
        netlist_resource_types = {}
        for resource in hls.netlist_resources:
            resource_type = getattr(resource, 'type', None) or getattr(resource, 'resource_type', 'unknown')
            if resource_type not in netlist_resource_types:
                netlist_resource_types[resource_type] = 0
            netlist_resource_types[resource_type] += 1
        
        logger.info(f"Netlist resource types: {pformat(netlist_resource_types)}")
    
    # Generate microarchitecture visualization
    try:
        microarch_file = hls.visualize_netlist_microarch(output_file="spmm_microarch_debug.png")
        logger.info(f"Generated microarchitecture visualization: {microarch_file}")
    except Exception as e:
        logger.error(f"Error generating microarchitecture visualization: {e}")
    
    logger.info("Debug compilation completed")

except Exception as e:
    logger.error(f"Error during debug: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    print("Debug complete. Check debug_fifo_ir.log for detailed information.") 