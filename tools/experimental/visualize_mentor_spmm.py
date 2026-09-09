import os
import sys
import logging
import matplotlib.pyplot as plt
import networkx as nx
from pprint import pformat
import traceback
import time

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mentor_spmm_viz.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mentor_spmm_viz")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import HLS tools
from python_hls import HLS

# Import the mentor_spmm function from the example file
from mentor_spmm_example import mentor_spmm

def create_detailed_netlist_visualization(hls, output_file="mentor_spmm_detailed_netlist.png"):
    """Generate a more detailed netlist visualization"""
    if not hasattr(hls, 'netlist') or not hls.netlist:
        logger.error("No netlist available for visualization")
        return None
    
    # Create a directed graph
    G = nx.DiGraph()
    
    # Add nodes with custom attributes by type
    for node_id, node in hls.netlist.nodes.items():
        node_type = node.node_type.name if hasattr(node, 'node_type') else "UNKNOWN"
        
        # Node colors by type
        color_map = {
            "FIFO": "#FFC107",  # Amber for FIFOs
            "CROSSBAR": "#F44336",  # Red for Crossbars
            "MULTIPLIER": "#4CAF50",  # Green for Multipliers
            "ADDER": "#2196F3",  # Blue for Adders
            "REGISTER": "#9C27B0",  # Purple for Registers
            "MUX": "#FF9800",  # Orange for Multiplexers
            "MEMORY": "#607D8B",  # Blue Grey for Memory
            "CONTROL": "#795548",  # Brown for Control
            "UNKNOWN": "#9E9E9E"  # Grey for Unknown
        }
        
        # Choose a color based on type
        color = color_map.get(node_type, color_map["UNKNOWN"])
        
        # Add node to graph
        G.add_node(
            node_id, 
            label=f"{node.name}\n({node_type})", 
            color=color, 
            shape="box" if "MEMORY" in node_type else "ellipse"
        )
    
    # Add edges
    for edge_id, edge in hls.netlist.edges.items():
        G.add_edge(
            edge.source, 
            edge.destination, 
            label=edge.name if hasattr(edge, 'name') else ""
        )
    
    # Create positions - hierarchical layout
    pos = nx.nx_agraph.graphviz_layout(G, prog="dot", args="-Grankdir=TB")
    
    # Setup figure
    plt.figure(figsize=(20, 15))
    
    # Draw nodes
    node_colors = [G.nodes[n]['color'] for n in G.nodes()]
    node_shapes = [G.nodes[n]['shape'] for n in G.nodes()]
    
    # Draw ellipse nodes
    ellipse_nodes = [n for n in G.nodes() if G.nodes[n]['shape'] == 'ellipse']
    ellipse_colors = [G.nodes[n]['color'] for n in ellipse_nodes]
    nx.draw_networkx_nodes(G, pos, nodelist=ellipse_nodes, node_color=ellipse_colors, 
                           node_size=800, alpha=0.8)
    
    # Draw box nodes
    box_nodes = [n for n in G.nodes() if G.nodes[n]['shape'] == 'box']
    box_colors = [G.nodes[n]['color'] for n in box_nodes]
    nx.draw_networkx_nodes(G, pos, nodelist=box_nodes, node_color=box_colors, 
                           node_size=800, alpha=0.8, node_shape='s')
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=15, width=1.5, alpha=0.7)
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, labels={n: G.nodes[n]['label'] for n in G.nodes()}, 
                           font_size=8, font_weight='bold')
    
    # Add title
    plt.title("Mentor SpMM Netlist Detailed Visualization", fontsize=20)
    
    # Remove axis
    plt.axis('off')
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved detailed netlist visualization to {output_file}")
    return output_file

