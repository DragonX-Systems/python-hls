"""
Netlist classes for representing hardware structures.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union, Any, Tuple
import os


@dataclass
class NetlistPort:
    """Port in a hardware module."""
    name: str
    direction: str  # "input", "output", "inout" for Verilog; "in", "out", "inout" for VHDL
    width: int
    is_signed: bool = False


@dataclass
class NetlistSignal:
    """Signal or wire in a hardware module."""
    name: str
    width: int
    is_signed: bool = False
    is_reg: bool = False
    
    # Hardware resource mapping
    resource_type: Optional[str] = None  # "register", "adder", "multiplier", etc.
    resource_instance: Optional[int] = None  # Instance ID of resource


@dataclass
class NetlistOperation:
    """Operation in a hardware module."""
    operation: str  # "+", "-", "*", etc.
    operands: List[Union[str, int, float]]  # Signal names or constants
    result: str  # Result signal name
    control_step: int = 0  # Scheduled control step
    resource_name: Optional[str] = None  # Name of the resource this operation is bound to
    memory_resource: Optional[str] = None  # For memory operations, the target memory resource


@dataclass
class NetlistResource:
    """Hardware resource in a module."""
    name: str
    type: str  # "register", "adder", "multiplier", "scratchpad", etc.
    bit_width: int
    latency: int
    area: float
    power: float
    
    # Technology-specific parameters
    technology_node: int  # in nm
    supply_voltage: float  # in V
    
    # Memory-specific parameters
    memory_size: int = 1  # Size in elements for memory resources
    memory_type: str = "none"  # "scratchpad", "sram", "register_file", "none"
    
    # Utilization
    utilization: List[int] = field(default_factory=list)  # Control steps where resource is used


@dataclass
class NetlistModule:
    """Hardware module (entity in VHDL, module in Verilog)."""
    name: str
    ports: List[NetlistPort] = field(default_factory=list)
    signals: List[NetlistSignal] = field(default_factory=list)
    resources: List[NetlistResource] = field(default_factory=list)
    operations: List[NetlistOperation] = field(default_factory=list)
    power_breakdown: Dict[str, float] = field(default_factory=dict)
    # HDL blocks (content dependent on target language)
    verilog_blocks: List[str] = field(default_factory=list)
    vhdl_blocks: List[str] = field(default_factory=list)
    
    # Performance metrics
    latency: int = 0  # Clock cycles
    initiation_interval: int = 0  # For pipelined designs
    clock_frequency_mhz: float = 100.0  # Default to 100 MHz
    
    # Resource usage
    area: float = 0.0
    power: float = 0.0
    energy_per_operation: float = 0.0
    
    @property
    def latency_ns(self) -> float:
        """Get the latency in nanoseconds."""
        if self.clock_frequency_mhz <= 0:
            return 0.0
        return (self.latency * 1000.0) / self.clock_frequency_mhz
    
    def add_port(self, port: NetlistPort) -> None:
        """Add a port to the module."""
        self.ports.append(port)
    
    def add_signal(self, signal: NetlistSignal) -> None:
        """Add a signal to the module."""
        self.signals.append(signal)
    
    def add_resource(self, resource: NetlistResource) -> None:
        """Add a hardware resource to the module."""
        self.resources.append(resource)
        # Update the module's area and power when a resource is added
        self.area = sum(r.area for r in self.resources)
        self.power = sum(r.power for r in self.resources)
        self.power_breakdown = {r.name: r.power for r in self.resources}
    
    def add_operation(self, operation: NetlistOperation) -> None:
        """Add an operation to the module."""
        self.operations.append(operation)
    
    def add_verilog_block(self, block: str) -> None:
        """Add a Verilog code block to the module."""
        self.verilog_blocks.append(block)
    
    def add_vhdl_block(self, block: str) -> None:
        """Add a VHDL code block to the module."""
        self.vhdl_blocks.append(block)


@dataclass
class Netlist:
    """Top-level netlist containing modules."""
    target_language: str  # "verilog" or "vhdl"
    modules: Dict[str, NetlistModule] = field(default_factory=dict)
    
    # Technology parameters
    technology_node: int = 45  # Default to 45nm
    supply_voltage: float = 1.0  # Default to 1.0V
    
    # Performance metrics
    total_area: float = 0.0
    total_power: float = 0.0
    critical_path: float = 0.0  # in ns
    
    def add_module(self, module: NetlistModule) -> None:
        """Add a module to the netlist."""
        self.modules[module.name] = module
        
        # Update overall metrics
        self.total_area += module.area
        self.total_power += module.power
    
    def save(self, output_file: str) -> None:
        """
        Save the netlist to a file.
        
        Args:
            output_file: Path to output file
        """
        with open(output_file, 'w') as f:
            if self.target_language.lower() == "verilog":
                self._save_verilog(f)
            elif self.target_language.lower() == "vhdl":
                self._save_vhdl(f)
            else:
                raise ValueError(f"Unsupported target language: {self.target_language}")
    
    def _save_verilog(self, file) -> None:
        """Save the netlist as Verilog."""
        for module_name, module in self.modules.items():
            # Module declaration
            file.write(f"module {module_name} (\n")
            
            # Ports
            port_strs = []
            for port in module.ports:
                direction = port.direction
                if port.width > 1:
                    if port.is_signed:
                        port_strs.append(f"    {direction} signed [{port.width-1}:0] {port.name}")
                    else:
                        port_strs.append(f"    {direction} [{port.width-1}:0] {port.name}")
                else:
                    port_strs.append(f"    {direction} {port.name}")
            
            file.write(",\n".join(port_strs))
            file.write("\n);\n\n")
            
            # Signals
            for signal in module.signals:
                if signal.is_reg:
                    reg_or_wire = "reg"
                else:
                    reg_or_wire = "wire"
                
                if signal.width > 1:
                    if signal.is_signed:
                        file.write(f"{reg_or_wire} signed [{signal.width-1}:0] {signal.name};\n")
                    else:
                        file.write(f"{reg_or_wire} [{signal.width-1}:0] {signal.name};\n")
                else:
                    file.write(f"{reg_or_wire} {signal.name};\n")
            
            file.write("\n")
            
            # Verilog blocks
            for block in module.verilog_blocks:
                file.write(block)
                file.write("\n\n")
            
            file.write("endmodule\n\n")
    
    def _save_vhdl(self, file) -> None:
        """Save the netlist as VHDL."""
        for module_name, module in self.modules.items():
            # Library declarations
            file.write("library IEEE;\n")
            file.write("use IEEE.STD_LOGIC_1164.ALL;\n")
            file.write("use IEEE.NUMERIC_STD.ALL;\n\n")
            
            # Entity declaration
            file.write(f"entity {module_name} is\n")
            if module.ports:
                file.write("Port (\n")
                
                port_strs = []
                for port in module.ports:
                    direction = port.direction
                    if port.width > 1:
                        if port.is_signed:
                            port_strs.append(f"    {port.name} : {direction} signed({port.width-1} downto 0)")
                        else:
                            port_strs.append(f"    {port.name} : {direction} std_logic_vector({port.width-1} downto 0)")
                    else:
                        port_strs.append(f"    {port.name} : {direction} std_logic")
                
                file.write(";\n".join(port_strs))
                file.write("\n);\n")
            
            file.write("end entity;\n\n")
            
            # Architecture
            file.write(f"architecture rtl of {module_name} is\n")
            
            # Signal declarations
            for signal in module.signals:
                if signal.width > 1:
                    if signal.is_signed:
                        file.write(f"signal {signal.name} : signed({signal.width-1} downto 0);\n")
                    else:
                        file.write(f"signal {signal.name} : std_logic_vector({signal.width-1} downto 0);\n")
                else:
                    file.write(f"signal {signal.name} : std_logic;\n")
            
            file.write("\nbegin\n\n")
            
            # VHDL blocks
            for block in module.vhdl_blocks:
                file.write(block)
                file.write("\n\n")
            
            file.write("end architecture;\n\n")
    
    def get_resource_report(self) -> Dict[str, Any]:
        """
        Get a report of resource usage.
        
        Returns:
            Dictionary with resource usage information
        """
        report = {
            "technology_node": self.technology_node,
            "supply_voltage": self.supply_voltage,
            "total_area": self.total_area,
            "total_power": self.total_power,
            "critical_path": self.critical_path,
            "modules": {}
        }
        
        for module_name, module in self.modules.items():
            module_report = {
                "latency": module.latency,
                "initiation_interval": module.initiation_interval,
                "area": module.area,
                "power": module.power,
                "energy_per_operation": module.energy_per_operation,
                "power_breakdown": module.power_breakdown,
                "resources": {}
            }
            
            # Group resources by type
            resource_types = {}
            for resource in module.resources:
                if resource.type not in resource_types:
                    resource_types[resource.type] = 0
                resource_types[resource.type] += 1
            
            module_report["resources"] = resource_types
            report["modules"][module_name] = module_report
        
        return report 