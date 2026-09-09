"""
Datapath visualizer using Graphviz.
"""

import os
import networkx as nx
from typing import Dict, List, Set, Optional, Union
import matplotlib.pyplot as plt
import graphviz

from ..ir.ir_nodes import IR, IRFunction, IRBlock, IROperation, IRConstant
from ..netlist.netlist import Netlist, NetlistModule, NetlistOperation, NetlistResource
from .netlist_microarch_dot import generate_hardware_dot


class DatapathVisualizer:
    """Visualizer for datapaths and control flow."""
    
    def __init__(self):
        """Initialize the visualizer."""
        self.colors = {
            "ADD": "#66c2a5",
            "SUB": "#66c2a5",
            "MUL": "#fc8d62",
            "DIV": "#8da0cb",
            "MOD": "#8da0cb",
            "INPUT": "#a6d854",
            "OUTPUT": "#e78ac3",
            "REGISTER": "#ffd92f",
            "MUX": "#e5c494",
            "DEFAULT": "#b3b3b3"
        }
    
    def visualize_datapath(self, ir: IR, output_file: str) -> str:
        """
        Visualize the datapath from IR.
        
        Args:
            ir: IR to visualize
            output_file: Output file path
            
        Returns:
            Path to generated visualization file
        """
        for func_name, func in ir.functions.items():
            # Create a graph for each function
            graph = self._create_datapath_graph(func)
            
            # Save the graph
            base, ext = os.path.splitext(output_file)
            func_output = f"{base}_{func_name}{ext}"
            self._save_graph(graph, func_output)
            
            # For now, just return the first function's graph
            return func_output
        
        return output_file
    
    def visualize_control_flow(self, ir: IR, output_file: str) -> str:
        """
        Visualize the control flow from IR.
        
        Args:
            ir: IR to visualize
            output_file: Output file path
            
        Returns:
            Path to generated visualization file
        """
        for func_name, func in ir.functions.items():
            # Create a graph for each function
            graph = self._create_control_flow_graph(func)
            
            # Save the graph
            base, ext = os.path.splitext(output_file)
            func_output = f"{base}_{func_name}_control{ext}"
            self._save_graph(graph, func_output)
            
            # For now, just return the first function's graph
            return func_output
        
        return output_file
    
    def visualize_netlist(self, netlist: Netlist, output_file: str) -> str:
        """
        Visualize the hardware netlist.
        
        Args:
            netlist: Netlist to visualize
            output_file: Output file path
            
        Returns:
            Path to generated visualization file
        """
        for module_name, module in netlist.modules.items():
            # Create a graph for each module
            graph = self._create_netlist_graph(module)
            
            # Save the graph
            base, ext = os.path.splitext(output_file)
            module_output = f"{base}_{module_name}_netlist{ext}"
            self._save_graph(graph, module_output)
            
            # For now, just return the first module's graph
            return module_output
        
        return output_file
    
    def visualize_scheduled_datapath(self, ir: IR, output_file: str) -> str:
        """
        Visualize the scheduled datapath with control steps.
        
        Args:
            ir: Scheduled IR to visualize
            output_file: Output file path
            
        Returns:
            Path to generated visualization file
        """
        for func_name, func in ir.functions.items():
            # Create a graph for each function
            graph = self._create_scheduled_datapath_graph(func)
            
            # Save the graph
            base, ext = os.path.splitext(output_file)
            func_output = f"{base}_{func_name}_scheduled{ext}"
            self._save_graph(graph, func_output)
            
            # For now, just return the first function's graph
            return func_output
        
        return output_file
    
    def visualize_netlist_microarch(self, ir: IR, netlist: Netlist, output_file: str) -> str:
        """
        Visualize the detailed microarchitecture of the hardware netlist.
        
        Args:
            ir: IR used to create the netlist
            netlist: Netlist to visualize
            output_file: Output file path
            
        Returns:
            Path to generated visualization file
        """
        if not ir or not netlist:
            return "Error: Missing IR or netlist data"
            
        # Extract operations from the IR for better visualization
        operations = []
        for func_name, func in ir.functions.items():
            for block in func.blocks:
                for instr in block.instructions:
                    for op in instr.operations:
                        operations.append(op.op_type.name)
        
        # Use the same visualization style as in HLS.visualize_netlist
        from python_hls.visualizer.netlist_microarch_dot import generate_netlist_microarch_visualization
        
        # Extract resources from netlist
        netlist_resources = []
        for module_name, module in netlist.modules.items():
            netlist_resources.extend(module.resources)
        
        # Generate the DOT representation
        dot_content = generate_netlist_microarch_visualization(netlist_resources, operations, netlist)
        
        # Set up output path
        base, ext = os.path.splitext(output_file)
        if not ext:
            ext = ".png"
        dot_file = f"{base}.dot"
        output_path = output_file if ext else f"{base}.png"
        
        # Write the DOT content to a file
        with open(dot_file, 'w') as f:
            f.write(dot_content)
        
        # Use graphviz to render the DOT file
        try:
            # Create a Source object from the DOT content
            graph = graphviz.Source(dot_content)
            # Render the graph to the output file
            graph.render(outfile=output_path, format=ext[1:] if ext else "png", cleanup=True)
            # Remove the DOT file
            if os.path.exists(dot_file):
                os.remove(dot_file)
            return output_path
        except Exception as e:
            print(f"Error rendering graph: {e}")
            # Return the DOT file path if rendering fails
            return dot_file
    
    def _create_datapath_graph(self, func: IRFunction) -> graphviz.Digraph:
        """
        Create a datapath graph for a function.
        
        Args:
            func: Function to visualize
            
        Returns:
            Graphviz digraph
        """
        graph = graphviz.Digraph(name=f"{func.name}_datapath", format='png')
        graph.attr(rankdir='TB', size='10,10', ratio='compress')
        
        # Collect all constants used in the function
        constants = set()
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    for operand in op.operands:
                        if isinstance(operand, IRConstant):
                            constants.add(operand)
        
        # Add nodes for variables
        for var_name, var in func.local_vars.items():
            graph.node(
                f"var_{var.node_id}",
                label=var_name,
                shape='ellipse',
                fontname='Arial',
                fontsize='12'
            )
        
        # Add nodes for parameters
        for param in func.parameters:
            graph.node(
                f"param_{param.node_id}",
                label=param.name,
                shape='diamond',
                style='filled',
                fillcolor=self.colors["INPUT"],
                fontname='Arial',
                fontsize='12'
            )
        
        # Add nodes for constants
        for const in constants:
            graph.node(
                f"const_{const.node_id}",
                label=str(const.value),
                shape='box',
                style='filled',
                fillcolor=self.colors["DEFAULT"],
                fontname='Arial',
                fontsize='12'
            )
        
        # Add nodes for operations
        op_nodes = []
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    op_type = op.op_type.name
                    color = self.colors.get(op_type, self.colors["DEFAULT"])
                    
                    graph.node(
                        f"op_{op.node_id}",
                        label=op_type,
                        shape='box',
                        style='filled',
                        fillcolor=color,
                        fontname='Arial',
                        fontsize='12'
                    )
                    op_nodes.append(op)
        
        # Add edges
        for op in op_nodes:
            # Edges from operands to operation
            for i, operand in enumerate(op.operands):
                if hasattr(operand, 'node_id'):
                    if isinstance(operand, IROperation):
                        graph.edge(f"op_{operand.node_id}", f"op_{op.node_id}")
                    else:
                        # For variables, parameters, and constants
                        if isinstance(operand, IRConstant):
                            # Handle constants
                            graph.edge(f"const_{operand.node_id}", f"op_{op.node_id}")
                        else:
                            # For variables and parameters
                            node_prefix = "param_" if hasattr(operand, 'is_input') and operand.is_input else "var_"
                            graph.edge(f"{node_prefix}{operand.node_id}", f"op_{op.node_id}")
            
            # Edge from operation to result
            if hasattr(op, 'result') and op.result:
                graph.edge(f"op_{op.node_id}", f"var_{op.result.node_id}")
        
        # Add invisible edge from return variable to parameters for better layout
        if func.return_var and func.parameters:
            graph.edge(
                f"var_{func.return_var.node_id}",
                f"param_{func.parameters[0].node_id}",
                style='invis'
            )
        
        return graph
    
    def _create_control_flow_graph(self, func: IRFunction) -> graphviz.Digraph:
        """
        Create a control flow graph for a function.
        
        Args:
            func: Function to visualize
            
        Returns:
            Graphviz digraph
        """
        graph = graphviz.Digraph(name=f"{func.name}_control", format='png')
        graph.attr(rankdir='TB', size='10,10', ratio='compress')
        
        # Add nodes for blocks
        for block in func.blocks:
            instr_labels = []
            for instr in block.instructions:
                op_labels = []
                for op in instr.operations:
                    op_labels.append(f"{op.op_type.name}")
                
                if op_labels:
                    instr_labels.append(", ".join(op_labels))
            
            label = block.name
            if instr_labels:
                label += "\\n" + "\\n".join(instr_labels)
            
            graph.node(
                f"block_{block.node_id}",
                label=label,
                shape='box',
                fontname='Arial',
                fontsize='12'
            )
        
        # Add edges for control flow
        for block in func.blocks:
            for succ in block.successors:
                graph.edge(f"block_{block.node_id}", f"block_{succ.node_id}")
        
        return graph
    
    def _create_scheduled_datapath_graph(self, func: IRFunction) -> graphviz.Digraph:
        """
        Create a scheduled datapath graph for a function.
        
        Args:
            func: Function to visualize
            
        Returns:
            Graphviz digraph
        """
        graph = graphviz.Digraph(name=f"{func.name}_scheduled", format='png')
        graph.attr(rankdir='TB', size='10,10', ratio='compress')
        
        # Collect all constants used in the function
        constants = set()
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    for operand in op.operands:
                        if isinstance(operand, IRConstant):
                            constants.add(operand)
        
        # Determine maximum control step
        max_step = 0
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    max_step = max(max_step, op.control_step)
        
        # Create subgraphs for each control step
        for step in range(max_step + 1):
            with graph.subgraph(name=f"cluster_step_{step}") as step_graph:
                step_graph.attr(label=f"Step {step}", style='filled', fillcolor='#f5f5f5')
                
                # Add operations for this step
                for block in func.blocks:
                    for instr in block.instructions:
                        for op in instr.operations:
                            if op.control_step == step:
                                op_type = op.op_type.name
                                color = self.colors.get(op_type, self.colors["DEFAULT"])
                                
                                step_graph.node(
                                    f"op_{op.node_id}",
                                    label=f"{op_type}",
                                    shape='box',
                                    style='filled',
                                    fillcolor=color,
                                    fontname='Arial',
                                    fontsize='12'
                                )
        
        # Add variables and parameters outside of step clusters
        for var_name, var in func.local_vars.items():
            graph.node(
                f"var_{var.node_id}",
                label=var_name,
                shape='ellipse',
                fontname='Arial',
                fontsize='12'
            )
        
        for param in func.parameters:
            graph.node(
                f"param_{param.node_id}",
                label=param.name,
                shape='diamond',
                style='filled',
                fillcolor=self.colors["INPUT"],
                fontname='Arial',
                fontsize='12'
            )
        
        # Add constants outside of step clusters
        for const in constants:
            graph.node(
                f"const_{const.node_id}",
                label=str(const.value),
                shape='box',
                style='filled',
                fillcolor=self.colors["DEFAULT"],
                fontname='Arial',
                fontsize='12'
            )
        
        # Add edges
        op_nodes = []
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    op_nodes.append(op)
        
        for op in op_nodes:
            # Edges from operands to operation
            for i, operand in enumerate(op.operands):
                if hasattr(operand, 'node_id'):
                    if isinstance(operand, IROperation):
                        graph.edge(f"op_{operand.node_id}", f"op_{op.node_id}")
                    else:
                        # For variables, parameters, and constants
                        if isinstance(operand, IRConstant):
                            # Handle constants
                            graph.edge(f"const_{operand.node_id}", f"op_{op.node_id}")
                        else:
                            # For variables and parameters
                            node_prefix = "param_" if hasattr(operand, 'is_input') and operand.is_input else "var_"
                            graph.edge(f"{node_prefix}{operand.node_id}", f"op_{op.node_id}")
            
            # Edge from operation to result
            if hasattr(op, 'result') and op.result:
                graph.edge(f"op_{op.node_id}", f"var_{op.result.node_id}")
        
        return graph
    
    def _create_netlist_graph(self, module: NetlistModule) -> graphviz.Digraph:
        """
        Create a graph for a netlist module.
        
        Args:
            module: Netlist module to visualize
            
        Returns:
            Graphviz digraph
        """
        graph = graphviz.Digraph(name=f"{module.name}_netlist", format='png')
        graph.attr(rankdir='TB', size='10,10', ratio='compress')
        
        # Add ports
        for port in module.ports:
            shape = 'diamond' if port.direction == 'input' or port.direction == 'in' else 'box'
            color = self.colors["INPUT"] if port.direction == 'input' or port.direction == 'in' else self.colors["OUTPUT"]
            
            graph.node(
                f"port_{port.name}",
                label=port.name,
                shape=shape,
                style='filled',
                fillcolor=color,
                fontname='Arial',
                fontsize='12'
            )
        
        # Add resources
        for resource in module.resources:
            graph.node(
                f"res_{resource.name}",
                label=f"{resource.name}\\n{resource.type}",
                shape='box',
                style='filled',
                fillcolor='#e5e5e5',
                fontname='Arial',
                fontsize='12'
            )
        
        # Add operations
        for op in module.operations:
            op_color = self.colors.get(op.operation, self.colors["DEFAULT"])
            
            graph.node(
                f"op_{op.operation}_{op.control_step}",
                label=f"{op.operation}\\nStep {op.control_step}",
                shape='box',
                style='filled',
                fillcolor=op_color,
                fontname='Arial',
                fontsize='12'
            )
        
        # Add edges (simplified for now)
        # In a real implementation, we would need more info about connections
        
        return graph
    
    def _save_graph(self, graph: graphviz.Digraph, output_file: str) -> None:
        """
        Save a graph to a file.
        
        Args:
            graph: Graphviz graph
            output_file: Output file path
        """
        base, ext = os.path.splitext(output_file)
        graph.render(base, format=ext[1:], cleanup=True) 