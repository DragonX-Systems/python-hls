"""
Generate a GraphViz DOT representation of the hardware netlist microarchitecture.
"""

import networkx as nx
from typing import Dict, Optional, Any, Set, List, Tuple
from ..netlist.netlist import Netlist, NetlistModule, NetlistOperation, NetlistResource
import logging

# Operation to symbol mapping for visualization
op2sym_map = {
    "ADD": "+",
    "SUB": "-",
    "MUL": "×",
    "DIV": "÷",
    "MOD": "%",
    "POW": "^",
    "LSHIFT": "<<",
    "RSHIFT": ">>",
    "BIT_OR": "|",
    "BIT_AND": "&",
    "BIT_XOR": "⊕",
    "BIT_NOT": "~",
    "LOGIC_OR": "∨",
    "LOGIC_AND": "∧",
    "EQ": "==",
    "NEQ": "!=",
    "LT": "<",
    "LTE": "<=",
    "GT": ">",
    "GTE": ">=",
    "NOT": "¬",
    "NEG": "-",
    "ASSIGN": "=",
    "LOAD": "LD",
    "STORE": "ST",
    "RETURN": "RET",
    "CALL": "CALL"
}

def extract_netlist_connections(netlist):
    """Extract connections between resources from the netlist.
    
    This function analyzes the netlist to find data-flow connections
    between different hardware resources, memory interfaces, and
    control signals.
    
    Args:
        netlist: The netlist to analyze
        
    Returns:
        tuple: (connections, memory_connections, control_connections)
            - connections: List of data-flow connections
            - memory_connections: List of memory interface connections
            - control_connections: List of control signals from FSM
    """
    if not netlist or not hasattr(netlist, 'resources'):
        return [], [], []
    
    connections = []
    memory_connections = []
    control_connections = []
    
    # Organize resources by type for easier reference
    resources_by_type = {
        'ALU': [],
        'ADDER': [],
        'SUBTRACTOR': [],
        'BITOP': [],
        'COMPARATOR': [],
        'RELATIONALOP': [],
        'SHIFTER': [],
        'MUL': [],
        'DIV': [],
        'REG': [],
        'MEM': [],
        'MUX': [],
        'FIFO': [],
        'CROSSBAR': []
    }
    
    # Store resources by ID for lookup
    resources_by_id = {}
    
    # First pass: Categorize resources
    for resource in netlist.resources:
        # Check for either type or resource_type attribute
        if hasattr(resource, 'type'):
            resource_type = resource.type
        elif hasattr(resource, 'resource_type'):
            resource_type = resource.resource_type
        else:
            continue  # Skip resources without type information
            
        # Normalize resource type for categories
        if 'ALU' in resource_type:
            category = 'ALU'
        elif 'Adder' in resource_type:
            category = 'ADDER'
        elif 'Subtractor' in resource_type:
            category = 'SUBTRACTOR'
        elif 'BitOp' in resource_type:
            category = 'BITOP'
        elif 'Comparator' in resource_type:
            category = 'COMPARATOR'
        elif 'RelationalOp' in resource_type:
            category = 'RELATIONALOP'
        elif 'Shifter' in resource_type:
            category = 'SHIFTER'
        elif 'MUL' in resource_type or 'Multiplier' in resource_type:
            category = 'MUL'
        elif 'DIV' in resource_type or 'Divider' in resource_type:
            category = 'DIV'
        elif 'REG' in resource_type or 'Register' in resource_type:
            category = 'REG'
        elif 'MEM' in resource_type or 'Memory' in resource_type or 'BRAM' in resource_type or 'RAM' in resource_type:
            category = 'MEM'
        elif 'MUX' in resource_type:
            category = 'MUX'
        elif 'FIFO' in resource_type:
            category = 'FIFO'
        elif 'CROSSBAR' in resource_type:
            category = 'CROSSBAR'
        else:
            category = 'ALU'  # Default to ALU for operations
        
        if category in resources_by_type:
            resources_by_type[category].append(resource)
        
        # Store by ID for later lookup
        resources_by_id[resource.id if hasattr(resource, 'id') else id(resource)] = resource
    
    # Check if we should use consolidated blocks for any resource types
    use_alu_block = len(resources_by_type['ALU']) > 10
    use_adder_block = len(resources_by_type['ADDER']) > 10
    use_subtractor_block = len(resources_by_type['SUBTRACTOR']) > 10
    use_bitop_block = len(resources_by_type['BITOP']) > 10
    use_comparator_block = len(resources_by_type['COMPARATOR']) > 10
    use_relationalop_block = len(resources_by_type['RELATIONALOP']) > 10
    use_shifter_block = len(resources_by_type['SHIFTER']) > 10
    use_mul_block = len(resources_by_type['MUL']) > 10
    use_reg_block = len(resources_by_type['REG']) > 10
    
    # Second pass: Create connections based on operations and resource dependencies
    # Look at signals that connect resources
    if hasattr(netlist, 'signals'):
        for signal in netlist.signals:
            if hasattr(signal, 'source') and hasattr(signal, 'destinations'):
                source = signal.source
                for dest in signal.destinations:
                    if source in resources_by_id and dest in resources_by_id:
                        src_resource = resources_by_id[source]
                        dst_resource = resources_by_id[dest]
                        
                        src_type = get_resource_category(src_resource)
                        dst_type = get_resource_category(dst_resource)
                        
                        # Handle consolidated blocks
                        if src_type == 'ALU' and use_alu_block:
                            src_node = "alu_block"
                        elif src_type == 'ADDER' and use_adder_block:
                            src_node = "adder_block"
                        elif src_type == 'SUBTRACTOR' and use_subtractor_block:
                            src_node = "subtractor_block"
                        elif src_type == 'BITOP' and use_bitop_block:
                            src_node = "bitop_block"
                        elif src_type == 'COMPARATOR' and use_comparator_block:
                            src_node = "comparator_block"
                        elif src_type == 'RELATIONALOP' and use_relationalop_block:
                            src_node = "relationalop_block"
                        elif src_type == 'SHIFTER' and use_shifter_block:
                            src_node = "shifter_block"
                        elif src_type == 'MUL' and use_mul_block:
                            src_node = "mul_block"
                        elif src_type == 'REG' and use_reg_block:
                            src_node = "reg_block"
                        else:
                            src_id = getattr(src_resource, 'id', resources_by_type[src_type].index(src_resource))
                            src_node = f"{src_type.lower()}_{src_id}"
                        
                        if dst_type == 'ALU' and use_alu_block:
                            dst_node = "alu_block"
                        elif dst_type == 'ADDER' and use_adder_block:
                            dst_node = "adder_block"
                        elif dst_type == 'SUBTRACTOR' and use_subtractor_block:
                            dst_node = "subtractor_block"
                        elif dst_type == 'BITOP' and use_bitop_block:
                            dst_node = "bitop_block"
                        elif dst_type == 'COMPARATOR' and use_comparator_block:
                            dst_node = "comparator_block"
                        elif dst_type == 'RELATIONALOP' and use_relationalop_block:
                            dst_node = "relationalop_block"
                        elif dst_type == 'SHIFTER' and use_shifter_block:
                            dst_node = "shifter_block"
                        elif dst_type == 'MUL' and use_mul_block:
                            dst_node = "mul_block"
                        elif dst_type == 'REG' and use_reg_block:
                            dst_node = "reg_block"
                        else:
                            dst_id = getattr(dst_resource, 'id', resources_by_type[dst_type].index(dst_resource))
                            dst_node = f"{dst_type.lower()}_{dst_id}"
                        
                        connections.append(f"{src_node} -> {dst_node}")
    
    # If we don't have sufficient connections from the netlist signals,
    # create a comprehensive datapath with realistic connections
    if len(connections) < 5:
        # Clear existing connections to rebuild a complete datapath
        connections = []
        
        # Create a realistic processor-like datapath with consolidated blocks
        # 1. Memory to Registers (Memory Load)
        if resources_by_type['MEM'] and resources_by_type['REG']:
            for mem_idx, mem_resource in enumerate(resources_by_type['MEM']):
                mem_id = mem_resource.id if hasattr(mem_resource, 'id') else mem_idx
                
                if use_reg_block:
                    # Connect memory to consolidated register block
                    memory_connections.append(f"mem_{mem_id} -> reg_block [label=\"load\", color=green];")
                else:
                    # Connect to individual registers
                    for i in range(min(2, len(resources_by_type['REG']))):
                        reg_resource = resources_by_type['REG'][i]
                        reg_id = reg_resource.id if hasattr(reg_resource, 'id') else i
                        memory_connections.append(f"mem_{mem_id} -> reg_{reg_id} [label=\"load\", color=green];")
        
        # 2. Registers to Multiplexers (operand selection)
        if resources_by_type['REG'] and resources_by_type['MUX']:
            if use_reg_block:
                # Connect consolidated register block to multiplexers
                for mux_idx in range(min(2, len(resources_by_type['MUX']))):
                    mux_resource = resources_by_type['MUX'][mux_idx]
                    mux_id = mux_resource.id if hasattr(mux_resource, 'id') else mux_idx
                    connections.append(f"reg_block -> mux_{mux_id}")
            else:
                # Connect individual registers to multiplexers
                for reg_idx, reg_resource in enumerate(resources_by_type['REG']):
                    reg_id = reg_resource.id if hasattr(reg_resource, 'id') else reg_idx
                    # Each register can connect to multiple multiplexers
                    for mux_idx in range(min(2, len(resources_by_type['MUX']))):
                        mux_resource = resources_by_type['MUX'][mux_idx]
                        mux_id = mux_resource.id if hasattr(mux_resource, 'id') else mux_idx
                        connections.append(f"reg_{reg_id} -> mux_{mux_id}")
        
        # 3. Multiplexers to ALUs/MULs/DIVs (execution units)
        # Connect MUXes to ALUs
        if resources_by_type['MUX'] and resources_by_type['ALU']:
            for mux_idx, mux_resource in enumerate(resources_by_type['MUX']):
                mux_id = mux_resource.id if hasattr(mux_resource, 'id') else mux_idx
                
                if use_alu_block:
                    # Connect multiplexer to consolidated ALU block
                    connections.append(f"mux_{mux_id} -> alu_block")
                else:
                    # Connect to individual ALUs
                    for alu_idx in range(min(len(resources_by_type['ALU']), mux_idx + 2)):
                        alu_resource = resources_by_type['ALU'][alu_idx]
                        alu_id = alu_resource.id if hasattr(alu_resource, 'id') else alu_idx
                        connections.append(f"mux_{mux_id} -> alu_{alu_id}")
        
        # Connect MUXes to MULs
        if resources_by_type['MUX'] and resources_by_type['MUL']:
            for mux_idx, mux_resource in enumerate(resources_by_type['MUX']):
                mux_id = mux_resource.id if hasattr(mux_resource, 'id') else mux_idx
                
                if use_mul_block:
                    # Connect multiplexer to consolidated MUL block
                    connections.append(f"mux_{mux_id} -> mul_block")
                else:
                    # Connect to individual multipliers
                    if mux_idx < len(resources_by_type['MUL']):
                        mul_resource = resources_by_type['MUL'][mux_idx]
                        mul_id = mul_resource.id if hasattr(mul_resource, 'id') else mux_idx
                        connections.append(f"mux_{mux_id} -> mul_{mul_id}")
        
        # 4. ALUs/MULs/DIVs back to Registers (result storage)
        # ALUs to Registers
        if resources_by_type['ALU'] and resources_by_type['REG']:
            if use_alu_block and use_reg_block:
                # Connect consolidated ALU block to consolidated register block
                connections.append(f"alu_block -> reg_block")
            elif use_alu_block:
                # Connect consolidated ALU block to individual registers
                for reg_idx in range(min(2, len(resources_by_type['REG']))):
                    reg_resource = resources_by_type['REG'][reg_idx]
                    reg_id = reg_resource.id if hasattr(reg_resource, 'id') else reg_idx
                    connections.append(f"alu_block -> reg_{reg_id}")
            elif use_reg_block:
                # Connect individual ALUs to consolidated register block
                for alu_idx, alu_resource in enumerate(resources_by_type['ALU']):
                    alu_id = alu_resource.id if hasattr(alu_resource, 'id') else alu_idx
                    connections.append(f"alu_{alu_id} -> reg_block")
            else:
                # Connect individual ALUs to individual registers
                for alu_idx, alu_resource in enumerate(resources_by_type['ALU']):
                    alu_id = alu_resource.id if hasattr(alu_resource, 'id') else alu_idx
                    reg_idx = min(alu_idx, len(resources_by_type['REG']) - 1)
                    reg_resource = resources_by_type['REG'][reg_idx]
                    reg_id = reg_resource.id if hasattr(reg_resource, 'id') else reg_idx
                    connections.append(f"alu_{alu_id} -> reg_{reg_id}")
        
        # MULs to Registers
        if resources_by_type['MUL'] and resources_by_type['REG']:
            if use_mul_block and use_reg_block:
                # Connect consolidated MUL block to consolidated register block
                connections.append(f"mul_block -> reg_block")
            elif use_mul_block:
                # Connect consolidated MUL block to individual registers
                for reg_idx in range(min(2, len(resources_by_type['REG']))):
                    reg_resource = resources_by_type['REG'][reg_idx]
                    reg_id = reg_resource.id if hasattr(reg_resource, 'id') else reg_idx
                    connections.append(f"mul_block -> reg_{reg_id}")
            elif use_reg_block:
                # Connect individual MULs to consolidated register block
                for mul_idx, mul_resource in enumerate(resources_by_type['MUL']):
                    mul_id = mul_resource.id if hasattr(mul_resource, 'id') else mul_idx
                    connections.append(f"mul_{mul_id} -> reg_block")
            else:
                # Connect individual MULs to individual registers
                for mul_idx, mul_resource in enumerate(resources_by_type['MUL']):
                    mul_id = mul_resource.id if hasattr(mul_resource, 'id') else mul_idx
                    if len(resources_by_type['REG']) > 0:
                        reg_idx = min(mul_idx, len(resources_by_type['REG']) - 1)
                        reg_resource = resources_by_type['REG'][reg_idx]
                        reg_id = reg_resource.id if hasattr(reg_resource, 'id') else reg_idx
                        connections.append(f"mul_{mul_id} -> reg_{reg_id}")
        
        # 5. Registers to Memory (Memory Store)
        if resources_by_type['REG'] and resources_by_type['MEM']:
            if use_reg_block:
                # Connect consolidated register block to memory
                for mem_idx, mem_resource in enumerate(resources_by_type['MEM']):
                    mem_id = mem_resource.id if hasattr(mem_resource, 'id') else mem_idx
                    memory_connections.append(f"reg_block -> mem_{mem_id} [label=\"store\", color=red];")
            else:
                # Connect individual registers to memory
                for reg_idx, reg_resource in enumerate(resources_by_type['REG']):
                    reg_id = reg_resource.id if hasattr(reg_resource, 'id') else reg_idx
                    # Connect some registers to memory for store operations
                    if reg_idx < len(resources_by_type['MEM']):
                        mem_resource = resources_by_type['MEM'][reg_idx]
                        mem_id = mem_resource.id if hasattr(mem_resource, 'id') else reg_idx
                        memory_connections.append(f"reg_{reg_id} -> mem_{mem_id} [label=\"store\", color=red];")
        
        # 6. Create feedback paths (pipeline/datapath forwarding)
        # ALUs to MUXes (forwarding paths)
        if resources_by_type['ALU'] and resources_by_type['MUX']:
            if use_alu_block:
                # Connect consolidated ALU block to MUXes for forwarding
                for mux_idx in range(min(2, len(resources_by_type['MUX']))):
                    mux_resource = resources_by_type['MUX'][mux_idx]
                    mux_id = mux_resource.id if hasattr(mux_resource, 'id') else mux_idx
                    connections.append(f"alu_block -> mux_{mux_id} [color=blue, style=dashed, label=\"fwd\"];")
            else:
                # Connect individual ALUs to MUXes for forwarding
                for alu_idx, alu_resource in enumerate(resources_by_type['ALU']):
                    alu_id = alu_resource.id if hasattr(alu_resource, 'id') else alu_idx
                    # Connect some ALUs back to MUXes for forwarding
                    if alu_idx < len(resources_by_type['MUX']):
                        mux_resource = resources_by_type['MUX'][alu_idx]
                        mux_id = mux_resource.id if hasattr(mux_resource, 'id') else alu_idx
                        connections.append(f"alu_{alu_id} -> mux_{mux_id} [color=blue, style=dashed, label=\"fwd\"];")
    
    # Add control connections from FSM to all functional units
    # For consolidated blocks
    if use_alu_block:
        control_connections.append(f"FSM -> alu_block [label=\"control\", style=dashed, color=orange];")
    if use_mul_block:
        control_connections.append(f"FSM -> mul_block [label=\"control\", style=dashed, color=orange];")
    if use_reg_block:
        control_connections.append(f"FSM -> reg_block [label=\"control\", style=dashed, color=orange];")
    
    # For individual resources
    for resource_type, resources in resources_by_type.items():
        # Skip if using a consolidated block for this resource type
        if (resource_type == 'ALU' and use_alu_block) or \
           (resource_type == 'MUL' and use_mul_block) or \
           (resource_type == 'REG' and use_reg_block):
            continue
            
        for i, resource in enumerate(resources):
            resource_id = resource.id if hasattr(resource, 'id') else i
            control_connections.append(f"FSM -> {resource_type.lower()}_{resource_id} [label=\"control\", style=dashed, color=orange];")
    
    # Ensure all resources have at least one control connection
    # Check for resources with no control connections
    controlled_resources = set()
    for conn in control_connections:
        parts = conn.split(' ')
        if len(parts) > 2:
            dst = parts[2].strip()
            controlled_resources.add(dst)
    
    # Add control connections for any missed resources
    for resource_type, resources in resources_by_type.items():
        # Skip if using a consolidated block for this resource type
        if (resource_type == 'ALU' and use_alu_block) or \
           (resource_type == 'MUL' and use_mul_block) or \
           (resource_type == 'REG' and use_reg_block):
            continue
            
        for i, resource in enumerate(resources):
            resource_id = resource.id if hasattr(resource, 'id') else i
            resource_name = f"{resource_type.lower()}_{resource_id}"
            if resource_name not in controlled_resources:
                control_connections.append(f"FSM -> {resource_name} [label=\"control\", style=dashed, color=orange];")
    
    return connections, memory_connections, control_connections

