"""
Streaming components for dataflow architectures.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union, Any, Tuple
from .netlist import NetlistResource, NetlistSignal, NetlistPort, NetlistOperation

@dataclass
class FIFOResource(NetlistResource):
    """
    FIFO (First-In-First-Out) buffer resource for streaming data.
    
    FIFOs are used to buffer data between pipeline stages, allowing for 
    asynchronous processing and decoupling of producer and consumer stages.
    """
    depth: int = 16  # Default FIFO depth (how many elements it can store)
    data_width: int = 32  # Width of each data element in bits
    
    # Additional FIFO-specific parameters
    almost_full_threshold: int = 0  # Configurable threshold for almost_full signal
    almost_empty_threshold: int = 0  # Configurable threshold for almost_empty signal
    supports_backpressure: bool = True  # Whether the FIFO supports backpressure
    
    # Performance and power characteristics
    read_latency: int = 1  # Latency of read operations in cycles
    write_latency: int = 1  # Latency of write operations in cycles
    
    # AXI interface configurations
    input_interface: str = "simple"  # Options: "simple", "axis", "axilite"
    output_interface: str = "simple"  # Options: "simple", "axis", "axilite"
    
    # AXI-Stream specific parameters
    axis_tuser_width: int = 0  # User-defined data width (0 means not used)
    axis_tid_width: int = 0    # Stream ID width (0 means not used)
    axis_tdest_width: int = 0  # Destination ID width (0 means not used)
    axis_tkeep: bool = False   # Whether to include TKEEP signal
    axis_tlast: bool = False   # Whether to include TLAST signal
    
    # AXI-Lite specific parameters
    axilite_addr_width: int = 32  # Address width for AXI-Lite interface
    axilite_has_strb: bool = True  # Whether to include STRB signal
    axilite_has_resp: bool = True  # Whether to include RESP signal
    
    def __post_init__(self):
        self.type = "fifo"
        # Calculate area based on depth and data width
        # These are simplified area models based on typical FPGA resources
        self.area = self.depth * self.data_width * 0.05
        self.power = self.depth * self.data_width * 0.001
        self.memory_type = "fifo"
        
        # Add interface type to the resource name for clarity
        if self.input_interface != "simple" or self.output_interface != "simple":
            if not hasattr(self, 'name') or not self.name:
                self.name = f"fifo_{id(self)}"
            
            if self.input_interface == "axis" and self.output_interface == "axis":
                self.name = f"{self.name}_axis"
            elif self.input_interface == "axilite" and self.output_interface == "axilite":
                self.name = f"{self.name}_axilite"
            elif self.input_interface == "axis" and self.output_interface != "axis":
                self.name = f"{self.name}_axis_in"
            elif self.input_interface != "axis" and self.output_interface == "axis":
                self.name = f"{self.name}_axis_out"
            elif self.input_interface == "axilite" and self.output_interface != "axilite":
                self.name = f"{self.name}_axilite_in"
            elif self.input_interface != "axilite" and self.output_interface == "axilite":
                self.name = f"{self.name}_axilite_out"

@dataclass
class CrossbarResource(NetlistResource):
    """
    Crossbar network for connecting multiple inputs to multiple outputs.
    
    Crossbars allow dynamic routing of data from input ports to output ports,
    enabling flexible data movement patterns required by dataflow architectures.
    """
    num_inputs: int = 4  # Number of input ports
    num_outputs: int = 4  # Number of output ports
    data_width: int = 32  # Width of each data element in bits
    
    # Crossbar configuration options
    allows_multicast: bool = False  # Whether multiple outputs can receive same input
    allows_broadcast: bool = False  # Whether one input can be sent to all outputs
    arbitration_scheme: str = "round-robin"  # Options: "round-robin", "fixed-priority", "fair"
    
    # Performance characteristics
    arbitration_latency: int = 1  # Latency of arbitration in cycles
    
    def __post_init__(self):
        self.type = "crossbar"
        # Calculate area based on crossbar size
        # Crossbar complexity grows with inputs*outputs
        self.area = self.num_inputs * self.num_outputs * self.data_width * 0.1
        self.power = self.num_inputs * self.num_outputs * self.data_width * 0.002
        # Crossbar latency depends on arbitration scheme
        self.latency = self.arbitration_latency

@dataclass
class StreamingChannel:
    """
    Represents a streaming data channel between components.
    
    A streaming channel connects producers and consumers of data,
    potentially through FIFOs and crossbars.
    """
    name: str
    source: str  # Source component name
    destination: str  # Destination component name
    data_width: int
    fifo_resource: Optional[str] = None  # Name of FIFO resource, if any
    crossbar_resource: Optional[str] = None  # Name of crossbar resource, if any
    
    # Channel characteristics
    has_valid: bool = True  # Whether channel has a valid signal
    has_ready: bool = True  # Whether channel has a ready signal for backpressure
    
    # For visualization and documentation
    channel_type: str = "data"  # "data", "control", "address", etc.
    
    # Interface type
    interface_type: str = "simple"  # "simple", "axis", "axilite"
    
    # AXI-Stream specific signals
    axis_has_tuser: bool = False
    axis_has_tid: bool = False
    axis_has_tdest: bool = False
    axis_has_tkeep: bool = False
    axis_has_tlast: bool = False
    
    # AXI-Lite specific signals
    axilite_has_strb: bool = False
    axilite_has_resp: bool = False
    axilite_addr_width: int = 32
    
    def get_signals(self) -> List[str]:
        """Get all signal names associated with this channel."""
        signals = [f"{self.name}_data"]
        
        if self.interface_type == "simple":
            # Simple interface signals
            if self.has_valid:
                signals.append(f"{self.name}_valid")
            if self.has_ready:
                signals.append(f"{self.name}_ready")
                
        elif self.interface_type == "axis":
            # AXI-Stream interface signals
            signals = [f"{self.name}_tdata"]
            signals.append(f"{self.name}_tvalid")
            signals.append(f"{self.name}_tready")
            
            if self.axis_has_tuser:
                signals.append(f"{self.name}_tuser")
            if self.axis_has_tid:
                signals.append(f"{self.name}_tid")
            if self.axis_has_tdest:
                signals.append(f"{self.name}_tdest")
            if self.axis_has_tkeep:
                signals.append(f"{self.name}_tkeep")
            if self.axis_has_tlast:
                signals.append(f"{self.name}_tlast")
                
        elif self.interface_type == "axilite":
            # AXI-Lite interface signals
            signals = []
            # Address channel
            signals.extend([
                f"{self.name}_awaddr",
                f"{self.name}_awvalid",
                f"{self.name}_awready",
                # Write data channel
                f"{self.name}_wdata",
                f"{self.name}_wvalid",
                f"{self.name}_wready"
            ])
            
            if self.axilite_has_strb:
                signals.append(f"{self.name}_wstrb")
                
            # Write response channel
            if self.axilite_has_resp:
                signals.extend([
                    f"{self.name}_bresp",
                    f"{self.name}_bvalid",
                    f"{self.name}_bready"
                ])
                
            # Read address channel
            signals.extend([
                f"{self.name}_araddr",
                f"{self.name}_arvalid",
                f"{self.name}_arready",
                # Read data channel
                f"{self.name}_rdata",
                f"{self.name}_rvalid",
                f"{self.name}_rready"
            ])
            
            if self.axilite_has_resp:
                signals.append(f"{self.name}_rresp")
                
        return signals


@dataclass
class StreamingArchitecture:
    """
    Represents a dataflow architecture with streaming components.
    
    This class helps track connections between streaming components
    and manages the overall dataflow architecture.
    """
    name: str
    channels: List[StreamingChannel] = field(default_factory=list)
    fifos: Dict[str, FIFOResource] = field(default_factory=dict)
    crossbars: Dict[str, CrossbarResource] = field(default_factory=dict)
    
    # Dependency tracking
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    
    def add_channel(self, channel: StreamingChannel) -> None:
        """Add a streaming channel to the architecture."""
        self.channels.append(channel)
        
        # Add to dependency tracking
        if channel.source not in self.dependencies:
            self.dependencies[channel.source] = []
        self.dependencies[channel.source].append(channel.destination)
    
    def add_fifo(self, name: str, fifo: FIFOResource) -> None:
        """Add a FIFO to the architecture."""
        self.fifos[name] = fifo
    
    def add_crossbar(self, name: str, crossbar: CrossbarResource) -> None:
        """Add a crossbar to the architecture."""
        self.crossbars[name] = crossbar
    
    def get_component_dependencies(self, component_name: str) -> List[str]:
        """Get all components that depend on the given component."""
        return self.dependencies.get(component_name, [])
    
    def generate_verilog(self) -> str:
        """Generate Verilog code for the streaming architecture."""
        # This would generate the interconnects and instantiate components
        # Implementation depends on the specific requirements
        pass
    
    def generate_system_diagram(self) -> str:
        """Generate a system diagram of the streaming architecture."""
        # This would create a visual representation of the architecture
        # Could use Graphviz or similar tools
        pass

# Functions to create streaming operations that can be incorporated into the netlist
def create_fifo_write_operation(fifo_name: str, data_signal: str, control_step: int, 
                               interface_type: str = "simple") -> NetlistOperation:
    """
    Create a FIFO write operation.
    
    Args:
        fifo_name: Name of the FIFO resource
        data_signal: Name of the data signal to write
        control_step: Control step for this operation
        interface_type: Interface type ('simple', 'axis', 'axilite')
        
    Returns:
        NetlistOperation: The created operation
    """
    if interface_type == "simple":
        return NetlistOperation(
            operation="fifo_write",
            operands=[data_signal],
            result=f"{fifo_name}_data_in",
            control_step=control_step,
            resource_name=fifo_name
        )
    elif interface_type == "axis":
        return NetlistOperation(
            operation="axis_fifo_write",
            operands=[data_signal],
            result=f"{fifo_name}_tdata",
            control_step=control_step,
            resource_name=fifo_name
        )
    elif interface_type == "axilite":
        return NetlistOperation(
            operation="axilite_fifo_write",
            operands=[data_signal],
            result=f"{fifo_name}_wdata",
            control_step=control_step,
            resource_name=fifo_name
        )
    else:
        raise ValueError(f"Unsupported interface type: {interface_type}")

def create_fifo_read_operation(fifo_name: str, result_signal: str, control_step: int,
                              interface_type: str = "simple") -> NetlistOperation:
    """
    Create a FIFO read operation.
    
    Args:
        fifo_name: Name of the FIFO resource
        result_signal: Name of the signal to store the read result
        control_step: Control step for this operation
        interface_type: Interface type ('simple', 'axis', 'axilite')
        
    Returns:
        NetlistOperation: The created operation
    """
    if interface_type == "simple":
        return NetlistOperation(
            operation="fifo_read",
            operands=[f"{fifo_name}_data_out"],
            result=result_signal,
            control_step=control_step,
            resource_name=fifo_name
        )
    elif interface_type == "axis":
        return NetlistOperation(
            operation="axis_fifo_read",
            operands=[f"{fifo_name}_tdata"],
            result=result_signal,
            control_step=control_step,
            resource_name=fifo_name
        )
    elif interface_type == "axilite":
        return NetlistOperation(
            operation="axilite_fifo_read",
            operands=[f"{fifo_name}_rdata"],
            result=result_signal,
            control_step=control_step,
            resource_name=fifo_name
        )
    else:
        raise ValueError(f"Unsupported interface type: {interface_type}")

def create_crossbar_route_operation(crossbar_name: str, input_port: int, output_port: int, 
                                    data_signal: str, result_signal: str, control_step: int) -> NetlistOperation:
    """Create a crossbar routing operation."""
    return NetlistOperation(
        operation="crossbar_route",
        operands=[data_signal, str(input_port), str(output_port)],
        result=result_signal,
        control_step=control_step,
        resource_name=crossbar_name
    ) 