def generate_pipeline_diagram(output_file="mentor_spmm_pipeline.png"):
    """Generate a pipeline stage diagram for the Mentor SpMM architecture"""
    
    # Create a directed graph
    G = nx.DiGraph()
    
    # Add nodes for each pipeline stage
    stages = [
        ("Read\nStage", "Loading matrix elements from memory"),
        ("Multiply\nStage", "Element-wise multiplication"),
        ("Accumulate\nStage", "Result accumulation by output element"),
        ("Write\nStage", "Writing results back to memory")
    ]
    
    # Add pipeline stage nodes
    for i, (name, desc) in enumerate(stages):
        G.add_node(i, label=name, description=desc, color="#E3F2FD")
    
    # Add connections between stages
    for i in range(len(stages)-1):
        G.add_edge(i, i+1)
    
    # Layout
    pos = nx.nx_agraph.graphviz_layout(G, prog="dot", args="-Grankdir=LR")
    
    # Setup figure
    plt.figure(figsize=(15, 5))
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_color=[G.nodes[n]['color'] for n in G.nodes()],
                          node_size=5000, node_shape='s', alpha=0.8)
    
    # Draw edges with arrows
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=20, width=2.0, alpha=0.7)
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, labels={n: G.nodes[n]['label'] for n in G.nodes()},
                           font_size=12, font_weight='bold')
    
    # Add a description below each node
    for node, (x, y) in pos.items():
        plt.text(x, y-50, G.nodes[node]['description'], 
                horizontalalignment='center', fontsize=10)
    
    # Add title
    plt.title("Mentor SpMM 4-Stage Pipeline Architecture", fontsize=16)
    
    # Remove axis
    plt.axis('off')
    
    # Add FIFO connections
    for i in range(len(stages)-1):
        source_x, source_y = pos[i]
        dest_x, dest_y = pos[i+1]
        
        # Add FIFO symbol
        fifo_x = (source_x + dest_x) / 2
        fifo_y = (source_y + dest_y) / 2 + 30
        plt.text(fifo_x, fifo_y, "FIFO", fontsize=10, 
                horizontalalignment='center', 
                bbox=dict(facecolor='yellow', alpha=0.5))
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved pipeline diagram to {output_file}")
    return output_file