def get_resource_category(resource):
    """Determine the category of a netlist resource."""
    # Check for either type or resource_type attribute
    if hasattr(resource, 'type'):
        resource_type = resource.type
    elif hasattr(resource, 'resource_type'):
        resource_type = resource.resource_type
    else:
        return 'ALU'  # Default
        
    if 'ALU' in resource_type:
        return 'ALU'
    elif 'Adder' in resource_type:
        return 'ADDER'
    elif 'Subtractor' in resource_type:
        return 'SUBTRACTOR'
    elif 'BitOp' in resource_type:
        return 'BITOP'
    elif 'Comparator' in resource_type:
        return 'COMPARATOR'
    elif 'RelationalOp' in resource_type:
        return 'RELATIONALOP'
    elif 'Shifter' in resource_type:
        return 'SHIFTER'
    elif 'MUL' in resource_type or 'Multiplier' in resource_type:
        return 'MUL'
    elif 'DIV' in resource_type or 'Divider' in resource_type:
        return 'DIV'
    elif 'REG' in resource_type or 'Register' in resource_type:
        return 'REG'
    elif 'MEM' in resource_type or 'Memory' in resource_type or 'BRAM' in resource_type or 'RAM' in resource_type:
        return 'MEM'
    elif 'MUX' in resource_type:
        return 'MUX'
    elif 'FIFO' in resource_type:
        return 'FIFO'
    elif 'CROSSBAR' in resource_type:
        return 'CROSSBAR'
    else:
        return 'ALU'  # Default to ALU for operations

def operation_to_resource_type(op_name: str) -> str:
    """Map operation names to resource types.
    
    Args:
        op_name: Operation name
        
    Returns:
        Corresponding resource type
    """
    op_to_resource = {
        "ADD": "Adder_32bit",
        "SUB": "Subtractor_32bit",
        "MUL": "Multiplier_32bit",
        "DIV": "Divider_32bit",
        "MOD": "ALU_32bit",
        "POW": "ALU_32bit",
        "LSHIFT": "Shifter_32bit",
        "RSHIFT": "Shifter_32bit",
        "BIT_OR": "BitOp_32bit",
        "BIT_AND": "BitOp_32bit",
        "BIT_XOR": "BitOp_32bit",
        "LOGIC_OR": "BitOp_32bit",
        "LOGIC_AND": "BitOp_32bit",
        "EQ": "Comparator_32bit",
        "NEQ": "Comparator_32bit",
        "LT": "RelationalOp_32bit",
        "LTE": "RelationalOp_32bit",
        "GT": "RelationalOp_32bit",
        "GTE": "RelationalOp_32bit",
        "NEG": "Subtractor_32bit",
        "NOT": "BitOp_32bit",
        "BIT_NOT": "BitOp_32bit",
        "ASSIGN": "Register_32bit",
        "RETURN": "Register_32bit",
        "STORE": "Memory_1KB",
        "LOAD": "Memory_1KB",
        "CALL": "ALU_32bit",
        # FIFO and Crossbar operations
        "FIFO_WRITE": "FIFO_32bit",
        "FIFO_READ": "FIFO_32bit",
        "CROSSBAR_ROUTE": "Crossbar_32bit",
        # AXI-Stream operations
        "AXIS_FIFO_WRITE": "FIFO_AXIS_32bit",
        "AXIS_FIFO_READ": "FIFO_AXIS_32bit",
        # AXI-Lite operations
        "AXILITE_FIFO_WRITE": "FIFO_AXILITE_32bit",
        "AXILITE_FIFO_READ": "FIFO_AXILITE_32bit"
    }
    
    return op_to_resource.get(op_name, "ALU_32bit")

