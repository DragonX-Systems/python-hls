import os
import sys
import logging
import matplotlib.pyplot as plt
import networkx as nx
from pprint import pformat

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("spmm_simple_viz.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("spmm_simple_viz")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import HLS tools
from python_hls import HLS

# Import the spmm function from the example file
from mentor_spmm_simple import spmm

def generate_pipeline_diagram(output_file="spmm_simple_pipeline.png"):
    """Generate a pipeline stage diagram for the Mentor SpMM architecture with FIFOs and crossbars"""
    
    # Create a directed graph
    G = nx.DiGraph()
    
    # Add nodes for each pipeline stage
    stages = [
        ("Read\nStage", "Loading matrix elements"),
        ("Multiply\nStage", "Element-wise multiplication"),
        ("Accumulate\nStage", "Result accumulation by output element"),
        ("Write\nStage", "Writing results back")
    ]
    
    # Add pipeline stage nodes
    for i, (name, desc) in enumerate(stages):
        G.add_node(i, label=name, description=desc, color="#E3F2FD", type="stage")
    
    # Add FIFO nodes
    fifos = [
        ("sparse_fifo", "Sparse matrix elements"),
        ("dense_fifo", "Dense matrix elements"),
        ("indices_fifo", "Row indices"),
        ("mult_fifo", "Multiplication results"),
        ("output_fifo", "Accumulated results")
    ]
    
    for i, (name, desc) in enumerate(fifos):
        node_id = f"fifo_{i}"
        G.add_node(node_id, label=name, description=desc, color="#FFECB3", type="fifo")
    
    # Add crossbar nodes
    crossbars = [
        ("read_crossbar", "Input data routing"),
        ("accumulate_crossbar", "Accumulation routing"),
        ("write_crossbar", "Output routing")
    ]
    
    for i, (name, desc) in enumerate(crossbars):
        node_id = f"crossbar_{i}"
        G.add_node(node_id, label=name, description=desc, color="#E1BEE7", type="crossbar")
    
    # Add connections between stages and FIFOs/crossbars
    # Stage 1 (Read) connections
    G.add_edge(f"crossbar_0", 0)  # read_crossbar to Read Stage
    G.add_edge(0, "fifo_0")  # Read Stage to sparse_fifo
    G.add_edge(0, "fifo_1")  # Read Stage to dense_fifo
    G.add_edge(0, "fifo_2")  # Read Stage to indices_fifo
    
    # Stage 2 (Multiply) connections
    G.add_edge("fifo_0", 1)  # sparse_fifo to Multiply Stage
    G.add_edge("fifo_1", 1)  # dense_fifo to Multiply Stage
    G.add_edge(1, "fifo_3")  # Multiply Stage to mult_fifo
    
    # Stage 3 (Accumulate) connections
    G.add_edge("fifo_3", 2)  # mult_fifo to Accumulate Stage
    G.add_edge("fifo_2", 2)  # indices_fifo to Accumulate Stage
    G.add_edge(2, f"crossbar_1")  # Accumulate Stage to accumulate_crossbar
    G.add_edge(f"crossbar_1", "fifo_4")  # accumulate_crossbar to output_fifo
    
    # Stage 4 (Write) connections
    G.add_edge("fifo_4", 3)  # output_fifo to Write Stage
    G.add_edge(3, f"crossbar_2")  # Write Stage to write_crossbar
    
    # Use hierarchical layout for better visualization of the pipeline
    pos = nx.multipartite_layout(
        G, 
        subset_key="type",
        align="horizontal"
    )
    
    # Custom positioning adjustments for better visualization
    for node in G.nodes():
        if isinstance(node, int):  # Pipeline stages
            pos[node] = (pos[node][0], pos[node][1] - 0.1 * node)
        elif "fifo" in node:  # FIFOs
            pos[node] = (pos[node][0] + 0.1, pos[node][1] + 0.2)
        elif "crossbar" in node:  # Crossbars
            pos[node] = (pos[node][0] - 0.1, pos[node][1] - 0.2)
    
    # Setup figure
    plt.figure(figsize=(15, 8))
    
    # Draw nodes by type with different colors and shapes
    # Draw stage nodes as squares
    stage_nodes = [n for n in G.nodes() if G.nodes[n].get('type') == "stage"]
    nx.draw_networkx_nodes(G, pos, nodelist=stage_nodes, 
                          node_color=[G.nodes[n]['color'] for n in stage_nodes],
                          node_size=5000, node_shape='s', alpha=0.8)
    
    # Draw FIFO nodes as ellipses
    fifo_nodes = [n for n in G.nodes() if G.nodes[n].get('type') == "fifo"]
    nx.draw_networkx_nodes(G, pos, nodelist=fifo_nodes, 
                          node_color=[G.nodes[n]['color'] for n in fifo_nodes],
                          node_size=3000, node_shape='o', alpha=0.8)
    
    # Draw crossbar nodes as diamonds
    crossbar_nodes = [n for n in G.nodes() if G.nodes[n].get('type') == "crossbar"]
    nx.draw_networkx_nodes(G, pos, nodelist=crossbar_nodes, 
                          node_color=[G.nodes[n]['color'] for n in crossbar_nodes],
                          node_size=3000, node_shape='d', alpha=0.8)
    
    # Draw edges with arrows
    nx.draw_networkx_edges(G, pos, arrows=True, arrowsize=15, width=1.5, alpha=0.7)
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, labels={n: G.nodes[n]['label'] for n in G.nodes()},
                           font_size=10, font_weight='bold')
    
    # Add a legend
    plt.plot([], [], 's', color='#E3F2FD', label='Pipeline Stages')
    plt.plot([], [], 'o', color='#FFECB3', label='FIFO Buffers')
    plt.plot([], [], 'd', color='#E1BEE7', label='Crossbars')
    plt.legend(loc='upper right')
    
    # Add title
    plt.title("Mentor SpMM Pipeline Architecture with FIFOs and Crossbars", fontsize=16)
    
    # Remove axis
    plt.axis('off')
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Saved pipeline diagram to {output_file}")
    return output_file

