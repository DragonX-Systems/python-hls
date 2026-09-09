"""
Script to visualize loop structures in the data flow graph.
This helps diagnose the "Data flow graph is disconnected" warning.
"""

import os
import sys
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import tempfile

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from python_hls import HLS
from python_hls.hls_engine.scheduler import ASAPScheduler

def visualize_dfg_with_loop_analysis(ir, output_file=None):
    """
    Create a detailed visualization of the data flow graph with loop structure analysis.
    Highlights loop-related nodes and shows disconnected components.
    
    Args:
        ir: The IR to visualize
        output_file: Output file path for the visualization
    """
    # Get functions
    functions = list(ir.functions.values())
    if not functions:
        print("No functions found in IR")
        return
    
    # For each function, create a scheduler and extract the DFG
    for func in functions:
        print(f"Analyzing function: {func.name}")
        
        # Create a scheduler to get the DFG
        scheduler = ASAPScheduler(None)  # No tech library needed for visualization
        dfg = scheduler._build_dfg(func)
        
        # Analyze graph connectivity
        components = list(nx.weakly_connected_components(dfg))
        print(f"Found {len(components)} disconnected components in DFG")
        
        # Identify loop-related nodes
        loop_init_nodes = []
        loop_cond_nodes = []
        loop_update_nodes = []
        compute_nodes = []
        
        for node in dfg.nodes():
            node_data = dfg.nodes[node]
            if 'op' in node_data:
                op = node_data['op']
                if hasattr(op, 'name'):
                    name = op.name
                    if "init_op" in name:
                        loop_init_nodes.append(node)
                    elif "cond_op" in name:
                        loop_cond_nodes.append(node)
                    elif "add_op" in name and "assign_op" in [dfg.nodes[n]['op'].name for n in dfg.successors(node) if 'op' in dfg.nodes[n]]:
                        # Increment operations typically feed back to assignments
                        loop_update_nodes.append(node)
                    elif any(op_type in name for op_type in ["add_op", "mul_op", "load_op", "store_op"]):
                        compute_nodes.append(node)
        
        # Count edge types
        loop_back_edges = 0
        cross_component_edges = set()
        
        for u, v in dfg.edges():
            u_comp = None
            v_comp = None
            
            # Find which component each node belongs to
            for i, comp in enumerate(components):
                if u in comp:
                    u_comp = i
                if v in comp:
                    v_comp = i
            
            # Check if this is a cross-component edge
            if u_comp is not None and v_comp is not None and u_comp != v_comp:
                cross_component_edges.add((u, v))
            
            # Check if this is a loop back edge (going from higher to lower node)
            if (u in loop_update_nodes and v in loop_cond_nodes) or \
               (u in loop_update_nodes and v in loop_init_nodes):
                loop_back_edges += 1
        
        print(f"Found {loop_back_edges} loop back edges")
        print(f"Found {len(cross_component_edges)} edges between disconnected components")
        
        # Create visualization
        plt.figure(figsize=(16, 12))
        
        # Position nodes using a spring layout with more iterations for better separation
        pos = nx.spring_layout(dfg, iterations=100)
        
        # Draw nodes by type
        nx.draw_networkx_nodes(dfg, pos, nodelist=loop_init_nodes, 
                               node_color='green', node_size=300, alpha=0.8, label='Loop Init')
        nx.draw_networkx_nodes(dfg, pos, nodelist=loop_cond_nodes, 
                               node_color='red', node_size=300, alpha=0.8, label='Loop Condition')
        nx.draw_networkx_nodes(dfg, pos, nodelist=loop_update_nodes, 
                               node_color='blue', node_size=300, alpha=0.8, label='Loop Update')
        nx.draw_networkx_nodes(dfg, pos, nodelist=compute_nodes, 
                               node_color='orange', node_size=300, alpha=0.8, label='Computation')
        
        # Draw remaining nodes
        other_nodes = [n for n in dfg.nodes() if n not in loop_init_nodes + 
                       loop_cond_nodes + loop_update_nodes + compute_nodes]
        nx.draw_networkx_nodes(dfg, pos, nodelist=other_nodes, 
                               node_color='gray', node_size=200, alpha=0.5, label='Other')
        
        # Highlight disconnected components with colored backgrounds
        colors = plt.cm.tab10(range(min(10, len(components))))
        
        for i, component in enumerate(components):
            component_color = colors[i % 10]
            # Draw a light background for this component
            component_nodes = list(component)
            if len(component_nodes) > 1:  # Only draw backgrounds for multi-node components
                nx.draw_networkx_nodes(dfg, pos, nodelist=component_nodes, 
                                      node_size=1000, alpha=0.1, 
                                      node_color=[component_color], 
                                      label=f"Component {i+1}")
        
        # Draw regular edges
        regular_edges = [(u, v) for u, v in dfg.edges() if (u, v) not in cross_component_edges]
        nx.draw_networkx_edges(dfg, pos, edgelist=regular_edges, alpha=0.3)
        
        # Highlight cross-component edges (should be empty in a properly connected graph)
        nx.draw_networkx_edges(dfg, pos, edgelist=list(cross_component_edges), 
                              edge_color='red', width=2, alpha=0.7, label='Missing Connection')
        
        # Draw node labels with shortened names
        labels = {}
        for node in dfg.nodes():
            if 'op' in dfg.nodes[node]:
                op = dfg.nodes[node]['op']
                if hasattr(op, 'name'):
                    # Shorten the name to make the graph readable
                    name = op.name
                    if len(name) > 20:
                        name = name[:10] + '...' + name[-7:]
                    labels[node] = name
                else:
                    labels[node] = str(node)
            else:
                labels[node] = str(node)
        
        nx.draw_networkx_labels(dfg, pos, labels, font_size=8)
        
        # Add title and legend
        plt.title(f"Data Flow Graph Analysis - Function: {func.name}\n"
                 f"Components: {len(components)}, Loop Back Edges: {loop_back_edges}, "
                 f"Missing Connections: {len(cross_component_edges)}")
        plt.legend(loc='upper right')
        
        # Remove axis
        plt.axis('off')
        
        # Save or show the visualization
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"Saved visualization to {output_file}")
        else:
            plt.show()
        
        # Create DOT file for detailed inspection
        dot_output = output_file.replace('.png', '.dot') if output_file else 'loop_analysis.dot'
        
        # Add custom attributes to nodes for the DOT visualization
        for node in dfg.nodes():
            if 'op' in dfg.nodes[node]:
                op = dfg.nodes[node]['op']
                if hasattr(op, 'name'):
                    dfg.nodes[node]['label'] = op.name
                    
                    # Color nodes by type
                    if "init_op" in op.name:
                        dfg.nodes[node]['color'] = 'green'
                        dfg.nodes[node]['style'] = 'filled'
                    elif "cond_op" in op.name:
                        dfg.nodes[node]['color'] = 'red'
                        dfg.nodes[node]['style'] = 'filled'
                    elif "add_op" in op.name:
                        dfg.nodes[node]['color'] = 'blue'
                        dfg.nodes[node]['style'] = 'filled'
                    elif any(op_type in op.name for op_type in ["mul_op", "load_op", "store_op"]):
                        dfg.nodes[node]['color'] = 'orange'
                        dfg.nodes[node]['style'] = 'filled'
        
        # Color edges that cross components
        for u, v in dfg.edges():
            if (u, v) in cross_component_edges:
                dfg[u][v]['color'] = 'red'
                dfg[u][v]['penwidth'] = '2.0'
                dfg[u][v]['label'] = 'Missing Connection'
        
        # Write to DOT file
        nx.drawing.nx_pydot.write_dot(dfg, dot_output)
        print(f"Saved DOT file to {dot_output}")
        
        # Generate analysis report
        report_output = output_file.replace('.png', '_report.txt') if output_file else 'loop_analysis_report.txt'
        with open(report_output, 'w') as f:
            f.write(f"Loop Structure Analysis Report - Function: {func.name}\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Graph Summary:\n")
            f.write(f"  - Total Nodes: {len(dfg.nodes())}\n")
            f.write(f"  - Total Edges: {len(dfg.edges())}\n")
            f.write(f"  - Disconnected Components: {len(components)}\n")
            f.write(f"  - Missing Connections: {len(cross_component_edges)}\n\n")
            
            f.write(f"Loop Structure:\n")
            f.write(f"  - Loop Init Nodes: {len(loop_init_nodes)}\n")
            f.write(f"    {[dfg.nodes[n]['op'].name for n in loop_init_nodes if 'op' in dfg.nodes[n]]}\n\n")
            f.write(f"  - Loop Condition Nodes: {len(loop_cond_nodes)}\n")
            f.write(f"    {[dfg.nodes[n]['op'].name for n in loop_cond_nodes if 'op' in dfg.nodes[n]]}\n\n")
            f.write(f"  - Loop Update Nodes: {len(loop_update_nodes)}\n")
            f.write(f"    {[dfg.nodes[n]['op'].name for n in loop_update_nodes if 'op' in dfg.nodes[n]]}\n\n")
            f.write(f"  - Compute Nodes: {len(compute_nodes)}\n")
            f.write(f"    {[dfg.nodes[n]['op'].name for n in compute_nodes if 'op' in dfg.nodes[n]]}\n\n")
            
            f.write(f"Missing Connections (Cross-Component Edges):\n")
            for u, v in cross_component_edges:
                u_name = dfg.nodes[u]['op'].name if 'op' in dfg.nodes[u] else str(u)
                v_name = dfg.nodes[v]['op'].name if 'op' in dfg.nodes[v] else str(v)
                f.write(f"  - {u_name} -> {v_name}\n")
            
            f.write("\nPossible Issues:\n")
            if len(components) > 1:
                f.write("  - The graph has disconnected components, which means some operations\n")
                f.write("    are unreachable from others in the data flow.\n")
                f.write("  - This can cause scheduling problems and incorrect hardware generation.\n\n")
            
            if loop_back_edges == 0 and (len(loop_init_nodes) > 0 or len(loop_cond_nodes) > 0):
                f.write("  - No loop back edges were detected, but loop control nodes exist.\n")
                f.write("  - This suggests that loop iterations are not properly connected.\n\n")
            
            f.write("Recommended Actions:\n")
            f.write("  1. Ensure that loop update operations connect back to loop condition checks\n")
            f.write("  2. Verify that array accesses use the correct loop iterator variables\n")
            f.write("  3. Check for operations with missing data dependencies\n")
            f.write("  4. Consider adding explicit data flow connections between loop iterations\n")
        
        print(f"Saved analysis report to {report_output}")