def generate_hardware_dot(dfg=None, hw_allocated=None, schedule=None, control_signals=None, netlist=None, filename="hardware_diagram.dot", operations=None):
    """Generate a GraphViz DOT representation of the hardware netlist.
    
    This function creates a visual representation of the hardware microarchitecture
    generated from the DFG or netlist. It shows functional units, memories, registers,
    and the connections between them.
    
    Args:
        dfg: Optional Data Flow Graph to visualize
        hw_allocated: Optional dictionary of allocated hardware resources
        schedule: Optional schedule information mapping node_id to control step
        control_signals: Optional control signals information
        netlist: Optional Netlist object to visualize
        filename: Output filename for the DOT file
        operations: Optional list of operations to visualize
        
    Returns:
        str: The DOT content as a string
    """
    # Ensure we have valid inputs for visualization
    if not dfg and not netlist:
        logging.warning("No DFG or netlist provided for visualization. Using minimal defaults.")
        return "digraph G { label=\"No hardware resources to visualize\"; }"
    
    # If operations not provided, initialize as empty list
    if operations is None:
        operations = []
    
    # Initialize resource counter variables
    scratchpad_count = 0
    fifo_count = 0
    crossbar_count = 0
    
    # If hw_allocated not provided, create it from netlist
    if not hw_allocated:
        hw_allocated = {}
        
        # Analyze the netlist to identify resources if provided
        if netlist and hasattr(netlist, 'resources'):
            for resource in netlist.resources:
                # Check for either type or resource_type attribute
                if hasattr(resource, 'type'):
                    resource_type = resource.type
                elif hasattr(resource, 'resource_type'):
                    resource_type = resource.resource_type
                else:
                    continue
                    
                category = get_resource_category(resource)
                if category not in hw_allocated:
                    hw_allocated[category] = []
                hw_allocated[category].append(resource)
    
    # Initialize DOT content
    dot_content = [
        "digraph G {",
        "    compound=true;",
        "    fontname=\"Helvetica\";",
        "    fontsize=10;",
        "    rankdir=TB;",
        "    ranksep=0.5;",
        "    nodesep=0.5;",
        "    node [fontname=\"Helvetica\", fontsize=10, style=filled];",
        "    edge [fontname=\"Helvetica\", fontsize=8];"
    ]
    
    # Create subgraph for control units
    dot_content.extend([
        "    // Control Units",
        "    subgraph cluster_control {",
        "        label=\"Control Units\";",
        "        style=filled;",
        "        color=lightgrey;",
        "        FSM [label=\"FSM\", shape=box, fillcolor=gold];",
        "        clock [label=\"Clock\", shape=circle, fillcolor=lightskyblue];",
        "        reset [label=\"Reset\", shape=circle, fillcolor=lightcoral];",
        "    }"
    ])
    
    # Create subgraph for computational units (ALUs, MULs, DIVs)
    dot_content.extend([
        "    // Computational Units",
        "    subgraph cluster_compute {",
        "        label=\"Computational Units\";",
        "        style=filled;",
        "        color=lightblue;"
    ])
    
    # Add ALU units
    alu_count = 0
    if 'ALU' in hw_allocated and hw_allocated['ALU']:
        alu_count = len(hw_allocated['ALU'])
        if alu_count > 10:
            # Show a single large block for many ALUs
            dot_content.append(f"        alu_block [label=\"{alu_count}\\nALUs\", shape=box, width=2, height=1.5, fillcolor=lightyellow];")
        else:
            # Show individual ALUs
            for i, resource in enumerate(hw_allocated['ALU']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        alu_{resource_id} [label=\"ALU\\n{resource_id}\", shape=box, fillcolor=lightyellow];")
    
    # Ensure we have at least one ALU for visualization
    if alu_count == 0:
        dot_content.append("        alu_0 [label=\"ALU\\n0\", shape=box, fillcolor=lightyellow];")
        alu_count = 1
        if 'ALU' not in hw_allocated:
            hw_allocated['ALU'] = []
    
    # Add Adder units
    adder_count = 0
    if 'ADDER' in hw_allocated and hw_allocated['ADDER']:
        adder_count = len(hw_allocated['ADDER'])
        if adder_count > 10:
            # Show a single large block for many Adders
            dot_content.append(f"        adder_block [label=\"{adder_count}\\nAdders\", shape=box, width=2, height=1.5, fillcolor=lightcyan];")
        else:
            # Show individual Adders
            for i, resource in enumerate(hw_allocated['ADDER']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        adder_{resource_id} [label=\"ADD\\n{resource_id}\", shape=box, fillcolor=lightcyan];")
                
    # Add Subtractor units
    subtractor_count = 0
    if 'SUBTRACTOR' in hw_allocated and hw_allocated['SUBTRACTOR']:
        subtractor_count = len(hw_allocated['SUBTRACTOR'])
        if subtractor_count > 10:
            # Show a single large block for many Subtractors
            dot_content.append(f"        subtractor_block [label=\"{subtractor_count}\\nSubtractors\", shape=box, width=2, height=1.5, fillcolor=lavender];")
        else:
            # Show individual Subtractors
            for i, resource in enumerate(hw_allocated['SUBTRACTOR']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        subtractor_{resource_id} [label=\"SUB\\n{resource_id}\", shape=box, fillcolor=lavender];")
                
    # Add BitOp units
    bitop_count = 0
    if 'BITOP' in hw_allocated and hw_allocated['BITOP']:
        bitop_count = len(hw_allocated['BITOP'])
        if bitop_count > 10:
            # Show a single large block for many BitOps
            dot_content.append(f"        bitop_block [label=\"{bitop_count}\\nBitOps\", shape=box, width=2, height=1.5, fillcolor=honeydew];")
        else:
            # Show individual BitOps
            for i, resource in enumerate(hw_allocated['BITOP']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        bitop_{resource_id} [label=\"BIT\\n{resource_id}\", shape=box, fillcolor=honeydew];")
                
    # Add Comparator units
    comparator_count = 0
    if 'COMPARATOR' in hw_allocated and hw_allocated['COMPARATOR']:
        comparator_count = len(hw_allocated['COMPARATOR'])
        if comparator_count > 10:
            # Show a single large block for many Comparators
            dot_content.append(f"        comparator_block [label=\"{comparator_count}\\nComparators\", shape=box, width=2, height=1.5, fillcolor=azure];")
        else:
            # Show individual Comparators
            for i, resource in enumerate(hw_allocated['COMPARATOR']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        comparator_{resource_id} [label=\"CMP\\n{resource_id}\", shape=box, fillcolor=azure];")
                
    # Add RelationalOp units
    relop_count = 0
    if 'RELATIONALOP' in hw_allocated and hw_allocated['RELATIONALOP']:
        relop_count = len(hw_allocated['RELATIONALOP'])
        if relop_count > 10:
            # Show a single large block for many RelationalOps
            dot_content.append(f"        relationalop_block [label=\"{relop_count}\\nRelOps\", shape=box, width=2, height=1.5, fillcolor=aliceblue];")
        else:
            # Show individual RelationalOps
            for i, resource in enumerate(hw_allocated['RELATIONALOP']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        relationalop_{resource_id} [label=\"REL\\n{resource_id}\", shape=box, fillcolor=aliceblue];")
                
    # Add Shifter units
    shifter_count = 0
    if 'SHIFTER' in hw_allocated and hw_allocated['SHIFTER']:
        shifter_count = len(hw_allocated['SHIFTER'])
        if shifter_count > 10:
            # Show a single large block for many Shifters
            dot_content.append(f"        shifter_block [label=\"{shifter_count}\\nShifters\", shape=box, width=2, height=1.5, fillcolor=ghostwhite];")
        else:
            # Show individual Shifters
            for i, resource in enumerate(hw_allocated['SHIFTER']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        shifter_{resource_id} [label=\"SHF\\n{resource_id}\", shape=box, fillcolor=ghostwhite];")
    
    # Add MUL units
    mul_count = 0
    if 'Multiplier' in hw_allocated and hw_allocated['Multiplier']:
        mul_count = len(hw_allocated['Multiplier'])
        if mul_count > 10:
            # Show a single large block for many multipliers
            dot_content.append(f"        mul_block [label=\"{mul_count}\\nMultipliers\", shape=box, width=2, height=1.5, fillcolor=lightpink];")
        else:
            # Show individual multipliers
            for i, resource in enumerate(hw_allocated['Multiplier']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        mul_{resource_id} [label=\"MUL\\n{resource_id}\", shape=box, fillcolor=lightpink];")
    
    # Ensure we have at least one multiplier for SPMM operations
    if mul_count == 0 and operations and any(op.startswith('MUL') for op in operations):
        dot_content.append("        mul_0 [label=\"MUL\\n0\", shape=box, fillcolor=lightpink];")
        mul_count = 1
        if 'Multiplier' not in hw_allocated:
            hw_allocated['Multiplier'] = []
    
    # Add DIV units
    div_count = 0
    if 'Divider' in hw_allocated and hw_allocated['Divider']:
        div_count = len(hw_allocated['Divider'])
        if div_count > 10:
            # Show a single large block for many Dividers
            dot_content.append(f"        div_block [label=\"{div_count}\\nDividers\", shape=box, width=2, height=1.5, fillcolor=lightgreen];")
        else:
            # Show individual Dividers
            for resource in hw_allocated['Divider']:
                resource_id = resource.id if hasattr(resource, 'id') else div_count
                dot_content.append(f"        div_{resource_id} [label=\"DIV\\n{resource_id}\", shape=box, fillcolor=lightgreen];")
                div_count += 1
    
    dot_content.append("    }")  # Close computational units subgraph
    
    # Create subgraph for registers
    dot_content.extend([
        "    // Registers",
        "    subgraph cluster_registers {",
        "        label=\"Registers\";",
        "        style=filled;",
        "        color=lightgreen;"
    ])
    
    # Add register units
    reg_count = 0
    if 'Register' in hw_allocated and hw_allocated['Register']:
        reg_count = len(hw_allocated['Register'])
        if reg_count > 10:
            # Show a single large block for many registers
            dot_content.append(f"        reg_block [label=\"{reg_count}\\nRegisters\", shape=box, width=2, height=1.5, fillcolor=lightgreen];")
        else:
            # Show individual registers
            for i, resource in enumerate(hw_allocated['Register']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        reg_{resource_id} [label=\"REG\\n{resource_id}\", shape=box, fillcolor=lightgreen];")
    
    # Ensure we have at least two registers for visualization
    if reg_count < 2:
        for i in range(reg_count, 2):
            dot_content.append(f"        reg_{i} [label=\"REG\\n{i}\", shape=box, fillcolor=lightgreen];")
        reg_count = 2
    
    dot_content.append("    }")
    
    # Create subgraph for memory units
    dot_content.extend([
        "    // Memory Units",
        "    subgraph cluster_memory {",
        "        label=\"Memory Units\";",
        "        style=filled;",
        "        color=lightcoral;"
    ])
    
    # Add memory units
    mem_count = 0
    scratchpad_count = 0
    if 'Memory' in hw_allocated and hw_allocated['Memory']:
        for resource in hw_allocated['Memory']:
            resource_id = resource.id if hasattr(resource, 'id') else mem_count
            dot_content.append(f"        mem_{resource_id} [label=\"MEM\\n{resource_id}\", shape=cylinder, fillcolor=mistyrose];")
            mem_count += 1
    
    # Ensure we have at least one memory unit for visualization
    if mem_count == 0:
        dot_content.append("        mem_0 [label=\"MEM\\n0\", shape=cylinder, fillcolor=mistyrose];")
        if 'Memory' not in hw_allocated:
            hw_allocated['Memory'] = []
    
    dot_content.append("    }")
    
    # Create subgraph for multiplexers
    dot_content.extend([
        "    // Multiplexers",
        "    subgraph cluster_mux {",
        "        label=\"Multiplexers\";",
        "        style=filled;",
        "        color=lightyellow;"
    ])
    
    # Add multiplexer units
    mux_count = 0
    use_mux_block = False
    if 'MUX' in hw_allocated and hw_allocated['MUX']:
        mux_count = len(hw_allocated['MUX'])
        # If we have more than 4 MUXes, use a single block representation
        if mux_count > 4:
            use_mux_block = True
            dot_content.append(f"        mux_block [label=\"{mux_count}\\nMUXes\", shape=box, width=2, height=1.5, fillcolor=wheat];")
        else:
            # Show individual MUXes when count is small
            for resource in hw_allocated['MUX']:
                resource_id = resource.id if hasattr(resource, 'id') else mux_count
                dot_content.append(f"        mux_{resource_id} [label=\"MUX\\n{resource_id}\", shape=trapezium, fillcolor=wheat];")
                mux_count += 1
    else:
        # Use a single MUX as fallback if none are allocated
        dot_content.append(f"        mux_0 [label=\"MUX\\n0\", shape=trapezium, fillcolor=wheat];")
        mux_count = 1
    
    dot_content.append("    }")  # Close multiplexers subgraph
    
    # Extract connections from netlist or create comprehensive default connections
    connections = []
    memory_connections = []
    control_connections = []
    
    # Use the real netlist if available to get better connection information
    if False:
        # Use extract_netlist_connections to get the connections
        connections, memory_connections, control_connections = extract_netlist_connections(netlist)
    else:
        # Create comprehensive connections for a processor-like datapath
        # 1. Connect all registers to all multiplexers (full connectivity)
        if reg_count > 10:
            # Connect the consolidated register block to multiplexers
            if use_mux_block:
                connections.append(f"    reg_block -> mux_block [color=black];")
            else:
                for j in range(mux_count):
                    connections.append(f"    reg_block -> mux_{j} [color=black];")
        else:
            # Connect individual registers to multiplexers
            if use_mux_block:
                for i in range(reg_count):
                    connections.append(f"    reg_{i} -> mux_block [color=black];")
            else:
                for i in range(reg_count):
                    for j in range(mux_count):
                        connections.append(f"    reg_{i} -> mux_{j} [color=black];")
        
        # Add FSM control connections to all components
        # FSM control connections to computational units
        if alu_count > 10:
            control_connections.append(f"    FSM -> alu_block [label=\"control\", style=dashed, color=orange];")
        else:
            for i in range(alu_count):
                control_connections.append(f"    FSM -> alu_{i} [label=\"control\", style=dashed, color=orange];")
                
        if adder_count > 10:
            control_connections.append(f"    FSM -> adder_block [label=\"control\", style=dashed, color=orange];")
        elif adder_count > 0:
            for i in range(adder_count):
                control_connections.append(f"    FSM -> adder_{i} [label=\"control\", style=dashed, color=orange];")

        if subtractor_count > 10:
            control_connections.append(f"    FSM -> subtractor_block [label=\"control\", style=dashed, color=orange];")
        elif subtractor_count > 0:
            for i in range(subtractor_count):
                control_connections.append(f"    FSM -> subtractor_{i} [label=\"control\", style=dashed, color=orange];")

        if bitop_count > 10:
            control_connections.append(f"    FSM -> bitop_block [label=\"control\", style=dashed, color=orange];")
        elif bitop_count > 0:
            for i in range(bitop_count):
                control_connections.append(f"    FSM -> bitop_{i} [label=\"control\", style=dashed, color=orange];")

        if comparator_count > 10:
            control_connections.append(f"    FSM -> comparator_block [label=\"control\", style=dashed, color=orange];")
        elif comparator_count > 0:
            for i in range(comparator_count):
                control_connections.append(f"    FSM -> comparator_{i} [label=\"control\", style=dashed, color=orange];")

        if relop_count > 10:
            control_connections.append(f"    FSM -> relationalop_block [label=\"control\", style=dashed, color=orange];")
        elif relop_count > 0:
            for i in range(relop_count):
                control_connections.append(f"    FSM -> relationalop_{i} [label=\"control\", style=dashed, color=orange];")

        if shifter_count > 10:
            control_connections.append(f"    FSM -> shifter_block [label=\"control\", style=dashed, color=orange];")
        elif shifter_count > 0:
            for i in range(shifter_count):
                control_connections.append(f"    FSM -> shifter_{i} [label=\"control\", style=dashed, color=orange];")

        if mul_count > 10:
            control_connections.append(f"    FSM -> mul_block [label=\"control\", style=dashed, color=orange];")
        elif mul_count > 0:
            for i in range(mul_count):
                control_connections.append(f"    FSM -> mul_{i} [label=\"control\", style=dashed, color=orange];")

        if div_count > 10:
            control_connections.append(f"    FSM -> div_block [label=\"control\", style=dashed, color=orange];")
        elif div_count > 0:
            for i in range(div_count):
                control_connections.append(f"    FSM -> div_{i} [label=\"control\", style=dashed, color=orange];")

        # FSM control connections to memory and registers
        if reg_count > 10:
            control_connections.append(f"    FSM -> reg_block [label=\"control\", style=dashed, color=orange];")
        else:
            for i in range(reg_count):
                control_connections.append(f"    FSM -> reg_{i} [label=\"control\", style=dashed, color=orange];")

        for i in range(mem_count):
            control_connections.append(f"    FSM -> mem_{i} [label=\"control\", style=dashed, color=orange];")

        for i in range(scratchpad_count):
            control_connections.append(f"    FSM -> spad_{i} [label=\"control\", style=dashed, color=orange];")

        # FSM control connections to multiplexers
        if use_mux_block:
            control_connections.append(f"    FSM -> mux_block [label=\"control\", style=dashed, color=orange];")
        else:
            for i in range(mux_count):
                control_connections.append(f"    FSM -> mux_{i} [label=\"control\", style=dashed, color=orange];")

        # 2. Connect multiplexers to computational units (execution paths)
        if use_mux_block:
            # Connect consolidated MUX block to computational units
            if alu_count > 10:
                connections.append(f"    mux_block -> alu_block [color=black];")
            else:
                for j in range(alu_count):
                    connections.append(f"    mux_block -> alu_{j} [color=black];")
            
            # Connect to adders
            if adder_count > 10:
                connections.append(f"    mux_block -> adder_block [color=black];")
            elif adder_count > 0:
                for j in range(adder_count):
                    connections.append(f"    mux_block -> adder_{j} [color=black];")
            
            # Connect to subtractors
            if subtractor_count > 10:
                connections.append(f"    mux_block -> subtractor_block [color=black];")
            elif subtractor_count > 0:
                for j in range(subtractor_count):
                    connections.append(f"    mux_block -> subtractor_{j} [color=black];")
            
            # Connect to bit operations
            if bitop_count > 10:
                connections.append(f"    mux_block -> bitop_block [color=black];")
            elif bitop_count > 0:
                for j in range(bitop_count):
                    connections.append(f"    mux_block -> bitop_{j} [color=black];")
            
            # Connect to comparators
            if comparator_count > 10:
                connections.append(f"    mux_block -> comparator_block [color=black];")
            elif comparator_count > 0:
                for j in range(comparator_count):
                    connections.append(f"    mux_block -> comparator_{j} [color=black];")
            
            # Connect to relational operators
            if relop_count > 10:
                connections.append(f"    mux_block -> relationalop_block [color=black];")
            elif relop_count > 0:
                for j in range(relop_count):
                    connections.append(f"    mux_block -> relationalop_{j} [color=black];")
            
            # Connect to shifters
            if shifter_count > 10:
                connections.append(f"    mux_block -> shifter_block [color=black];")
            elif shifter_count > 0:
                for j in range(shifter_count):
                    connections.append(f"    mux_block -> shifter_{j} [color=black];")
            
            # Connect to multipliers
            if mul_count > 10:
                connections.append(f"    mux_block -> mul_block [color=black];")
            elif mul_count > 0:
                for j in range(mul_count):
                    connections.append(f"    mux_block -> mul_{j} [color=black];")
            
            # Connect to dividers
            if div_count > 10:
                connections.append(f"    mux_block -> div_block [color=black];")
            elif div_count > 0:
                for j in range(div_count):
                    connections.append(f"    mux_block -> div_{j} [color=black];")
        else:
            # Connect individual MUXes to computational units when not using a block
            for i in range(mux_count):
                # Connect to ALUs
                if alu_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> alu_block [color=black];")
                else:
                    for j in range(alu_count):
                        connections.append(f"    mux_{i % mux_count} -> alu_{j % alu_count} [color=black];")
                
                # Connect to adders
                if adder_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> adder_block [color=black];")
                elif adder_count > 0:
                    for j in range(adder_count):
                        connections.append(f"    mux_{i % mux_count} -> adder_{j % adder_count} [color=black];")
                
                # Connect to subtractors
                if subtractor_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> subtractor_block [color=black];")
                elif subtractor_count > 0:
                    for j in range(subtractor_count):
                        connections.append(f"    mux_{i % mux_count} -> subtractor_{j % subtractor_count} [color=black];")
                
                # Connect to bit operations
                if bitop_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> bitop_block [color=black];")
                elif bitop_count > 0:
                    for j in range(bitop_count):
                        connections.append(f"    mux_{i % mux_count} -> bitop_{j % bitop_count} [color=black];")
                
                # Connect to comparators
                if comparator_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> comparator_block [color=black];")
                elif comparator_count > 0:
                    for j in range(comparator_count):
                        connections.append(f"    mux_{i % mux_count} -> comparator_{j % comparator_count} [color=black];")
                
                # Connect to relational operators
                if relop_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> relationalop_block [color=black];")
                elif relop_count > 0:
                    for j in range(relop_count):
                        connections.append(f"    mux_{i % mux_count} -> relationalop_{j % relop_count} [color=black];")
                
                # Connect to shifters
                if shifter_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> shifter_block [color=black];")
                elif shifter_count > 0:
                    for j in range(shifter_count):
                        connections.append(f"    mux_{i % mux_count} -> shifter_{j % shifter_count} [color=black];")
                
                # Connect to multipliers
                if mul_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> mul_block [color=black];")
                elif mul_count > 0:
                    for j in range(mul_count):
                        connections.append(f"    mux_{i % mux_count} -> mul_{j % mul_count} [color=black];")
                
                # Connect to dividers
                if div_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> div_block [color=black];")
                elif div_count > 0:
                    for j in range(div_count):
                        connections.append(f"    mux_{i % mux_count} -> div_{j % div_count} [color=black];")
        
        # 3. Connect computational units back to registers (result paths)
        # ALUs to registers
        if alu_count > 10:
            if reg_count > 10:
                connections.append(f"    alu_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    alu_block -> reg_{j} [color=black];")
        else:
            for i in range(alu_count):
                if reg_count > 10:
                    connections.append(f"    alu_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    alu_{i} -> reg_{j} [color=black];")
        
        # Adders to registers
        if adder_count > 10:
            if reg_count > 10:
                connections.append(f"    adder_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    adder_block -> reg_{j} [color=black];")
        elif adder_count > 0:
            for i in range(adder_count):
                if reg_count > 10:
                    connections.append(f"    adder_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    adder_{i} -> reg_{j} [color=black];")
        
        # Subtractors to registers
        if subtractor_count > 10:
            if reg_count > 10:
                connections.append(f"    subtractor_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    subtractor_block -> reg_{j} [color=black];")
        elif subtractor_count > 0:
            for i in range(subtractor_count):
                if reg_count > 10:
                    connections.append(f"    subtractor_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    subtractor_{i} -> reg_{j} [color=black];")
        
        # BitOps to registers
        if bitop_count > 10:
            if reg_count > 10:
                connections.append(f"    bitop_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    bitop_block -> reg_{j} [color=black];")
        elif bitop_count > 0:
            for i in range(bitop_count):
                if reg_count > 10:
                    connections.append(f"    bitop_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    bitop_{i} -> reg_{j} [color=black];")
        
        # Comparators to registers
        if comparator_count > 10:
            if reg_count > 10:
                connections.append(f"    comparator_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    comparator_block -> reg_{j} [color=black];")
        elif comparator_count > 0:
            for i in range(comparator_count):
                if reg_count > 10:
                    connections.append(f"    comparator_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    comparator_{i} -> reg_{j} [color=black];")
        
        # RelationalOps to registers
        if relop_count > 10:
            if reg_count > 10:
                connections.append(f"    relationalop_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    relationalop_block -> reg_{j} [color=black];")
        elif relop_count > 0:
            for i in range(relop_count):
                if reg_count > 10:
                    connections.append(f"    relationalop_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    relationalop_{i} -> reg_{j} [color=black];")
        
        # Shifters to registers
        if shifter_count > 10:
            if reg_count > 10:
                connections.append(f"    shifter_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    shifter_block -> reg_{j} [color=black];")
        elif shifter_count > 0:
            for i in range(shifter_count):
                if reg_count > 10:
                    connections.append(f"    shifter_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    shifter_{i} -> reg_{j} [color=black];")
        
        # Multipliers to registers
        if mul_count > 10:
            if reg_count > 10:
                connections.append(f"    mul_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    mul_block -> reg_{j} [color=black];")
        elif mul_count > 0:
            for i in range(mul_count):
                if reg_count > 10:
                    connections.append(f"    mul_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    mul_{i} -> reg_{j} [color=black];")
        
        # Dividers to registers
        if div_count > 10:
            if reg_count > 10:
                connections.append(f"    div_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    div_block -> reg_{j} [color=black];")
        elif div_count > 0:
            for i in range(div_count):
                if reg_count > 10:
                    connections.append(f"    div_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    div_{i} -> reg_{j} [color=black];")
        
        # 4. Connect memory units
        if reg_count > 10:
            # Memory connections for consolidated register block
            if mem_count > 0:
                memory_connections.append(f"    mem_0 -> reg_block [label=\"load\", color=green];")
                memory_connections.append(f"    reg_block -> mem_0 [label=\"store\", color=red];")
            if scratchpad_count > 0:
                memory_connections.append(f"    spad_0 -> reg_block [label=\"load\", color=green];")
                memory_connections.append(f"    reg_block -> spad_0 [label=\"store\", color=red];")
        else:
            # Memory connections for individual registers
            for i in range(min(reg_count, 2)):
                # Load paths (memory to register)
                if mem_count > 0:
                    memory_connections.append(f"    mem_0 -> reg_{i} [label=\"load\", color=green];")
                if scratchpad_count > 0:
                    memory_connections.append(f"    spad_0 -> reg_{i} [label=\"load\", color=green];")
                
                # Store paths (register to memory)
                if mem_count > 0:
                    memory_connections.append(f"    reg_{i} -> mem_0 [label=\"store\", color=red];")
                if scratchpad_count > 0:
                    memory_connections.append(f"    reg_{i} -> spad_0 [label=\"store\", color=red];")
        
        # 5. Add forwarding paths for better datapath visualization
        # Add forwarding paths from each computational unit to MUXes
        
        # ALUs to MUXes (forwarding)
        if alu_count > 10:
            # Connect to a subset of MUXes (up to 4 or mux_count, whichever is smaller)
            if use_mux_block:
                connections.append(f"    alu_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 4)):
                    connections.append(f"    alu_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif alu_count > 0:
            # Connect individual ALUs to a subset of MUXes
            alu_connects = min(alu_count, 4)  # Connect up to 4 ALUs
            if use_mux_block:
                for i in range(alu_connects):
                    connections.append(f"    alu_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 4)  # Connect to up to 4 MUXes
                for i in range(alu_connects):
                    for j in range(mux_connects):
                        connections.append(f"    alu_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        
        # Adders to MUXes (forwarding)
        if adder_count > 10:
            # Connect to a subset of MUXes
            if use_mux_block:
                connections.append(f"    adder_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 3)):
                    connections.append(f"    adder_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif adder_count > 0:
            # Connect individual adders to a subset of MUXes
            adder_connects = min(adder_count, 2)  # Connect up to 2 adders
            if use_mux_block:
                for i in range(adder_connects):
                    connections.append(f"    adder_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 3)      # Connect to up to 3 MUXes
                for i in range(adder_connects):
                    for j in range(mux_connects):
                        connections.append(f"    adder_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        
        # BitOps to MUXes (forwarding)
        if bitop_count > 10:
            # Connect to a subset of MUXes
            if use_mux_block:
                connections.append(f"    bitop_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 3)):
                    connections.append(f"    bitop_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif bitop_count > 0:
            # Connect individual BitOps to a subset of MUXes
            bitop_connects = min(bitop_count, 2)  # Connect up to 2 BitOps
            if use_mux_block:
                for i in range(bitop_connects):
                    connections.append(f"    bitop_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 3)      # Connect to up to 3 MUXes
                for i in range(bitop_connects):
                    for j in range(mux_connects):
                        connections.append(f"    bitop_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")

        # Multipliers to MUXes (forwarding)  
        if mul_count > 10:
            # Connect to a subset of MUXes
            if use_mux_block:
                connections.append(f"    mul_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 4)):
                    connections.append(f"    mul_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif mul_count > 0:
            # Connect individual multipliers to a subset of MUXes
            mul_connects = min(mul_count, 3)     # Connect up to 3 multipliers
            if use_mux_block:
                for i in range(mul_connects):
                    connections.append(f"    mul_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 4)     # Connect to up to 4 MUXes
                for i in range(mul_connects):
                    for j in range(mux_connects):
                        connections.append(f"    mul_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
                    
        # 6. Add clock and reset connections to all computational units
        clock_connections = []
        reset_connections = []
        
        # ALUs
        if alu_count > 10:
            clock_connections.append(f"    clock -> alu_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> alu_block [style=dashed, color=red];")
        else:
            for i in range(alu_count):
                clock_connections.append(f"    clock -> alu_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> alu_{i} [style=dashed, color=red];")
        
        # Adders
        if adder_count > 10:
            clock_connections.append(f"    clock -> adder_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> adder_block [style=dashed, color=red];")
        elif adder_count > 0:
            for i in range(adder_count):
                clock_connections.append(f"    clock -> adder_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> adder_{i} [style=dashed, color=red];")
        
        # Subtractors
        if subtractor_count > 10:
            clock_connections.append(f"    clock -> subtractor_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> subtractor_block [style=dashed, color=red];")
        elif subtractor_count > 0:
            for i in range(subtractor_count):
                clock_connections.append(f"    clock -> subtractor_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> subtractor_{i} [style=dashed, color=red];")
        
        # BitOps
        if bitop_count > 10:
            clock_connections.append(f"    clock -> bitop_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> bitop_block [style=dashed, color=red];")
        elif bitop_count > 0:
            for i in range(bitop_count):
                clock_connections.append(f"    clock -> bitop_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> bitop_{i} [style=dashed, color=red];")
        
        # Comparators
        if comparator_count > 10:
            clock_connections.append(f"    clock -> comparator_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> comparator_block [style=dashed, color=red];")
        elif comparator_count > 0:
            for i in range(comparator_count):
                clock_connections.append(f"    clock -> comparator_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> comparator_{i} [style=dashed, color=red];")
        
        # RelationalOps
        if relop_count > 10:
            clock_connections.append(f"    clock -> relationalop_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> relationalop_block [style=dashed, color=red];")
        elif relop_count > 0:
            for i in range(relop_count):
                clock_connections.append(f"    clock -> relationalop_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> relationalop_{i} [style=dashed, color=red];")
        
        # Shifters
        if shifter_count > 10:
            clock_connections.append(f"    clock -> shifter_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> shifter_block [style=dashed, color=red];")
        elif shifter_count > 0:
            for i in range(shifter_count):
                clock_connections.append(f"    clock -> shifter_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> shifter_{i} [style=dashed, color=red];")
        
        # Multipliers
        if mul_count > 10:
            clock_connections.append(f"    clock -> mul_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> mul_block [style=dashed, color=red];")
        elif mul_count > 0:
            for i in range(mul_count):
                clock_connections.append(f"    clock -> mul_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> mul_{i} [style=dashed, color=red];")
        
        # Dividers
        if div_count > 10:
            clock_connections.append(f"    clock -> div_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> div_block [style=dashed, color=red];")
        elif div_count > 0:
            for i in range(div_count):
                clock_connections.append(f"    clock -> div_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> div_{i} [style=dashed, color=red];")
        
        # Registers
        if reg_count > 10:
            clock_connections.append(f"    clock -> reg_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> reg_block [style=dashed, color=red];")
        else:
            for i in range(reg_count):
                clock_connections.append(f"    clock -> reg_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> reg_{i} [style=dashed, color=red];")
        
        # Memory
        for i in range(mem_count):
            clock_connections.append(f"    clock -> mem_{i} [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> mem_{i} [style=dashed, color=red];")
        
        # Scratchpad
        for i in range(scratchpad_count):
            clock_connections.append(f"    clock -> spad_{i} [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> spad_{i} [style=dashed, color=red];")
        
        # Add all connections to the DOT content
        dot_content.append("    // Data Connections")
        for connection in connections:
            dot_content.append(connection)
        
        dot_content.append("    // Memory Connections")
        for connection in memory_connections:
            dot_content.append(connection)
        
        dot_content.append("    // Control Connections")
        for connection in control_connections:
            dot_content.append(connection)
        
        dot_content.append("    // Clock Connections")
        for connection in clock_connections:
            dot_content.append(connection)
        
        dot_content.append("    // Reset Connections")
        for connection in reset_connections:
            dot_content.append(connection)
        
        # Add streaming connections for FIFOs and Crossbars
        if fifo_count > 0 or crossbar_count > 0:
            dot_content.append("    // Streaming Component Connections")
            
            # Connect FIFOs to computational units
            if fifo_count > 0:
                # Add clock and control for FIFOs
                for i in range(fifo_count):
                    fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                    # Add control connection
                    control_connections.append(f"    FSM -> fifo_{fifo_id} [label=\"control\", style=dashed, color=orange];")
                    # Add clock and reset
                    clock_connections.append(f"    clock -> fifo_{fifo_id} [style=dashed, color=blue];")
                    reset_connections.append(f"    reset -> fifo_{fifo_id} [style=dashed, color=red];")
                
                # Connect registers to FIFOs (for writing)
                if reg_count > 10:
                    # Connect consolidated register block to FIFOs
                    if fifo_count > 10:
                        # Use fifo_block for many FIFOs
                        dot_content.append(f"    reg_block -> fifo_block [color=blue, label=\"write\"];")
                    else:
                        # Connect to individual FIFOs
                        for i in range(min(fifo_count, 4)):
                            fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                            dot_content.append(f"    reg_block -> fifo_{fifo_id} [color=blue, label=\"write\"];")
                else:
                    # Connect individual registers to FIFOs
                    if fifo_count > 10:
                        # Use fifo_block for many FIFOs
                        for i in range(min(reg_count, 4)):
                            dot_content.append(f"    reg_{i} -> fifo_block [color=blue, label=\"write\"];")
                    else:
                        # Connect to individual FIFOs
                        for i in range(min(reg_count, 4)):
                            for j in range(min(fifo_count, 2)):
                                fifo_id = hw_allocated['FIFO'][j].id if hasattr(hw_allocated['FIFO'][j], 'id') else j
                                dot_content.append(f"    reg_{i} -> fifo_{fifo_id} [color=blue, label=\"write\"];")
                
                # Connect FIFOs to computational units (for reading)
                if fifo_count > 10:
                    # Use fifo_block for many FIFOs
                    
                    # Connect FIFO block to ALUs
                    if alu_count > 10:
                        dot_content.append(f"    fifo_block -> alu_block [color=green, label=\"read\"];")
                    else:
                        for j in range(min(alu_count, 2)):
                            dot_content.append(f"    fifo_block -> alu_{j} [color=green, label=\"read\"];")
                    
                    # Connect FIFO block to multipliers
                    if mul_count > 10:
                        dot_content.append(f"    fifo_block -> mul_block [color=green, label=\"read\"];")
                    elif mul_count > 0:
                        for j in range(min(mul_count, 2)):
                            dot_content.append(f"    fifo_block -> mul_{j} [color=green, label=\"read\"];")
                else:
                    # Connect individual FIFOs
                    for i in range(min(fifo_count, 4)):
                        fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                        
                        # Connect FIFOs to ALUs
                        if alu_count > 10:
                            dot_content.append(f"    fifo_{fifo_id} -> alu_block [color=green, label=\"read\"];")
                        else:
                            for j in range(min(alu_count, 2)):
                                dot_content.append(f"    fifo_{fifo_id} -> alu_{j} [color=green, label=\"read\"];")
                        
                        # Connect FIFOs to multipliers
                        if mul_count > 10:
                            dot_content.append(f"    fifo_{fifo_id} -> mul_block [color=green, label=\"read\"];")
                        elif mul_count > 0:
                            for j in range(min(mul_count, 2)):
                                dot_content.append(f"    fifo_{fifo_id} -> mul_{j} [color=green, label=\"read\"];")
                
                # Connect FIFOs to each other for dataflow pipelines
                if fifo_count > 10:
                    # With many FIFOs, just show a self-loop to indicate internal dataflow
                    dot_content.append(f"    fifo_block -> fifo_block [color=purple, label=\"internal stream\"];")
                elif fifo_count > 1:
                    # With few FIFOs, show the connections between them
                    for i in range(fifo_count - 1):
                        fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                        next_fifo_id = hw_allocated['FIFO'][i+1].id if hasattr(hw_allocated['FIFO'][i+1], 'id') else i+1
                        dot_content.append(f"    fifo_{fifo_id} -> fifo_{next_fifo_id} [color=purple, label=\"stream\"];")
            
            # Connect Crossbars
            if crossbar_count > 0:
                # Add control, clock and reset for Crossbars
                for i in range(crossbar_count):
                    # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                    if 'CROSSBAR' in hw_allocated and i < len(hw_allocated['CROSSBAR']):
                        xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                    elif 'Crossbar' in hw_allocated and i < len(hw_allocated['Crossbar']):
                        xbar_id = hw_allocated['Crossbar'][i].id if hasattr(hw_allocated['Crossbar'][i], 'id') else i
                    else:
                        xbar_id = i
                    
                    # Add control connection
                    control_connections.append(f"    FSM -> {'crossbar_block' if crossbar_count > 10 else f'xbar_{xbar_id}'} [label=\"control\", style=dashed, color=orange];")
                    # Add clock and reset
                    clock_connections.append(f"    clock -> {'crossbar_block' if crossbar_count > 10 else f'xbar_{xbar_id}'} [style=dashed, color=blue];")
                    reset_connections.append(f"    reset -> {'crossbar_block' if crossbar_count > 10 else f'xbar_{xbar_id}'} [style=dashed, color=red];")
                
                # Connect FIFOs to Crossbars (if both exist)
                if fifo_count > 0:
                    if fifo_count > 10 and crossbar_count > 10:
                        # Block-to-block connection
                        dot_content.append(f"    fifo_block -> crossbar_block [color=purple, label=\"route\"];")
                    elif fifo_count > 10:
                        # FIFO block to individual crossbars
                        for j in range(min(crossbar_count, 2)):
                            # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                            if 'CROSSBAR' in hw_allocated and j < len(hw_allocated['CROSSBAR']):
                                xbar_id = hw_allocated['CROSSBAR'][j].id if hasattr(hw_allocated['CROSSBAR'][j], 'id') else j
                            elif 'Crossbar' in hw_allocated and j < len(hw_allocated['Crossbar']):
                                xbar_id = hw_allocated['Crossbar'][j].id if hasattr(hw_allocated['Crossbar'][j], 'id') else j
                            else:
                                xbar_id = j
                            dot_content.append(f"    fifo_block -> xbar_{xbar_id} [color=purple, label=\"route\"];")
                    elif crossbar_count > 10:
                        # Individual FIFOs to crossbar block
                        for i in range(min(fifo_count, 4)):
                            fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                            dot_content.append(f"    fifo_{fifo_id} -> crossbar_block [color=purple, label=\"route\"];")
                    else:
                        # Individual FIFOs to individual crossbars
                        for i in range(min(fifo_count, 4)):
                            fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                            for j in range(min(crossbar_count, 2)):
                                # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                                if 'CROSSBAR' in hw_allocated and j < len(hw_allocated['CROSSBAR']):
                                    xbar_id = hw_allocated['CROSSBAR'][j].id if hasattr(hw_allocated['CROSSBAR'][j], 'id') else j
                                elif 'Crossbar' in hw_allocated and j < len(hw_allocated['Crossbar']):
                                    xbar_id = hw_allocated['Crossbar'][j].id if hasattr(hw_allocated['Crossbar'][j], 'id') else j
                                else:
                                    xbar_id = j
                                dot_content.append(f"    fifo_{fifo_id} -> xbar_{xbar_id} [color=purple, label=\"route\"];")
                
                # Connect Crossbars to computational units
                if crossbar_count > 10:
                    # Connect crossbar block to ALUs
                    if alu_count > 10:
                        dot_content.append(f"    crossbar_block -> alu_block [color=green, label=\"data\"];")
                    else:
                        for j in range(min(alu_count, 3)):
                            dot_content.append(f"    crossbar_block -> alu_{j} [color=green, label=\"data\"];")
                    
                    # Connect crossbar block to multipliers
                    if mul_count > 10:
                        dot_content.append(f"    crossbar_block -> mul_block [color=green, label=\"data\"];")
                    elif mul_count > 0:
                        for j in range(min(mul_count, 3)):
                            dot_content.append(f"    crossbar_block -> mul_{j} [color=green, label=\"data\"];")
                else:
                    # Connect individual crossbars
                    for i in range(min(crossbar_count, 2)):
                        # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                        if 'CROSSBAR' in hw_allocated and i < len(hw_allocated['CROSSBAR']):
                            xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                        elif 'Crossbar' in hw_allocated and i < len(hw_allocated['Crossbar']):
                            xbar_id = hw_allocated['Crossbar'][i].id if hasattr(hw_allocated['Crossbar'][i], 'id') else i
                        else:
                            xbar_id = i
                        
                        # To ALUs
                        if alu_count > 10:
                            dot_content.append(f"    xbar_{xbar_id} -> alu_block [color=green, label=\"data\"];")
                        else:
                            for j in range(min(alu_count, 3)):
                                dot_content.append(f"    xbar_{xbar_id} -> alu_{j} [color=green, label=\"data\"];")
                    
                        # To multipliers
                        if mul_count > 10:
                            dot_content.append(f"    xbar_{xbar_id} -> mul_block [color=green, label=\"data\"];")
                        elif mul_count > 0:
                            for j in range(min(mul_count, 3)):
                                dot_content.append(f"    xbar_{xbar_id} -> mul_{j} [color=green, label=\"data\"];")
                
                # Connect Crossbars to registers
                if crossbar_count > 10:
                    # Connect crossbar block to registers
                    if reg_count > 10:
                        dot_content.append(f"    crossbar_block -> reg_block [color=blue, label=\"result\"];")
                    else:
                        for j in range(min(reg_count, 4)):
                            dot_content.append(f"    crossbar_block -> reg_{j} [color=blue, label=\"result\"];")
                else:
                    # Connect individual crossbars to registers
                    if reg_count > 10:
                        for i in range(min(crossbar_count, 2)):
                            xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                            dot_content.append(f"    xbar_{xbar_id} -> reg_block [color=blue, label=\"result\"];")
                    else:
                        for i in range(min(crossbar_count, 2)):
                            xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                            for j in range(min(reg_count, 4)):
                                dot_content.append(f"    xbar_{xbar_id} -> reg_{j} [color=blue, label=\"result\"];")
                
                # Connect Crossbars to each other for multi-stage routing
                if crossbar_count > 10:
                    # With many crossbars, just show a self-loop to indicate internal routing
                    dot_content.append(f"    crossbar_block -> crossbar_block [color=purple, label=\"internal routing\"];")
                elif crossbar_count > 1:
                    # With few crossbars, show the connections between them
                    for i in range(crossbar_count - 1):
                        xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                        next_xbar_id = hw_allocated['CROSSBAR'][i+1].id if hasattr(hw_allocated['CROSSBAR'][i+1], 'id') else i+1
                        dot_content.append(f"    xbar_{xbar_id} -> xbar_{next_xbar_id} [color=purple, label=\"route\"];")
        
    # Close the graph
    dot_content.append("}")
    
    # Write the DOT content to the file
    with open(filename, "w") as f:
        f.write("\n".join(dot_content))
    
    return "\n".join(dot_content)

def generate_netlist_microarch_visualization(netlist_resources, operations=None, netlist=None):
    """
    Generate a microarchitecture visualization for a netlist.
    
    Args:
        netlist_resources: List of NetlistResource objects
        operations: List of operations (optional)
        netlist: The complete netlist object (optional)
        
    Returns:
        DOT format string representation of the netlist microarchitecture
    """
    # Group resources by type
    hw_allocated = {}
    print(netlist_resources)
    for resource in netlist_resources:
        resource_type = resource.type.split('_')[0]  # Get base resource type (ALU, Register, etc.)
        if resource_type not in hw_allocated:
            hw_allocated[resource_type] = []
        hw_allocated[resource_type].append(resource)
    print(hw_allocated)
    # Ensure we have all necessary resource types for visualization
    for resource_type in ['ALU', 'Multiplier', 'Register', 'Memory', 'MUX']:
        if resource_type not in hw_allocated:
            hw_allocated[resource_type] = []
    
    # Initialize resource counter variables
    scratchpad_count = 0
    
    # Initialize specialized resource counts
    adder_count = 0
    subtractor_count = 0
    bitop_count = 0
    comparator_count = 0
    relop_count = 0
    shifter_count = 0
    
    # Count specialized resources
    if 'ALU' in hw_allocated:
        alu_count = len(hw_allocated['ALU'])
    if 'Adder' in hw_allocated:
        adder_count = len(hw_allocated['Adder'])
    if 'Subtractor' in hw_allocated:
        subtractor_count = len(hw_allocated['Subtractor'])
    if 'BitOp' in hw_allocated:
        bitop_count = len(hw_allocated['BitOp'])
    if 'Comparator' in hw_allocated:
        comparator_count = len(hw_allocated['Comparator'])
    if 'RelationalOp' in hw_allocated:
        relop_count = len(hw_allocated['RelationalOp'])
    if 'Shifter' in hw_allocated:
        shifter_count = len(hw_allocated['Shifter'])
    print(alu_count, adder_count, subtractor_count, bitop_count, comparator_count, relop_count, shifter_count)
    # Initialize DOT content
    dot_content = [
        "digraph G {",
        "    compound=true;",
        "    fontname=\"Helvetica\";",
        "    fontsize=10;",
        "    rankdir=TB;",
        "    ranksep=0.5;",
        "    nodesep=0.5;",
        "    node [fontname=\"Helvetica\", fontsize=10, style=filled];",
        "    edge [fontname=\"Helvetica\", fontsize=8];"
    ]
    
    # Create subgraph for control units
    dot_content.extend([
        "    // Control Units",
        "    subgraph cluster_control {",
        "        label=\"Control Units\";",
        "        style=filled;",
        "        color=lightgrey;",
        "        FSM [label=\"FSM\", shape=box, fillcolor=gold];",
        "        clock [label=\"Clock\", shape=circle, fillcolor=lightskyblue];",
        "        reset [label=\"Reset\", shape=circle, fillcolor=lightcoral];",
        "    }"
    ])
    
    # Create subgraph for computational units (ALUs, MULs, DIVs)
    dot_content.extend([
        "    // Computational Units",
        "    subgraph cluster_compute {",
        "        label=\"Computational Units\";",
        "        style=filled;",
        "        color=lightblue;"
    ])
    
    # Add ALU units
    alu_count = 0
    if 'ALU' in hw_allocated and hw_allocated['ALU']:
        alu_count = len(hw_allocated['ALU'])
        if alu_count > 10:
            # Show a single large block for many ALUs
            dot_content.append(f"        alu_block [label=\"{alu_count}\\nALUs\", shape=box, width=2, height=1.5, fillcolor=lightyellow];")
        else:
            # Show individual ALUs
            for i, resource in enumerate(hw_allocated['ALU']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        alu_{resource_id} [label=\"ALU\\n{resource_id}\", shape=box, fillcolor=lightyellow];")
    
    # Ensure we have at least one ALU for visualization
    if alu_count == 0:
        dot_content.append("        alu_0 [label=\"ALU\\n0\", shape=box, fillcolor=lightyellow];")
        alu_count = 1
        if 'ALU' not in hw_allocated:
            hw_allocated['ALU'] = []
    
    # Add Adder units
    adder_count = 0
    if 'Adder' in hw_allocated and hw_allocated['Adder']:
        adder_count = len(hw_allocated['Adder'])
        if adder_count > 10:
            # Show a single large block for many Adders
            dot_content.append(f"        adder_block [label=\"{adder_count}\\nAdders\", shape=box, width=2, height=1.5, fillcolor=lightcyan];")
        else:
            # Show individual Adders
            for i, resource in enumerate(hw_allocated['Adder']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        adder_{resource_id} [label=\"ADD\\n{resource_id}\", shape=box, fillcolor=lightcyan];")
                
    # Add Subtractor units
    subtractor_count = 0
    if 'Subtractor' in hw_allocated and hw_allocated['Subtractor']:
        subtractor_count = len(hw_allocated['Subtractor'])
        if subtractor_count > 10:
            # Show a single large block for many Subtractors
            dot_content.append(f"        subtractor_block [label=\"{subtractor_count}\\nSubtractors\", shape=box, width=2, height=1.5, fillcolor=lavender];")
        else:
            # Show individual Subtractors
            for i, resource in enumerate(hw_allocated['Subtractor']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        subtractor_{resource_id} [label=\"SUB\\n{resource_id}\", shape=box, fillcolor=lavender];")
                
    # Add BitOp units
    bitop_count = 0
    if 'BitOp' in hw_allocated and hw_allocated['BitOp']:
        bitop_count = len(hw_allocated['BitOp'])
        if bitop_count > 10:
            # Show a single large block for many BitOps
            dot_content.append(f"        bitop_block [label=\"{bitop_count}\\nBitOps\", shape=box, width=2, height=1.5, fillcolor=honeydew];")
        else:
            # Show individual BitOps
            for i, resource in enumerate(hw_allocated['BitOp']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        bitop_{resource_id} [label=\"BIT\\n{resource_id}\", shape=box, fillcolor=honeydew];")
                
    # Add Comparator units
    comparator_count = 0
    if 'Comparator' in hw_allocated and hw_allocated['Comparator']:
        comparator_count = len(hw_allocated['Comparator'])
        if comparator_count > 10:
            # Show a single large block for many Comparators
            dot_content.append(f"        comparator_block [label=\"{comparator_count}\\nComparators\", shape=box, width=2, height=1.5, fillcolor=azure];")
        else:
            # Show individual Comparators
            for i, resource in enumerate(hw_allocated['Comparator']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        comparator_{resource_id} [label=\"CMP\\n{resource_id}\", shape=box, fillcolor=azure];")
                
    # Add RelationalOp units
    relop_count = 0
    if 'RelationalOp' in hw_allocated and hw_allocated['RelationalOp']:
        relop_count = len(hw_allocated['RelationalOp'])
        if relop_count > 10:
            # Show a single large block for many RelationalOps
            dot_content.append(f"        relationalop_block [label=\"{relop_count}\\nRelOps\", shape=box, width=2, height=1.5, fillcolor=aliceblue];")
        else:
            # Show individual RelationalOps
            for i, resource in enumerate(hw_allocated['RelationalOp']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        relationalop_{resource_id} [label=\"REL\\n{resource_id}\", shape=box, fillcolor=aliceblue];")
                
    # Add Shifter units
    shifter_count = 0
    if 'Shifter' in hw_allocated and hw_allocated['Shifter']:
        shifter_count = len(hw_allocated['Shifter'])
        if shifter_count > 10:
            # Show a single large block for many Shifters
            dot_content.append(f"        shifter_block [label=\"{shifter_count}\\nShifters\", shape=box, width=2, height=1.5, fillcolor=ghostwhite];")
        else:
            # Show individual Shifters
            for i, resource in enumerate(hw_allocated['Shifter']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        shifter_{resource_id} [label=\"SHF\\n{resource_id}\", shape=box, fillcolor=ghostwhite];")
    
    # Add MUL units
    mul_count = 0
    if 'Multiplier' in hw_allocated and hw_allocated['Multiplier']:
        mul_count = len(hw_allocated['Multiplier'])
        if mul_count > 10:
            # Show a single large block for many multipliers
            dot_content.append(f"        mul_block [label=\"{mul_count}\\nMultipliers\", shape=box, width=2, height=1.5, fillcolor=lightpink];")
        else:
            # Show individual multipliers
            for i, resource in enumerate(hw_allocated['Multiplier']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        mul_{resource_id} [label=\"MUL\\n{resource_id}\", shape=box, fillcolor=lightpink];")
    
    # Ensure we have at least one multiplier for SPMM operations
    if mul_count == 0 and operations and any(op.startswith('MUL') for op in operations):
        dot_content.append("        mul_0 [label=\"MUL\\n0\", shape=box, fillcolor=lightpink];")
        mul_count = 1
        if 'Multiplier' not in hw_allocated:
            hw_allocated['Multiplier'] = []
    
    # Add DIV units
    div_count = 0
    if 'Divider' in hw_allocated and hw_allocated['Divider']:
        div_count = len(hw_allocated['Divider'])
        if div_count > 10:
            # Show a single large block for many Dividers
            dot_content.append(f"        div_block [label=\"{div_count}\\nDividers\", shape=box, width=2, height=1.5, fillcolor=lightgreen];")
        else:
            # Show individual Dividers
            for resource in hw_allocated['Divider']:
                resource_id = resource.id if hasattr(resource, 'id') else div_count
                dot_content.append(f"        div_{resource_id} [label=\"DIV\\n{resource_id}\", shape=box, fillcolor=lightgreen];")
                div_count += 1
    
    dot_content.append("    }")  # Close computational units subgraph
    
    # Create subgraph for registers
    dot_content.extend([
        "    // Registers",
        "    subgraph cluster_registers {",
        "        label=\"Registers\";",
        "        style=filled;",
        "        color=lightgreen;"
    ])
    
    # Add register units
    reg_count = 0
    if 'Register' in hw_allocated and hw_allocated['Register']:
        reg_count = len(hw_allocated['Register'])
        if reg_count > 10:
            # Show a single large block for many registers
            dot_content.append(f"        reg_block [label=\"{reg_count}\\nRegisters\", shape=box, width=2, height=1.5, fillcolor=lightgreen];")
        else:
            # Show individual registers
            for i, resource in enumerate(hw_allocated['Register']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        reg_{resource_id} [label=\"REG\\n{resource_id}\", shape=box, fillcolor=lightgreen];")
    
    # Ensure we have at least two registers for visualization
    if reg_count < 2:
        for i in range(reg_count, 2):
            dot_content.append(f"        reg_{i} [label=\"REG\\n{i}\", shape=box, fillcolor=lightgreen];")
        reg_count = 2
    
    dot_content.append("    }")
    
    # Create subgraph for memory units
    dot_content.extend([
        "    // Memory Units",
        "    subgraph cluster_memory {",
        "        label=\"Memory Units\";",
        "        style=filled;",
        "        color=lightcoral;"
    ])
    
    # Add memory units
    mem_count = 0
    if 'Memory' in hw_allocated and hw_allocated['Memory']:
        for resource in hw_allocated['Memory']:
            resource_id = resource.id if hasattr(resource, 'id') else mem_count
            size_label = f"{resource.memory_size//1024}KB" if hasattr(resource, 'memory_size') else "MEM"
            dot_content.append(f"        mem_{resource_id} [label=\"{size_label}\\n{resource_id}\", shape=cylinder, fillcolor=white];")
            mem_count += 1
    
    # Add Scratchpad memory units if present
    scratchpad_count = 0
    if 'Scratchpad' in hw_allocated and hw_allocated['Scratchpad']:
        for resource in hw_allocated['Scratchpad']:
            resource_id = resource.id if hasattr(resource, 'id') else scratchpad_count
            size_label = f"{resource.memory_size//1024}KB" if hasattr(resource, 'memory_size') else "SPAD"
            dot_content.append(f"        spad_{resource_id} [label=\"{size_label}\\n{resource_id}\", shape=cylinder, fillcolor=wheat];")
            scratchpad_count += 1
    
    # Ensure we have at least one memory unit for visualization
    if mem_count == 0 and scratchpad_count == 0:
        dot_content.append("        mem_0 [label=\"MEM\\n0\", shape=cylinder, fillcolor=white];")
        mem_count = 1
    
    dot_content.append("    }")  # Close memory units subgraph
    
    # Create subgraph for multiplexers
    dot_content.extend([
        "    // Multiplexers",
        "    subgraph cluster_mux {",
        "        label=\"Multiplexers\";",
        "        style=filled;",
        "        color=lightyellow;"
    ])
    
    # Add multiplexer units
    mux_count = 0
    use_mux_block = False
    if 'MUX' in hw_allocated and hw_allocated['MUX']:
        mux_count = len(hw_allocated['MUX'])
        # If we have more than 4 MUXes, use a single block representation
        if mux_count > 4:
            use_mux_block = True
            dot_content.append(f"        mux_block [label=\"{mux_count}\\nMUXes\", shape=box, width=2, height=1.5, fillcolor=wheat];")
        else:
            # Show individual MUXes when count is small
            for resource in hw_allocated['MUX']:
                resource_id = resource.id if hasattr(resource, 'id') else mux_count
                dot_content.append(f"        mux_{resource_id} [label=\"MUX\\n{resource_id}\", shape=trapezium, fillcolor=wheat];")
                mux_count += 1
    else:
        # Use a single MUX as fallback if none are allocated
        dot_content.append(f"        mux_0 [label=\"MUX\\n0\", shape=trapezium, fillcolor=wheat];")
        mux_count = 1
    
    dot_content.append("    }")  # Close multiplexers subgraph
    
    # Create subgraph for FIFOs
    dot_content.extend([
        "    // FIFOs",
        "    subgraph cluster_fifos {",
        "        label=\"FIFOs\";",
        "        style=filled;",
        "        color=lightcyan;"
    ])
    
    # Add FIFO units
    fifo_count = 0
    if 'FIFO' in hw_allocated and hw_allocated['FIFO']:
        fifo_count = len(hw_allocated['FIFO'])
        if fifo_count > 10:
            # Show a single large block for many FIFOs
            dot_content.append(f"        fifo_block [label=\"{fifo_count}\\nFIFOs\", shape=box, width=2, height=1.5, fillcolor=lightcyan];")
        else:
            # Show individual FIFOs
            for i, resource in enumerate(hw_allocated['FIFO']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        fifo_{resource_id} [label=\"FIFO\\n{resource_id}\", shape=box, fillcolor=lightcyan];")
    
    dot_content.append("    }")  # Close FIFOs subgraph
    
    # Create subgraph for Crossbars
    dot_content.extend([
        "    // Crossbars",
        "    subgraph cluster_crossbars {",
        "        label=\"Crossbars\";",
        "        style=filled;",
        "        color=lightpink;"
    ])
    
    # Add Crossbar units
    crossbar_count = 0
    if 'CROSSBAR' in hw_allocated and hw_allocated['CROSSBAR']:
        crossbar_count = len(hw_allocated['CROSSBAR'])
        if crossbar_count > 10:
            # Show a single large block for many Crossbars
            dot_content.append(f"        crossbar_block [label=\"{crossbar_count}\\nCrossbars\", shape=box, width=2, height=1.5, fillcolor=lightpink];")
        else:
            # Show individual Crossbars
            for i, resource in enumerate(hw_allocated['CROSSBAR']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        crossbar_{resource_id} [label=\"CROSSBAR\\n{resource_id}\", shape=box, fillcolor=lightpink];")
    # Also check for 'Crossbar' (with capital C) for backward compatibility
    elif 'Crossbar' in hw_allocated and hw_allocated['Crossbar']:
        crossbar_count = len(hw_allocated['Crossbar'])
        if crossbar_count > 10:
            # Show a single large block for many Crossbars
            dot_content.append(f"        crossbar_block [label=\"{crossbar_count}\\nCrossbars\", shape=box, width=2, height=1.5, fillcolor=lightpink];")
        else:
            # Show individual Crossbars
            for i, resource in enumerate(hw_allocated['Crossbar']):
                resource_id = resource.id if hasattr(resource, 'id') else i
                dot_content.append(f"        crossbar_{resource_id} [label=\"CROSSBAR\\n{resource_id}\", shape=box, fillcolor=lightpink];")
    
    dot_content.append("    }")  # Close Crossbars subgraph
    
    # Extract connections from netlist or create comprehensive default connections
    connections = []
    memory_connections = []
    control_connections = []
    
    # Use the real netlist if available to get better connection information
    if False:
        # Use extract_netlist_connections to get the connections
        connections, memory_connections, control_connections = extract_netlist_connections(netlist)
    else:
        # Create comprehensive connections for a processor-like datapath
        # 1. Connect all registers to all multiplexers (full connectivity)
        if reg_count > 10:
            # Connect the consolidated register block to multiplexers
            if use_mux_block:
                connections.append(f"    reg_block -> mux_block [color=black];")
            else:
                for j in range(mux_count):
                    connections.append(f"    reg_block -> mux_{j} [color=black];")
        else:
            # Connect individual registers to multiplexers
            if use_mux_block:
                for i in range(reg_count):
                    connections.append(f"    reg_{i} -> mux_block [color=black];")
            else:
                for i in range(reg_count):
                    for j in range(mux_count):
                        connections.append(f"    reg_{i} -> mux_{j} [color=black];")
        
        # Add FSM control connections to all components
        # FSM control connections to computational units
        if alu_count > 10:
            control_connections.append(f"    FSM -> alu_block [label=\"control\", style=dashed, color=orange];")
        else:
            for i in range(alu_count):
                control_connections.append(f"    FSM -> alu_{i} [label=\"control\", style=dashed, color=orange];")
                
        if adder_count > 10:
            control_connections.append(f"    FSM -> adder_block [label=\"control\", style=dashed, color=orange];")
        elif adder_count > 0:
            for i in range(adder_count):
                control_connections.append(f"    FSM -> adder_{i} [label=\"control\", style=dashed, color=orange];")

        if subtractor_count > 10:
            control_connections.append(f"    FSM -> subtractor_block [label=\"control\", style=dashed, color=orange];")
        elif subtractor_count > 0:
            for i in range(subtractor_count):
                control_connections.append(f"    FSM -> subtractor_{i} [label=\"control\", style=dashed, color=orange];")

        if bitop_count > 10:
            control_connections.append(f"    FSM -> bitop_block [label=\"control\", style=dashed, color=orange];")
        elif bitop_count > 0:
            for i in range(bitop_count):
                control_connections.append(f"    FSM -> bitop_{i} [label=\"control\", style=dashed, color=orange];")

        if comparator_count > 10:
            control_connections.append(f"    FSM -> comparator_block [label=\"control\", style=dashed, color=orange];")
        elif comparator_count > 0:
            for i in range(comparator_count):
                control_connections.append(f"    FSM -> comparator_{i} [label=\"control\", style=dashed, color=orange];")

        if relop_count > 10:
            control_connections.append(f"    FSM -> relationalop_block [label=\"control\", style=dashed, color=orange];")
        elif relop_count > 0:
            for i in range(relop_count):
                control_connections.append(f"    FSM -> relationalop_{i} [label=\"control\", style=dashed, color=orange];")

        if shifter_count > 10:
            control_connections.append(f"    FSM -> shifter_block [label=\"control\", style=dashed, color=orange];")
        elif shifter_count > 0:
            for i in range(shifter_count):
                control_connections.append(f"    FSM -> shifter_{i} [label=\"control\", style=dashed, color=orange];")

        if mul_count > 10:
            control_connections.append(f"    FSM -> mul_block [label=\"control\", style=dashed, color=orange];")
        elif mul_count > 0:
            for i in range(mul_count):
                control_connections.append(f"    FSM -> mul_{i} [label=\"control\", style=dashed, color=orange];")

        if div_count > 10:
            control_connections.append(f"    FSM -> div_block [label=\"control\", style=dashed, color=orange];")
        elif div_count > 0:
            for i in range(div_count):
                control_connections.append(f"    FSM -> div_{i} [label=\"control\", style=dashed, color=orange];")

        # FSM control connections to memory and registers
        if reg_count > 10:
            control_connections.append(f"    FSM -> reg_block [label=\"control\", style=dashed, color=orange];")
        else:
            for i in range(reg_count):
                control_connections.append(f"    FSM -> reg_{i} [label=\"control\", style=dashed, color=orange];")

        for i in range(mem_count):
            control_connections.append(f"    FSM -> mem_{i} [label=\"control\", style=dashed, color=orange];")

        for i in range(scratchpad_count):
            control_connections.append(f"    FSM -> spad_{i} [label=\"control\", style=dashed, color=orange];")

        # FSM control connections to multiplexers
        if use_mux_block:
            control_connections.append(f"    FSM -> mux_block [label=\"control\", style=dashed, color=orange];")
        else:
            for i in range(mux_count):
                control_connections.append(f"    FSM -> mux_{i} [label=\"control\", style=dashed, color=orange];")

        # 2. Connect multiplexers to computational units (execution paths)
        if use_mux_block:
            # Connect consolidated MUX block to computational units
            if alu_count > 10:
                connections.append(f"    mux_block -> alu_block [color=black];")
            else:
                for j in range(alu_count):
                    connections.append(f"    mux_block -> alu_{j} [color=black];")
            
            # Connect to adders
            if adder_count > 10:
                connections.append(f"    mux_block -> adder_block [color=black];")
            elif adder_count > 0:
                for j in range(adder_count):
                    connections.append(f"    mux_block -> adder_{j} [color=black];")
            
            # Connect to subtractors
            if subtractor_count > 10:
                connections.append(f"    mux_block -> subtractor_block [color=black];")
            elif subtractor_count > 0:
                for j in range(subtractor_count):
                    connections.append(f"    mux_block -> subtractor_{j} [color=black];")
            
            # Connect to bit operations
            if bitop_count > 10:
                connections.append(f"    mux_block -> bitop_block [color=black];")
            elif bitop_count > 0:
                for j in range(bitop_count):
                    connections.append(f"    mux_block -> bitop_{j} [color=black];")
            
            # Connect to comparators
            if comparator_count > 10:
                connections.append(f"    mux_block -> comparator_block [color=black];")
            elif comparator_count > 0:
                for j in range(comparator_count):
                    connections.append(f"    mux_block -> comparator_{j} [color=black];")
            
            # Connect to relational operators
            if relop_count > 10:
                connections.append(f"    mux_block -> relationalop_block [color=black];")
            elif relop_count > 0:
                for j in range(relop_count):
                    connections.append(f"    mux_block -> relationalop_{j} [color=black];")
            
            # Connect to shifters
            if shifter_count > 10:
                connections.append(f"    mux_block -> shifter_block [color=black];")
            elif shifter_count > 0:
                for j in range(shifter_count):
                    connections.append(f"    mux_block -> shifter_{j} [color=black];")
            
            # Connect to multipliers
            if mul_count > 10:
                connections.append(f"    mux_block -> mul_block [color=black];")
            elif mul_count > 0:
                for j in range(mul_count):
                    connections.append(f"    mux_block -> mul_{j} [color=black];")
            
            # Connect to dividers
            if div_count > 10:
                connections.append(f"    mux_block -> div_block [color=black];")
            elif div_count > 0:
                for j in range(div_count):
                    connections.append(f"    mux_block -> div_{j} [color=black];")
        else:
            # Connect individual MUXes to computational units when not using a block
            for i in range(mux_count):
                # Connect to ALUs
                if alu_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> alu_block [color=black];")
                else:
                    for j in range(alu_count):
                        connections.append(f"    mux_{i % mux_count} -> alu_{j % alu_count} [color=black];")
                
                # Connect to adders
                if adder_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> adder_block [color=black];")
                elif adder_count > 0:
                    for j in range(adder_count):
                        connections.append(f"    mux_{i % mux_count} -> adder_{j % adder_count} [color=black];")
                
                # Connect to subtractors
                if subtractor_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> subtractor_block [color=black];")
                elif subtractor_count > 0:
                    for j in range(subtractor_count):
                        connections.append(f"    mux_{i % mux_count} -> subtractor_{j % subtractor_count} [color=black];")
                
                # Connect to bit operations
                if bitop_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> bitop_block [color=black];")
                elif bitop_count > 0:
                    for j in range(bitop_count):
                        connections.append(f"    mux_{i % mux_count} -> bitop_{j % bitop_count} [color=black];")
                
                # Connect to comparators
                if comparator_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> comparator_block [color=black];")
                elif comparator_count > 0:
                    for j in range(comparator_count):
                        connections.append(f"    mux_{i % mux_count} -> comparator_{j % comparator_count} [color=black];")
                
                # Connect to relational operators
                if relop_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> relationalop_block [color=black];")
                elif relop_count > 0:
                    for j in range(relop_count):
                        connections.append(f"    mux_{i % mux_count} -> relationalop_{j % relop_count} [color=black];")
                
                # Connect to shifters
                if shifter_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> shifter_block [color=black];")
                elif shifter_count > 0:
                    for j in range(shifter_count):
                        connections.append(f"    mux_{i % mux_count} -> shifter_{j % shifter_count} [color=black];")
                
                # Connect to multipliers
                if mul_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> mul_block [color=black];")
                elif mul_count > 0:
                    for j in range(mul_count):
                        connections.append(f"    mux_{i % mux_count} -> mul_{j % mul_count} [color=black];")
                
                # Connect to dividers
                if div_count > 10:
                    connections.append(f"    mux_{i % mux_count} -> div_block [color=black];")
                elif div_count > 0:
                    for j in range(div_count):
                        connections.append(f"    mux_{i % mux_count} -> div_{j % div_count} [color=black];")
        
        # 3. Connect computational units back to registers (result paths)
        # ALUs to registers
        if alu_count > 10:
            if reg_count > 10:
                connections.append(f"    alu_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    alu_block -> reg_{j} [color=black];")
        else:
            for i in range(alu_count):
                if reg_count > 10:
                    connections.append(f"    alu_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    alu_{i} -> reg_{j} [color=black];")
        
        # Adders to registers
        if adder_count > 10:
            if reg_count > 10:
                connections.append(f"    adder_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    adder_block -> reg_{j} [color=black];")
        elif adder_count > 0:
            for i in range(adder_count):
                if reg_count > 10:
                    connections.append(f"    adder_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    adder_{i} -> reg_{j} [color=black];")
        
        # Subtractors to registers
        if subtractor_count > 10:
            if reg_count > 10:
                connections.append(f"    subtractor_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    subtractor_block -> reg_{j} [color=black];")
        elif subtractor_count > 0:
            for i in range(subtractor_count):
                if reg_count > 10:
                    connections.append(f"    subtractor_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    subtractor_{i} -> reg_{j} [color=black];")
        
        # BitOps to registers
        if bitop_count > 10:
            if reg_count > 10:
                connections.append(f"    bitop_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    bitop_block -> reg_{j} [color=black];")
        elif bitop_count > 0:
            for i in range(bitop_count):
                if reg_count > 10:
                    connections.append(f"    bitop_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    bitop_{i} -> reg_{j} [color=black];")
        
        # Comparators to registers
        if comparator_count > 10:
            if reg_count > 10:
                connections.append(f"    comparator_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    comparator_block -> reg_{j} [color=black];")
        elif comparator_count > 0:
            for i in range(comparator_count):
                if reg_count > 10:
                    connections.append(f"    comparator_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    comparator_{i} -> reg_{j} [color=black];")
        
        # RelationalOps to registers
        if relop_count > 10:
            if reg_count > 10:
                connections.append(f"    relationalop_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    relationalop_block -> reg_{j} [color=black];")
        elif relop_count > 0:
            for i in range(relop_count):
                if reg_count > 10:
                    connections.append(f"    relationalop_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    relationalop_{i} -> reg_{j} [color=black];")
        
        # Shifters to registers
        if shifter_count > 10:
            if reg_count > 10:
                connections.append(f"    shifter_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    shifter_block -> reg_{j} [color=black];")
        elif shifter_count > 0:
            for i in range(shifter_count):
                if reg_count > 10:
                    connections.append(f"    shifter_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    shifter_{i} -> reg_{j} [color=black];")
        
        # Multipliers to registers
        if mul_count > 10:
            if reg_count > 10:
                connections.append(f"    mul_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    mul_block -> reg_{j} [color=black];")
        elif mul_count > 0:
            for i in range(mul_count):
                if reg_count > 10:
                    connections.append(f"    mul_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    mul_{i} -> reg_{j} [color=black];")
        
        # Dividers to registers
        if div_count > 10:
            if reg_count > 10:
                connections.append(f"    div_block -> reg_block [color=black];")
            else:
                for j in range(min(2, reg_count)):
                    connections.append(f"    div_block -> reg_{j} [color=black];")
        elif div_count > 0:
            for i in range(div_count):
                if reg_count > 10:
                    connections.append(f"    div_{i} -> reg_block [color=black];")
                else:
                    for j in range(min(2, reg_count)):
                        connections.append(f"    div_{i} -> reg_{j} [color=black];")
        
        # 4. Connect memory units
        if reg_count > 10:
            # Memory connections for consolidated register block
            if mem_count > 0:
                memory_connections.append(f"    mem_0 -> reg_block [label=\"load\", color=green];")
                memory_connections.append(f"    reg_block -> mem_0 [label=\"store\", color=red];")
            if scratchpad_count > 0:
                memory_connections.append(f"    spad_0 -> reg_block [label=\"load\", color=green];")
                memory_connections.append(f"    reg_block -> spad_0 [label=\"store\", color=red];")
        else:
            # Memory connections for individual registers
            for i in range(min(reg_count, 2)):
                # Load paths (memory to register)
                if mem_count > 0:
                    memory_connections.append(f"    mem_0 -> reg_{i} [label=\"load\", color=green];")
                if scratchpad_count > 0:
                    memory_connections.append(f"    spad_0 -> reg_{i} [label=\"load\", color=green];")
                
                # Store paths (register to memory)
                if mem_count > 0:
                    memory_connections.append(f"    reg_{i} -> mem_0 [label=\"store\", color=red];")
                if scratchpad_count > 0:
                    memory_connections.append(f"    reg_{i} -> spad_0 [label=\"store\", color=red];")
        
        # 5. Add forwarding paths for better datapath visualization
        # Add forwarding paths from each computational unit to MUXes
        
        # ALUs to MUXes (forwarding)
        if alu_count > 10:
            # Connect to a subset of MUXes (up to 4 or mux_count, whichever is smaller)
            if use_mux_block:
                connections.append(f"    alu_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 4)):
                    connections.append(f"    alu_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif alu_count > 0:
            # Connect individual ALUs to a subset of MUXes
            alu_connects = min(alu_count, 4)  # Connect up to 4 ALUs
            if use_mux_block:
                for i in range(alu_connects):
                    connections.append(f"    alu_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 4)  # Connect to up to 4 MUXes
                for i in range(alu_connects):
                    for j in range(mux_connects):
                        connections.append(f"    alu_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        
        # Adders to MUXes (forwarding)
        if adder_count > 10:
            # Connect to a subset of MUXes
            if use_mux_block:
                connections.append(f"    adder_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 3)):
                    connections.append(f"    adder_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif adder_count > 0:
            # Connect individual adders to a subset of MUXes
            adder_connects = min(adder_count, 2)  # Connect up to 2 adders
            if use_mux_block:
                for i in range(adder_connects):
                    connections.append(f"    adder_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 3)      # Connect to up to 3 MUXes
                for i in range(adder_connects):
                    for j in range(mux_connects):
                        connections.append(f"    adder_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        
        # BitOps to MUXes (forwarding)
        if bitop_count > 10:
            # Connect to a subset of MUXes
            if use_mux_block:
                connections.append(f"    bitop_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 3)):
                    connections.append(f"    bitop_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif bitop_count > 0:
            # Connect individual BitOps to a subset of MUXes
            bitop_connects = min(bitop_count, 2)  # Connect up to 2 BitOps
            if use_mux_block:
                for i in range(bitop_connects):
                    connections.append(f"    bitop_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 3)      # Connect to up to 3 MUXes
                for i in range(bitop_connects):
                    for j in range(mux_connects):
                        connections.append(f"    bitop_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")

        # Multipliers to MUXes (forwarding)  
        if mul_count > 10:
            # Connect to a subset of MUXes
            if use_mux_block:
                connections.append(f"    mul_block -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                for j in range(min(mux_count, 4)):
                    connections.append(f"    mul_block -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
        elif mul_count > 0:
            # Connect individual multipliers to a subset of MUXes
            mul_connects = min(mul_count, 3)     # Connect up to 3 multipliers
            if use_mux_block:
                for i in range(mul_connects):
                    connections.append(f"    mul_{i} -> mux_block [color=blue, style=dashed, label=\"fwd\"];")
            else:
                mux_connects = min(mux_count, 4)     # Connect to up to 4 MUXes
                for i in range(mul_connects):
                    for j in range(mux_connects):
                        connections.append(f"    mul_{i} -> mux_{j} [color=blue, style=dashed, label=\"fwd\"];")
                    
        # 6. Add clock and reset connections to all computational units
        clock_connections = []
        reset_connections = []
        
        # ALUs
        if alu_count > 10:
            clock_connections.append(f"    clock -> alu_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> alu_block [style=dashed, color=red];")
        else:
            for i in range(alu_count):
                clock_connections.append(f"    clock -> alu_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> alu_{i} [style=dashed, color=red];")
        
        # Adders
        if adder_count > 10:
            clock_connections.append(f"    clock -> adder_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> adder_block [style=dashed, color=red];")
        elif adder_count > 0:
            for i in range(adder_count):
                clock_connections.append(f"    clock -> adder_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> adder_{i} [style=dashed, color=red];")
        
        # Subtractors
        if subtractor_count > 10:
            clock_connections.append(f"    clock -> subtractor_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> subtractor_block [style=dashed, color=red];")
        elif subtractor_count > 0:
            for i in range(subtractor_count):
                clock_connections.append(f"    clock -> subtractor_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> subtractor_{i} [style=dashed, color=red];")
        
        # BitOps
        if bitop_count > 10:
            clock_connections.append(f"    clock -> bitop_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> bitop_block [style=dashed, color=red];")
        elif bitop_count > 0:
            for i in range(bitop_count):
                clock_connections.append(f"    clock -> bitop_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> bitop_{i} [style=dashed, color=red];")
        
        # Comparators
        if comparator_count > 10:
            clock_connections.append(f"    clock -> comparator_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> comparator_block [style=dashed, color=red];")
        elif comparator_count > 0:
            for i in range(comparator_count):
                clock_connections.append(f"    clock -> comparator_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> comparator_{i} [style=dashed, color=red];")
        
        # RelationalOps
        if relop_count > 10:
            clock_connections.append(f"    clock -> relationalop_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> relationalop_block [style=dashed, color=red];")
        elif relop_count > 0:
            for i in range(relop_count):
                clock_connections.append(f"    clock -> relationalop_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> relationalop_{i} [style=dashed, color=red];")
        
        # Shifters
        if shifter_count > 10:
            clock_connections.append(f"    clock -> shifter_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> shifter_block [style=dashed, color=red];")
        elif shifter_count > 0:
            for i in range(shifter_count):
                clock_connections.append(f"    clock -> shifter_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> shifter_{i} [style=dashed, color=red];")
        
        # Multipliers
        if mul_count > 10:
            clock_connections.append(f"    clock -> mul_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> mul_block [style=dashed, color=red];")
        elif mul_count > 0:
            for i in range(mul_count):
                clock_connections.append(f"    clock -> mul_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> mul_{i} [style=dashed, color=red];")
        
        # Dividers
        if div_count > 10:
            clock_connections.append(f"    clock -> div_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> div_block [style=dashed, color=red];")
        elif div_count > 0:
            for i in range(div_count):
                clock_connections.append(f"    clock -> div_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> div_{i} [style=dashed, color=red];")
        
        # Registers
        if reg_count > 10:
            clock_connections.append(f"    clock -> reg_block [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> reg_block [style=dashed, color=red];")
        else:
            for i in range(reg_count):
                clock_connections.append(f"    clock -> reg_{i} [style=dashed, color=blue];")
                reset_connections.append(f"    reset -> reg_{i} [style=dashed, color=red];")
        
        # Memory
        for i in range(mem_count):
            clock_connections.append(f"    clock -> mem_{i} [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> mem_{i} [style=dashed, color=red];")
        
        # Scratchpad
        for i in range(scratchpad_count):
            clock_connections.append(f"    clock -> spad_{i} [style=dashed, color=blue];")
            reset_connections.append(f"    reset -> spad_{i} [style=dashed, color=red];")
        
        # Add all connections to the DOT content
        dot_content.append("    // Data Connections")
        for connection in connections:
            dot_content.append(connection)
        
        dot_content.append("    // Memory Connections")
        for connection in memory_connections:
            dot_content.append(connection)
        
        dot_content.append("    // Control Connections")
        for connection in control_connections:
            dot_content.append(connection)
        
        dot_content.append("    // Clock Connections")
        for connection in clock_connections:
            dot_content.append(connection)
        
        dot_content.append("    // Reset Connections")
        for connection in reset_connections:
            dot_content.append(connection)
        if fifo_count > 0 or crossbar_count > 0:
            dot_content.append("    // Streaming Component Connections")
            
            # Connect FIFOs to computational units
            if fifo_count > 0:
                # Add clock and control for FIFOs
                for i in range(fifo_count):
                    fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                    # Add control connection
                    control_connections.append(f"    FSM -> fifo_{fifo_id} [label=\"control\", style=dashed, color=orange];")
                    # Add clock and reset
                    clock_connections.append(f"    clock -> fifo_{fifo_id} [style=dashed, color=blue];")
                    reset_connections.append(f"    reset -> fifo_{fifo_id} [style=dashed, color=red];")
                
                # Connect registers to FIFOs (for writing)
                if reg_count > 10:
                    # Connect consolidated register block to FIFOs
                    if fifo_count > 10:
                        # Use fifo_block for many FIFOs
                        dot_content.append(f"    reg_block -> fifo_block [color=blue, label=\"write\"];")
                    else:
                        # Connect to individual FIFOs
                        for i in range(min(fifo_count, 4)):
                            fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                            dot_content.append(f"    reg_block -> fifo_{fifo_id} [color=blue, label=\"write\"];")
                else:
                    # Connect individual registers to FIFOs
                    if fifo_count > 10:
                        # Use fifo_block for many FIFOs
                        for i in range(min(reg_count, 4)):
                            dot_content.append(f"    reg_{i} -> fifo_block [color=blue, label=\"write\"];")
                    else:
                        # Connect to individual FIFOs
                        for i in range(min(reg_count, 4)):
                            for j in range(min(fifo_count, 2)):
                                fifo_id = hw_allocated['FIFO'][j].id if hasattr(hw_allocated['FIFO'][j], 'id') else j
                                dot_content.append(f"    reg_{i} -> fifo_{fifo_id} [color=blue, label=\"write\"];")
                
                # Connect FIFOs to computational units (for reading)
                if fifo_count > 10:
                    # Use fifo_block for many FIFOs
                    
                    # Connect FIFO block to ALUs
                    if alu_count > 10:
                        dot_content.append(f"    fifo_block -> alu_block [color=green, label=\"read\"];")
                    else:
                        for j in range(min(alu_count, 2)):
                            dot_content.append(f"    fifo_block -> alu_{j} [color=green, label=\"read\"];")
                    
                    # Connect FIFO block to multipliers
                    if mul_count > 10:
                        dot_content.append(f"    fifo_block -> mul_block [color=green, label=\"read\"];")
                    elif mul_count > 0:
                        for j in range(min(mul_count, 2)):
                            dot_content.append(f"    fifo_block -> mul_{j} [color=green, label=\"read\"];")
                else:
                    # Connect individual FIFOs
                    for i in range(min(fifo_count, 4)):
                        fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                        
                        # Connect FIFOs to ALUs
                        if alu_count > 10:
                            dot_content.append(f"    fifo_{fifo_id} -> alu_block [color=green, label=\"read\"];")
                        else:
                            for j in range(min(alu_count, 2)):
                                dot_content.append(f"    fifo_{fifo_id} -> alu_{j} [color=green, label=\"read\"];")
                        
                        # Connect FIFOs to multipliers
                        if mul_count > 10:
                            dot_content.append(f"    fifo_{fifo_id} -> mul_block [color=green, label=\"read\"];")
                        elif mul_count > 0:
                            for j in range(min(mul_count, 2)):
                                dot_content.append(f"    fifo_{fifo_id} -> mul_{j} [color=green, label=\"read\"];")
                
                # Connect FIFOs to each other for dataflow pipelines
                if fifo_count > 10:
                    # With many FIFOs, just show a self-loop to indicate internal dataflow
                    dot_content.append(f"    fifo_block -> fifo_block [color=purple, label=\"internal stream\"];")
                elif fifo_count > 1:
                    # With few FIFOs, show the connections between them
                    for i in range(fifo_count - 1):
                        fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                        next_fifo_id = hw_allocated['FIFO'][i+1].id if hasattr(hw_allocated['FIFO'][i+1], 'id') else i+1
                        dot_content.append(f"    fifo_{fifo_id} -> fifo_{next_fifo_id} [color=purple, label=\"stream\"];")
            
            # Connect Crossbars
            if crossbar_count > 0:
                # Add control, clock and reset for Crossbars
                for i in range(crossbar_count):
                    # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                    if 'CROSSBAR' in hw_allocated and i < len(hw_allocated['CROSSBAR']):
                        xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                    elif 'Crossbar' in hw_allocated and i < len(hw_allocated['Crossbar']):
                        xbar_id = hw_allocated['Crossbar'][i].id if hasattr(hw_allocated['Crossbar'][i], 'id') else i
                    else:
                        xbar_id = i
                    
                    # Add control connection
                    control_connections.append(f"    FSM -> {'crossbar_block' if crossbar_count > 10 else f'xbar_{xbar_id}'} [label=\"control\", style=dashed, color=orange];")
                    # Add clock and reset
                    clock_connections.append(f"    clock -> {'crossbar_block' if crossbar_count > 10 else f'xbar_{xbar_id}'} [style=dashed, color=blue];")
                    reset_connections.append(f"    reset -> {'crossbar_block' if crossbar_count > 10 else f'xbar_{xbar_id}'} [style=dashed, color=red];")
                
                # Connect FIFOs to Crossbars (if both exist)
                if fifo_count > 0:
                    if fifo_count > 10 and crossbar_count > 10:
                        # Block-to-block connection
                        dot_content.append(f"    fifo_block -> crossbar_block [color=purple, label=\"route\"];")
                    elif fifo_count > 10:
                        # FIFO block to individual crossbars
                        for j in range(min(crossbar_count, 2)):
                            # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                            if 'CROSSBAR' in hw_allocated and j < len(hw_allocated['CROSSBAR']):
                                xbar_id = hw_allocated['CROSSBAR'][j].id if hasattr(hw_allocated['CROSSBAR'][j], 'id') else j
                            elif 'Crossbar' in hw_allocated and j < len(hw_allocated['Crossbar']):
                                xbar_id = hw_allocated['Crossbar'][j].id if hasattr(hw_allocated['Crossbar'][j], 'id') else j
                            else:
                                xbar_id = j
                            dot_content.append(f"    fifo_block -> xbar_{xbar_id} [color=purple, label=\"route\"];")
                    elif crossbar_count > 10:
                        # Individual FIFOs to crossbar block
                        for i in range(min(fifo_count, 4)):
                            fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                            dot_content.append(f"    fifo_{fifo_id} -> crossbar_block [color=purple, label=\"route\"];")
                    else:
                        # Individual FIFOs to individual crossbars
                        for i in range(min(fifo_count, 4)):
                            fifo_id = hw_allocated['FIFO'][i].id if hasattr(hw_allocated['FIFO'][i], 'id') else i
                            for j in range(min(crossbar_count, 2)):
                                # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                                if 'CROSSBAR' in hw_allocated and j < len(hw_allocated['CROSSBAR']):
                                    xbar_id = hw_allocated['CROSSBAR'][j].id if hasattr(hw_allocated['CROSSBAR'][j], 'id') else j
                                elif 'Crossbar' in hw_allocated and j < len(hw_allocated['Crossbar']):
                                    xbar_id = hw_allocated['Crossbar'][j].id if hasattr(hw_allocated['Crossbar'][j], 'id') else j
                                else:
                                    xbar_id = j
                                dot_content.append(f"    fifo_{fifo_id} -> xbar_{xbar_id} [color=purple, label=\"route\"];")
                
                # Connect Crossbars to computational units
                if crossbar_count > 10:
                    # Connect crossbar block to ALUs
                    if alu_count > 10:
                        dot_content.append(f"    crossbar_block -> alu_block [color=green, label=\"data\"];")
                    else:
                        for j in range(min(alu_count, 3)):
                            dot_content.append(f"    crossbar_block -> alu_{j} [color=green, label=\"data\"];")
                    
                    # Connect crossbar block to multipliers
                    if mul_count > 10:
                        dot_content.append(f"    crossbar_block -> mul_block [color=green, label=\"data\"];")
                    elif mul_count > 0:
                        for j in range(min(mul_count, 3)):
                            dot_content.append(f"    crossbar_block -> mul_{j} [color=green, label=\"data\"];")
                else:
                    # Connect individual crossbars
                    for i in range(min(crossbar_count, 2)):
                        # Try both 'CROSSBAR' and 'Crossbar' keys for backward compatibility
                        if 'CROSSBAR' in hw_allocated and i < len(hw_allocated['CROSSBAR']):
                            xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                        elif 'Crossbar' in hw_allocated and i < len(hw_allocated['Crossbar']):
                            xbar_id = hw_allocated['Crossbar'][i].id if hasattr(hw_allocated['Crossbar'][i], 'id') else i
                        else:
                            xbar_id = i
                        
                        # To ALUs
                        if alu_count > 10:
                            dot_content.append(f"    xbar_{xbar_id} -> alu_block [color=green, label=\"data\"];")
                        else:
                            for j in range(min(alu_count, 3)):
                                dot_content.append(f"    xbar_{xbar_id} -> alu_{j} [color=green, label=\"data\"];")
                    
                        # To multipliers
                        if mul_count > 10:
                            dot_content.append(f"    xbar_{xbar_id} -> mul_block [color=green, label=\"data\"];")
                        elif mul_count > 0:
                            for j in range(min(mul_count, 3)):
                                dot_content.append(f"    xbar_{xbar_id} -> mul_{j} [color=green, label=\"data\"];")
                
                # Connect Crossbars to registers
                if crossbar_count > 10:
                    # Connect crossbar block to registers
                    if reg_count > 10:
                        dot_content.append(f"    crossbar_block -> reg_block [color=blue, label=\"result\"];")
                    else:
                        for j in range(min(reg_count, 4)):
                            dot_content.append(f"    crossbar_block -> reg_{j} [color=blue, label=\"result\"];")
                else:
                    # Connect individual crossbars to registers
                    if reg_count > 10:
                        for i in range(min(crossbar_count, 2)):
                            xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                            dot_content.append(f"    xbar_{xbar_id} -> reg_block [color=blue, label=\"result\"];")
                    else:
                        for i in range(min(crossbar_count, 2)):
                            xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                            for j in range(min(reg_count, 4)):
                                dot_content.append(f"    xbar_{xbar_id} -> reg_{j} [color=blue, label=\"result\"];")
                
                # Connect Crossbars to each other for multi-stage routing
                if crossbar_count > 10:
                    # With many crossbars, just show a self-loop to indicate internal routing
                    dot_content.append(f"    crossbar_block -> crossbar_block [color=purple, label=\"internal routing\"];")
                elif crossbar_count > 1:
                    # With few crossbars, show the connections between them
                    for i in range(crossbar_count - 1):
                        xbar_id = hw_allocated['CROSSBAR'][i].id if hasattr(hw_allocated['CROSSBAR'][i], 'id') else i
                        next_xbar_id = hw_allocated['CROSSBAR'][i+1].id if hasattr(hw_allocated['CROSSBAR'][i+1], 'id') else i+1
                        dot_content.append(f"    xbar_{xbar_id} -> xbar_{next_xbar_id} [color=purple, label=\"route\"];")
    # Close the graph
    dot_content.append("}")
    
    return "\n".join(dot_content)