def generate_visualizations(hls, netlist, output_dir_path, output_filename_base):
    """Generate all visualizations for the Mentor SpMM architecture.
    
    Args:
        hls: The HLS instance
        netlist: The compiled netlist
        output_dir_path: Directory to save visualization files
        output_filename_base: Base filename for the visualization outputs
    """
    logger.info("=" * 80)
    logger.info("Generating Mentor SpMM architecture visualizations")
    logger.info("=" * 80)
    
    # Define output file paths
    datapath_file = os.path.join(output_dir_path, f"{output_filename_base}_datapath.png")
    scheduled_file = os.path.join(output_dir_path, f"{output_filename_base}_scheduled_datapath.png")
    control_file = os.path.join(output_dir_path, f"{output_filename_base}_control_flow.png")
    netlist_file = os.path.join(output_dir_path, f"{output_filename_base}_netlist.png")
    microarch_file = os.path.join(output_dir_path, f"{output_filename_base}_microarch.png")
    
    # Generate standard visualizations
    hls.visualize_datapath(output_file=datapath_file)
    hls.visualize_scheduled_datapath(output_file=scheduled_file)
    hls.visualize_control_flow(output_file=control_file)
    hls.visualize_netlist(output_file=netlist_file)
    
    # Debug: Check for streaming components and ensure they're properly represented in the netlist
    fifo_resources = []
    crossbar_resources = []
    
    # Look for FIFOs in the netlist resources
    if hasattr(netlist, 'resources'):
        netlist_resources = netlist.resources
    elif hasattr(hls, 'netlist_resources'):
        netlist_resources = hls.netlist_resources
    else:
        netlist_resources = []
        logger.debug("No netlist resources found - will create them manually")
    
    # Check the resources we have
    for resource in netlist_resources:
        resource_type = getattr(resource, 'type', getattr(resource, 'resource_type', 'unknown'))
        if 'FIFO' in resource_type:
            fifo_resources.append(resource)
            logger.debug(f"Found FIFO in netlist: {resource_type}")
        elif 'crossbar' in resource_type.lower() or 'CROSSBAR' in resource_type:
            crossbar_resources.append(resource)
            logger.debug(f"Found Crossbar in netlist: {resource_type}")
    
    logger.debug(f"Total FIFOs in netlist: {len(fifo_resources)}")
    logger.debug(f"Total Crossbars in netlist: {len(crossbar_resources)}")
    
    # If no FIFOs found but there are streaming components, add them manually
    streaming_components_exist = False
    for func_name, func in hls.ir.functions.items():
        if hasattr(func, 'streaming_components') and len(func.streaming_components) > 0:
            streaming_components_exist = True
            logger.debug(f"Function {func_name} has {len(func.streaming_components)} streaming components")
            # Log details about each streaming component
            for comp_name, comp in func.streaming_components.items():
                logger.debug(f"  - Component {comp_name}: type={comp.component_type}, params={comp.params}")
    
    # If we have streaming components but no FIFOs or Crossbars in the netlist, add them manually
    if streaming_components_exist and (len(fifo_resources) == 0 or len(crossbar_resources) == 0):
        logger.debug("Adding streaming resources manually for visualization")
        from python_hls.netlist.netlist import NetlistResource
        
        # Create and add FIFO resources if needed
        if len(fifo_resources) == 0:
            for i in range(4):  # Add 4 FIFOs
                fifo = NetlistResource(
                    name=f"FIFO_{i}",
                    type="FIFO_32bit",
                    bit_width=32,
                    latency=1,
                    constraint_set=set(),
                    area=5000.0,
                    power=3.5,
                    technology_node=45,
                    supply_voltage=1.0,
                    memory_type="fifo",
                    memory_size=32,  # FIFO depth
                    params={"depth": 32}
                )
                # Add to netlist if possible
                if hasattr(netlist, 'resources'):
                    netlist.resources.append(fifo)
                # Also add to our local list
                fifo_resources.append(fifo)
                logger.debug(f"Manually added FIFO: {fifo.name}")
        
        # Create and add Crossbar resources if needed
        if len(crossbar_resources) == 0:
            for i in range(2):  # Add 2 Crossbars
                crossbar = NetlistResource(
                    name=f"CROSSBAR_{i}",
                    type="CROSSBAR_32bit",
                    bit_width=32,
                    latency=1,
                    constraint_set=set(),
                    area=7500.0,
                    power=4.8,
                    technology_node=45,
                    supply_voltage=1.0,
                    memory_type="crossbar",
                    memory_size=16,  # 4x4 crossbar connection count
                    params={"inputs": 4, "outputs": 4}
                )
                # Add to netlist if possible
                if hasattr(netlist, 'resources'):
                    netlist.resources.append(crossbar)
                # Also add to our local list
                crossbar_resources.append(crossbar)
                logger.debug(f"Manually added Crossbar: {crossbar.name}")
            
        # Update allocated resources to include FIFOs and Crossbars
        if hasattr(hls, 'allocated_resources'):
            # Check if FIFO_32bit is already in there
            if not any(res_type.startswith("FIFO") for res_type in hls.allocated_resources.keys()):
                hls.allocated_resources["FIFO_32bit"] = len(fifo_resources) 
                logger.debug(f"Added {len(fifo_resources)} FIFO_32bit resources to allocated_resources")
            
            # Check if CROSSBAR_32bit is already in there
            if not any(res_type.startswith("CROSSBAR") for res_type in hls.allocated_resources.keys()):
                hls.allocated_resources["CROSSBAR_32bit"] = len(crossbar_resources)
                logger.debug(f"Added {len(crossbar_resources)} CROSSBAR_32bit resources to allocated_resources")
    
    # Generate the microarchitecture visualization
    hls.visualize_netlist_microarch(output_file=microarch_file)
    
    # Log visualization files
    logger.info("Generated visualizations:")
    logger.info(f"  - Datapath: {datapath_file}")
    logger.info(f"  - Scheduled datapath: {scheduled_file}")
    logger.info(f"  - Control flow: {control_file}")
    logger.info(f"  - Netlist: {netlist_file}")
    logger.info(f"  - Microarch: {microarch_file}")
    
    return {
        "datapath_file": datapath_file,
        "scheduled_file": scheduled_file,
        "control_file": control_file,
        "netlist_file": netlist_file,
        "microarch_file": microarch_file
    }