def main():
    """Main function to run loop structure visualization."""
    if len(sys.argv) < 2:
        print("Usage: python visualize_loops.py <spmm_variant>")
        sys.exit(1)
    
    variant = sys.argv[1]
    
    # Read the SPMM program (reusing code from visualize_spmm.py)
    from visualize_spmm import read_spmm_program, get_spmm_variants
    
    spmm_program = read_spmm_program(variant)
    
    # Create a temporary directory for our source file
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a copy of the SPMM program in the temp directory
        spmm_file = os.path.join(temp_dir, "spmm_temp.py")
        with open(spmm_file, 'w') as f:
            f.write(spmm_program)
        
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loop_analysis")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"Compiling SPMM program (variant: {variant})...")
        
        # Create an HLS instance
        # Using optimization_level=0 to preserve the structure for visualization
        hls = HLS(optimization_level=0, tech_node=45)
        
        # Front-end translation only (don't proceed to scheduling)
        # Front-end translation only (parser → AST → IR)
        hls.ast = hls.parser.parse_file(spmm_file)
        hls.ir = hls.ir_generator.generate(hls.ast)
        
        # Visualize the DFG with loop analysis
        output_file = os.path.join(output_dir, f"spmm_{variant}_loop_analysis.png")
        visualize_dfg_with_loop_analysis(hls.ir, output_file)
        
        print(f"\nAnalysis complete. Check {output_dir} for results.")
        
    finally:
        # Clean up the temporary directory
        import shutil
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()