def create_output_dir():
    """Create a directory for visualization output that won't be deleted"""
    output_dir = "visualization_output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def run_visualization():
    """Run visualizations for the Mentor SpMM architecture with FIFOs and crossbars"""
    logger.info("=" * 80)
    logger.info("Generating Mentor SpMM architecture visualizations with FIFOs and crossbars")
    logger.info("=" * 80)
    
    # Create output directory
    output_dir = create_output_dir()
    
    # Create an HLS instance with optimization_level=0 to prevent removal of operations
    # Setting tech_node=45 to match the reference implementation
    hls = HLS(optimization_level=3, tech_node=45)
    
    # Compile the mentor_spmm_simple.py file
    try:
        logger.info("Compiling Mentor SpMM code with FIFOs and crossbars")
        
        # Path to the mentor_spmm_simple.py file
        filepath = os.path.join(current_dir, "mentor_spmm_simple.py")
        
        # Ensure HLS modules are properly configured to visualize FIFOs and crossbars
        hls.config = {
            "visualize": {
                "show_fifos": True,
                "show_crossbars": True,
                "highlight_communication": True
            }
        }
        
        # Perform the compilation
        netlist = hls.compile(filepath, target="verilog")
        
        # Apply resource allocation optimizations to ensure FIFOs and crossbars are included
        if hasattr(hls, 'scheduled_ir') and hls.scheduled_ir:
            # Optimize for performance to generate more hardware resources
            optimization_target = "performance"
            hls.allocated_resources = hls.allocator.allocate(
                hls.scheduled_ir, optimization_target
            )[1]
            hls.netlist_resources = hls.allocator.create_netlist_resources(hls.allocated_resources)
            
            # Update the netlist resources
            hls._apply_resources_to_modules()
        
        # Generate standard visualizations with permanent output paths
        datapath_file = hls.visualize_datapath(output_file=os.path.join(output_dir, "spmm_datapath.png"))
        scheduled_file = hls.visualize_scheduled_datapath(output_file=os.path.join(output_dir, "spmm_scheduled.png"))
        control_file = hls.visualize_control_flow(output_file=os.path.join(output_dir, "spmm_control_flow.png"))
        netlist_file = hls.visualize_netlist(output_file=os.path.join(output_dir, "spmm_netlist.png"))
        
        # Generate microarchitecture visualization with enhanced FIFO and crossbar visibility
        microarch_file = hls.visualize_netlist_microarch(
            output_file=os.path.join(output_dir, "spmm_microarch.png"),
        )
        
        # Generate custom pipeline diagram that explicitly shows FIFOs and crossbars
        pipeline_diagram_file = generate_pipeline_diagram(output_file=os.path.join(output_dir, "spmm_pipeline.png"))
        
        logger.info("Generated visualizations with FIFOs and crossbars:")
        logger.info(f"  - Datapath: {datapath_file}")
        logger.info(f"  - Scheduled datapath: {scheduled_file}")
        logger.info(f"  - Control flow: {control_file}")
        logger.info(f"  - Netlist: {netlist_file}")
        logger.info(f"  - Microarchitecture: {microarch_file}")
        logger.info(f"  - Pipeline diagram: {pipeline_diagram_file}")
        
        # Print absolute paths for easier access
        logger.info("\nAbsolute paths:")
        for file_path in [microarch_file]:
            abs_path = os.path.abspath(file_path)
            logger.info(f"  {os.path.basename(file_path)}: {abs_path}")
        
        return {
            "datapath_file": datapath_file,
            "scheduled_file": scheduled_file,
            "control_file": control_file,
            "netlist_file": netlist_file,
            "microarch_file": microarch_file,
            "pipeline_diagram_file": pipeline_diagram_file
        }
        
    except Exception as e:
        logger.error(f"Error during visualization: {e}")
        raise

if __name__ == "__main__":
    visualization_results = run_visualization() 