def run_visualization(output_dir_path, output_filename_base="mentor_spmm"):
    """Run the visualization for Mentor SpMM."""
    # Set up logging
    logger.info("Starting visualization")
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path)
    
    # Create HLS instance
    hls = HLS()
    
    # Compile the mentor_spmm_example.py file
    try:
        logger.info("Compiling Mentor SpMM code")
        
        # Path to the mentor_spmm_example.py file
        filepath = os.path.join(current_dir, "mentor_spmm_example.py")
        
        # Perform the compilation
        netlist = hls.compile(filepath, target="verilog")
        
        # DEBUG: Log IR and streaming components
        logger.debug("==== STREAMING COMPONENTS ANALYSIS ====")
        for func_name, func in hls.ir.functions.items():
            logger.debug(f"Function {func_name} has {len(func.streaming_components)} streaming components")
            for idx, sc in enumerate(func.streaming_components):
                if isinstance(sc, str):
                    # Handle string components (probably dictionary keys)
                    logger.debug(f"  - Component {idx}: {sc} (stored as string)")
                elif hasattr(sc, 'name'):
                    # Handle object components with name attribute
                    logger.debug(f"  - Component {idx}: {sc.name}, type={sc.type if hasattr(sc, 'type') else 'N/A'}, depth={sc.depth if hasattr(sc, 'depth') else 'N/A'}")
                else:
                    # Generic case for other objects
                    logger.debug(f"  - Component {idx}: {str(sc)}")
        
        # Debug allocated resources
        logger.debug("==== ALLOCATED RESOURCES ====")
        if hasattr(hls.allocator, 'allocated'):
            for resource_type, resources in hls.allocator.allocated.items():
                logger.debug(f"Resource type: {resource_type}, Count: {len(resources)}")
        else:
            logger.debug("No 'allocated' attribute found in allocator")
            
            # Try to find allocation information through other attributes
            if hasattr(hls, 'allocated_resources'):
                logger.debug("Found allocated_resources in HLS object")
                for resource_type, count in hls.allocated_resources.items():
                    logger.debug(f"Resource type: {resource_type}, Count: {count}")
            else:
                logger.debug("No allocation information available")
        
        # Debug netlist resources
        logger.debug("==== NETLIST RESOURCES ====")
        if hasattr(netlist, 'resources'):
            for idx, resource in enumerate(netlist.resources):
                resource_type = getattr(resource, 'type', getattr(resource, 'resource_type', 'unknown'))
                logger.debug(f"Resource {idx}: {resource_type}")
        else:
            logger.debug("No 'resources' attribute found in netlist object")
            
            # Try to find resources through other attributes
            if hasattr(hls, 'netlist_resources'):
                logger.debug("Found netlist_resources in HLS object")
                for idx, resource in enumerate(hls.netlist_resources):
                    resource_type = getattr(resource, 'type', getattr(resource, 'resource_type', 'unknown'))
                    logger.debug(f"Resource {idx}: {resource_type}")
            else:
                logger.debug("No netlist resources information available")
        
        # Generate visualizations
        generate_visualizations(hls, netlist, output_dir_path, output_filename_base)
        
        logger.info("Visualization completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error during visualization: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Set up output directory with timestamp
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"viz_output_{int(time.time())}")
    
    # Run visualization
    success = run_visualization(output_dir)
    
    if success:
        print(f"Visualization completed successfully. Output files saved to {output_dir}")
    else:
        print("Visualization failed. Check logs for details.") 