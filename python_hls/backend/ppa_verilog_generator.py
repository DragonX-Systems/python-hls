"""
PPA (Power, Performance, Area) Optimized Verilog Generator.
Industry-grade Verilog generation with PPA objective-based optimization.
"""

import os
import logging
from typing import Dict, List, Optional, Set, Union, Any, Tuple
from dataclasses import dataclass

from .verilog_generator import VerilogGenerator
from ..ir.ir_nodes import (
    IR, IRFunction, IRBlock, IRInstruction,
    IRVariable, IRConstant, IROperation, OperationType, DataType
)
from ..netlist import Netlist, NetlistModule, NetlistPort, NetlistSignal, NetlistResource
from ..tech import TechLibrary, ResourceModel

# Set up logger
logger = logging.getLogger(__name__)

@dataclass
class PPAObjective:
    """Represents a PPA optimization objective with weights."""
    area_weight: float = 1.0
    performance_weight: float = 1.0
    power_weight: float = 1.0
    
    @classmethod
    def area_optimized(cls) -> 'PPAObjective':
        """Create area-optimized objective."""
        return cls(area_weight=3.0, performance_weight=0.5, power_weight=1.0)
    
    @classmethod
    def performance_optimized(cls) -> 'PPAObjective':
        """Create performance-optimized objective."""
        return cls(area_weight=0.5, performance_weight=3.0, power_weight=1.0)
    
    @classmethod
    def power_optimized(cls) -> 'PPAObjective':
        """Create power-optimized objective."""
        return cls(area_weight=1.0, performance_weight=0.5, power_weight=3.0)
    
    @classmethod
    def balanced(cls) -> 'PPAObjective':
        """Create balanced objective."""
        return cls(area_weight=1.0, performance_weight=1.0, power_weight=1.0)

@dataclass
class OptimizationContext:
    """Context information for optimization decisions."""
    tech_node: int
    target_frequency: float  # MHz
    resource_constraints: Dict[str, int]
    loop_unroll_factors: Dict[str, int]
    pipeline_depth: int
    has_matrix_operations: bool
    memory_footprint: int  # bytes
    critical_path_operations: List[str]


class PPAOptimizedVerilogGenerator(VerilogGenerator):
    """
    PPA-optimized Verilog generator that adapts code generation based on
    Power, Performance, and Area objectives.
    """
    
    def __init__(self, ppa_objective: str = "area", tech_node: int = 45):
        """
        Initialize the PPA-optimized Verilog generator.
        
        Args:
            ppa_objective: Primary PPA objective ("area", "performance", "power", "balanced")
            tech_node: Technology node in nm
        """
        super().__init__()
        
        self.ppa_objective_str = ppa_objective
        self.tech_node = tech_node
        
        # Create PPA objective weights
        if ppa_objective == "area":
            self.ppa_objective = PPAObjective.area_optimized()
        elif ppa_objective == "performance":
            self.ppa_objective = PPAObjective.performance_optimized()
        elif ppa_objective == "power":
            self.ppa_objective = PPAObjective.power_optimized()
        else:
            self.ppa_objective = PPAObjective.balanced()
        
        # Initialize technology library for tech node specific optimizations
        self.tech_library = TechLibrary(tech_node=tech_node)
        
        # Optimization context
        self.optimization_context = None
        self.netlist_resources = []
        
        logger.info(f"Initialized PPA-optimized Verilog generator for {ppa_objective} optimization at {tech_node}nm")
    
    def generate(self, ir: IR, netlist_resources: List[NetlistResource] = None) -> Netlist:
        """
        Generate PPA-optimized Verilog netlist from IR.
        
        Args:
            ir: IR to generate code for
            netlist_resources: Allocated netlist resources
            
        Returns:
            Netlist with PPA-optimized Verilog code
        """
        self.netlist_resources = netlist_resources or []
        
        # Create optimization context
        self.optimization_context = self._create_optimization_context(ir)
        
        # Log optimization strategy
        logger.info(f"Generating {self.ppa_objective_str}-optimized Verilog for {self.tech_node}nm")
        logger.info(f"Optimization context: freq={self.optimization_context.target_frequency:.1f}MHz, "
                   f"resources={len(self.netlist_resources)}, "
                   f"memory={self.optimization_context.memory_footprint}B")
        
        # Generate netlist using PPA-optimized approach
        netlist = Netlist(target_language="verilog")
        
        # Process each function with PPA-aware generation
        for func_name, func in ir.functions.items():
            logger.info(f"Generating PPA-optimized module for function: {func_name}")
            
            # Create module with PPA-optimized implementation
            module = self._generate_ppa_optimized_module(func)
            netlist.add_module(module)
        
        return netlist
    
    def _create_optimization_context(self, ir: IR) -> OptimizationContext:
        """Create optimization context from IR and resources."""
        # Extract context information
        tech_node = self.tech_node
        target_frequency = getattr(ir, 'target_frequency_mhz', 100.0)
        
        # Analyze resource constraints
        resource_constraints = {}
        for resource in self.netlist_resources:
            res_type = resource.type
            if res_type not in resource_constraints:
                resource_constraints[res_type] = 0
            resource_constraints[res_type] += 1
        
        # Analyze loop characteristics
        loop_unroll_factors = {}
        pipeline_depth = 1
        has_matrix_operations = False
        memory_footprint = 0
        critical_path_operations = []
        
        for func_name, func in ir.functions.items():
            # Check for matrix operations
            if hasattr(func, 'has_matrix_operations') and func.has_matrix_operations:
                has_matrix_operations = True
            
            # Check pipeline depth
            if hasattr(func, 'pipeline_depth') and func.pipeline_depth > pipeline_depth:
                pipeline_depth = func.pipeline_depth
            
            # Analyze memory footprint
            for var_name, var in func.local_vars.items():
                if hasattr(var, 'memory_size') and var.memory_size > 0:
                    memory_footprint += var.memory_size * (var.bit_width // 8)
            
            # Analyze loop unrolling
            for block in func.blocks:
                if hasattr(block, 'unroll') and block.unroll:
                    unroll_factor = getattr(block, 'unroll_factor', 1)
                    loop_unroll_factors[f"{func_name}_{block.name}"] = unroll_factor
        
        return OptimizationContext(
            tech_node=tech_node,
            target_frequency=target_frequency,
            resource_constraints=resource_constraints,
            loop_unroll_factors=loop_unroll_factors,
            pipeline_depth=pipeline_depth,
            has_matrix_operations=has_matrix_operations,
            memory_footprint=memory_footprint,
            critical_path_operations=critical_path_operations
        )
    
    def _generate_ppa_optimized_module(self, func: IRFunction) -> NetlistModule:
        """
        Generate a PPA-optimized module for a function.
        
        Args:
            func: IRFunction to generate code for
            
        Returns:
            NetlistModule with PPA-optimized Verilog code
        """
        module = NetlistModule(name=func.name)
        
        # Generate PPA-optimized Verilog code
        if self.ppa_objective_str == "area":
            verilog_code = self._generate_area_optimized_module(func)
        elif self.ppa_objective_str == "performance":
            verilog_code = self._generate_performance_optimized_module(func)
        elif self.ppa_objective_str == "power":
            verilog_code = self._generate_power_optimized_module(func)
        else:
            verilog_code = self._generate_balanced_module(func)
        
        module.add_verilog_block(verilog_code)
        
        # Add resource information to module
        self._add_resource_info_to_module(module, func)
        
        return module
    
    def _generate_area_optimized_module(self, func: IRFunction) -> str:
        """Generate area-optimized Verilog module."""
        logger.info(f"Generating area-optimized module for {func.name}")
        
        code = []
        
        # Module header with minimal ports
        code.extend(self._generate_area_optimized_header(func))
        
        # Signal declarations with resource sharing considerations
        code.extend(self._generate_area_optimized_signals(func))
        
        # Compact state machine for area optimization
        code.extend(self._generate_area_optimized_fsm(func))
        
        # Shared datapath with resource multiplexing
        code.extend(self._generate_area_optimized_datapath(func))
        
        # Memory subsystem with sharing
        code.extend(self._generate_area_optimized_memory(func))
        
        # Clock gating for unused resources
        code.extend(self._generate_area_optimized_clock_gating(func))
        
        # Module footer
        code.append("endmodule")
        
        return "\n".join(code)
    
    def _generate_performance_optimized_module(self, func: IRFunction) -> str:
        """Generate performance-optimized Verilog module."""
        logger.info(f"Generating performance-optimized module for {func.name}")
        
        code = []
        
        # Module header with parallel interfaces
        code.extend(self._generate_performance_optimized_header(func))
        
        # Signal declarations for parallel execution
        code.extend(self._generate_performance_optimized_signals(func))
        
        # Parallel state machines or pipelined control
        code.extend(self._generate_performance_optimized_fsm(func))
        
        # Parallel datapath with dedicated resources
        code.extend(self._generate_performance_optimized_datapath(func))
        
        # High-bandwidth memory subsystem
        code.extend(self._generate_performance_optimized_memory(func))
        
        # Pipeline registers for high frequency
        code.extend(self._generate_performance_optimized_pipeline(func))
        
        # Module footer
        code.append("endmodule")
        
        return "\n".join(code)
    
    def _generate_power_optimized_module(self, func: IRFunction) -> str:
        """Generate power-optimized Verilog module."""
        logger.info(f"Generating power-optimized module for {func.name}")
        
        code = []
        
        # Module header with power management
        code.extend(self._generate_power_optimized_header(func))
        
        # Signal declarations with power considerations
        code.extend(self._generate_power_optimized_signals(func))
        
        # Power-aware state machine with sleep states
        code.extend(self._generate_power_optimized_fsm(func))
        
        # Clock-gated datapath
        code.extend(self._generate_power_optimized_datapath(func))
        
        # Power-efficient memory subsystem
        code.extend(self._generate_power_optimized_memory(func))
        
        # Extensive clock gating and power management
        code.extend(self._generate_power_optimized_power_management(func))
        
        # Module footer
        code.append("endmodule")
        
        return "\n".join(code)
    
    def _generate_balanced_module(self, func: IRFunction) -> str:
        """Generate balanced PPA module."""
        logger.info(f"Generating balanced PPA module for {func.name}")
        
        # Use the existing complete function module as baseline
        # but with some PPA-aware enhancements
        code = []
        
        # Standard module header
        code.extend(self._generate_standard_header(func))
        
        # Balanced signal declarations
        code.extend(self._generate_balanced_signals(func))
        
        # Efficient state machine
        code.extend(self._generate_balanced_fsm(func))
        
        # Balanced datapath
        code.extend(self._generate_balanced_datapath(func))
        
        # Standard memory subsystem
        code.extend(self._generate_balanced_memory(func))
        
        # Selective clock gating
        code.extend(self._generate_balanced_clock_gating(func))
        
        # Module footer
        code.append("endmodule")
        
        return "\n".join(code)
    
    # Area-optimized generation methods
    def _generate_area_optimized_header(self, func: IRFunction) -> List[str]:
        """Generate area-optimized module header."""
        code = []
        
        # Minimal port list for area optimization
        ports = []
        ports.append("    input wire clk")
        ports.append("    input wire rst_n")
        
        # Function parameters - packed if possible
        for param in func.parameters:
            if param.bit_width <= 32:
                ports.append(f"    input wire [{param.bit_width-1}:0] {param.name}")
            else:
                # Large parameters use shared bus
                ports.append(f"    input wire [31:0] {param.name}_addr")
                ports.append(f"    input wire [31:0] {param.name}_data")
        
        # Minimal output interface
        if func.return_var and func.return_var.bit_width <= 32:
            ports.append(f"    output reg [{func.return_var.bit_width-1}:0] {func.return_var.name}")
        else:
            ports.append("    output reg [31:0] result")
        
        # Control signals
        ports.append("    output reg valid")
        ports.append("    output reg done")
        
        code.append(f"module {func.name} (")
        code.append(",\n".join(ports))
        code.append(");")
        code.append("")
        
        return code
    
    def _generate_area_optimized_signals(self, func: IRFunction) -> List[str]:
        """Generate area-optimized signal declarations."""
        code = []
        code.append("// Area-optimized signal declarations")
        
        # Shared temporary registers
        code.append("reg [31:0] shared_temp_reg;")
        code.append("reg [31:0] shared_addr_reg;")
        
        # Minimal local variables - use shared registers when possible
        essential_vars = self._identify_essential_variables(func)
        for var_name in essential_vars:
            if var_name in func.local_vars:
                var = func.local_vars[var_name]
                if var.bit_width > 1:
                    code.append(f"reg [{var.bit_width-1}:0] {var_name};")
                else:
                    code.append(f"reg {var_name};")
        
        # Resource sharing signals
        code.append("reg [2:0] resource_select;")
        code.append("reg resource_enable;")
        code.append("")
        
        return code
    
    def _generate_area_optimized_fsm(self, func: IRFunction) -> List[str]:
        """Generate compact state machine for area optimization."""
        code = []
        code.append("// Compact FSM for area optimization")
        
        # Minimal state encoding
        num_states = max(3, len(func.blocks) + 2)  # IDLE, blocks, DONE
        state_bits = (num_states - 1).bit_length()
        
        code.append(f"reg [{state_bits-1}:0] state;")
        code.append(f"reg [{state_bits-1}:0] next_state;")
        code.append("")
        
        # Compact state encoding
        code.append("// Compact state encoding")
        code.append("localparam IDLE = 0;")
        code.append("localparam COMPUTE = 1;")
        code.append("localparam DONE = 2;")
        
        # Add block states only if needed
        if len(func.blocks) > 1:
            for i, block in enumerate(func.blocks):
                code.append(f"localparam {block.name.upper()} = {i + 3};")
        
        code.append("")
        
        # State register
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n)")
        code.append("        state <= IDLE;")
        code.append("    else")
        code.append("        state <= next_state;")
        code.append("end")
        code.append("")
        
        # Next state logic - optimized for area
        code.append("always @(*) begin")
        code.append("    next_state = state;")
        code.append("    case (state)")
        code.append("        IDLE: next_state = COMPUTE;")
        code.append("        COMPUTE: next_state = DONE;")
        code.append("        DONE: next_state = IDLE;")
        code.append("        default: next_state = IDLE;")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_area_optimized_datapath(self, func: IRFunction) -> List[str]:
        """Generate shared datapath for area optimization."""
        code = []
        code.append("// Shared datapath for area optimization")
        
        # Shared ALU with multiplexed inputs
        code.append("reg [31:0] alu_input_a;")
        code.append("reg [31:0] alu_input_b;")
        code.append("reg [3:0] alu_operation;")
        code.append("reg [31:0] alu_result;")
        code.append("")
        
        # Shared ALU implementation
        code.append("always @(*) begin")
        code.append("    case (alu_operation)")
        code.append("        4'b0000: alu_result = alu_input_a + alu_input_b;")
        code.append("        4'b0001: alu_result = alu_input_a - alu_input_b;")
        code.append("        4'b0010: alu_result = alu_input_a * alu_input_b;")
        code.append("        4'b0011: alu_result = alu_input_a & alu_input_b;")
        code.append("        4'b0100: alu_result = alu_input_a | alu_input_b;")
        code.append("        4'b0101: alu_result = alu_input_a ^ alu_input_b;")
        code.append("        4'b0110: alu_result = alu_input_a << alu_input_b[4:0];")
        code.append("        4'b0111: alu_result = alu_input_a >> alu_input_b[4:0];")
        code.append("        default: alu_result = alu_input_a;")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        # Input multiplexers for resource sharing
        code.append("always @(*) begin")
        code.append("    case (resource_select)")
        code.append("        3'b000: begin")
        code.append("            alu_input_a = shared_temp_reg;")
        code.append("            alu_input_b = 32'h1;")
        code.append("            alu_operation = 4'b0000;")
        code.append("        end")
        code.append("        default: begin")
        code.append("            alu_input_a = 32'h0;")
        code.append("            alu_input_b = 32'h0;")
        code.append("            alu_operation = 4'b0000;")
        code.append("        end")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_area_optimized_memory(self, func: IRFunction) -> List[str]:
        """Generate area-optimized memory subsystem."""
        code = []
        
        # Check if memory is needed
        memory_vars = [(name, var) for name, var in func.local_vars.items() 
                      if var.data_type == "ARRAY" or var.memory_size > 1]
        
        if not memory_vars:
            return code
        
        code.append("// Area-optimized shared memory")
        
        # Single shared memory with arbitration
        total_memory_size = sum(var.memory_size for _, var in memory_vars)
        addr_bits = max(10, (total_memory_size - 1).bit_length())
        
        code.append(f"reg [31:0] shared_memory [0:{total_memory_size-1}];")
        code.append(f"reg [{addr_bits-1}:0] mem_addr;")
        code.append("reg [31:0] mem_data_in;")
        code.append("reg [31:0] mem_data_out;")
        code.append("reg mem_write_enable;")
        code.append("")
        
        # Memory access logic
        code.append("always @(posedge clk) begin")
        code.append("    if (mem_write_enable)")
        code.append("        shared_memory[mem_addr] <= mem_data_in;")
        code.append("    mem_data_out <= shared_memory[mem_addr];")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_area_optimized_clock_gating(self, func: IRFunction) -> List[str]:
        """Generate clock gating for area optimization."""
        code = []
        code.append("// Clock gating for area optimization")
        
        # Simple clock gating based on state
        code.append("wire gated_clk;")
        code.append("assign gated_clk = clk & (state == COMPUTE);")
        code.append("")
        
        return code
    
    # Performance-optimized generation methods
    def _generate_performance_optimized_header(self, func: IRFunction) -> List[str]:
        """Generate performance-optimized module header."""
        code = []
        
        # Wide parallel interfaces
        ports = []
        ports.append("    input wire clk")
        ports.append("    input wire rst_n")
        
        # Parallel input ports for performance
        for i, param in enumerate(func.parameters):
            ports.append(f"    input wire [{param.bit_width-1}:0] {param.name}")
            # Add ready/valid signals for high-performance interface
            ports.append(f"    input wire {param.name}_valid")
            ports.append(f"    output wire {param.name}_ready")
        
        # Parallel output interface
        if func.return_var:
            ports.append(f"    output reg [{func.return_var.bit_width-1}:0] {func.return_var.name}")
        else:
            ports.append("    output reg [31:0] result")
        
        # High-performance control signals
        ports.append("    output reg result_valid")
        ports.append("    input wire result_ready")
        ports.append("    output reg done")
        
        code.append(f"module {func.name} (")
        code.append(",\n".join(ports))
        code.append(");")
        code.append("")
        
        return code
    
    def _generate_performance_optimized_signals(self, func: IRFunction) -> List[str]:
        """Generate performance-optimized signal declarations."""
        code = []
        code.append("// Performance-optimized signal declarations")
        
        # Parallel execution units
        num_parallel_units = min(4, len(self.netlist_resources))
        for i in range(num_parallel_units):
            code.append(f"reg [31:0] alu_{i}_input_a;")
            code.append(f"reg [31:0] alu_{i}_input_b;")
            code.append(f"reg [31:0] alu_{i}_result;")
            code.append(f"reg alu_{i}_enable;")
        
        # Pipeline registers
        pipeline_stages = min(3, self.optimization_context.pipeline_depth)
        for stage in range(pipeline_stages):
            code.append(f"reg [31:0] pipeline_stage_{stage}_data;")
            code.append(f"reg pipeline_stage_{stage}_valid;")
        
        # Local variables with parallel access
        for var_name, var in func.local_vars.items():
            if var.bit_width > 1:
                code.append(f"reg [{var.bit_width-1}:0] {var_name};")
            else:
                code.append(f"reg {var_name};")
        
        code.append("")
        return code
    
    def _generate_performance_optimized_fsm(self, func: IRFunction) -> List[str]:
        """Generate performance-optimized FSM."""
        code = []
        code.append("// Performance-optimized parallel FSM")
        
        # Parallel state machines or pipelined control
        code.append("reg [2:0] main_state;")
        code.append("reg [2:0] next_main_state;")
        code.append("reg [1:0] pipeline_state;")
        code.append("")
        
        # State definitions
        code.append("localparam IDLE = 3'b000;")
        code.append("localparam SETUP = 3'b001;")
        code.append("localparam EXECUTE = 3'b010;")
        code.append("localparam PIPELINE = 3'b011;")
        code.append("localparam DONE = 3'b100;")
        code.append("")
        
        # Main state machine
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        code.append("        main_state <= IDLE;")
        code.append("        pipeline_state <= 2'b00;")
        code.append("    end else begin")
        code.append("        main_state <= next_main_state;")
        code.append("        if (main_state == PIPELINE)")
        code.append("            pipeline_state <= pipeline_state + 1;")
        code.append("    end")
        code.append("end")
        code.append("")
        
        # Next state logic
        code.append("always @(*) begin")
        code.append("    next_main_state = main_state;")
        code.append("    case (main_state)")
        code.append("        IDLE: next_main_state = SETUP;")
        code.append("        SETUP: next_main_state = EXECUTE;")
        code.append("        EXECUTE: next_main_state = PIPELINE;")
        code.append("        PIPELINE: begin")
        code.append("            if (pipeline_state == 2'b11)")
        code.append("                next_main_state = DONE;")
        code.append("        end")
        code.append("        DONE: next_main_state = IDLE;")
        code.append("        default: next_main_state = IDLE;")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_performance_optimized_datapath(self, func: IRFunction) -> List[str]:
        """Generate parallel datapath for performance optimization."""
        code = []
        code.append("// Parallel datapath for performance optimization")
        
        # Parallel ALU units
        num_alus = min(4, len([r for r in self.netlist_resources if 'ALU' in r.type]))
        for i in range(num_alus):
            code.append(f"// ALU {i}")
            code.append(f"always @(*) begin")
            code.append(f"    if (alu_{i}_enable)")
            code.append(f"        alu_{i}_result = alu_{i}_input_a + alu_{i}_input_b;")
            code.append(f"    else")
            code.append(f"        alu_{i}_result = 32'h0;")
            code.append(f"end")
            code.append("")
        
        # Parallel execution control
        code.append("always @(*) begin")
        code.append("    case (main_state)")
        code.append("        EXECUTE: begin")
        for i in range(num_alus):
            code.append(f"            alu_{i}_enable = 1'b1;")
        code.append("        end")
        code.append("        default: begin")
        for i in range(num_alus):
            code.append(f"            alu_{i}_enable = 1'b0;")
        code.append("        end")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_performance_optimized_memory(self, func: IRFunction) -> List[str]:
        """Generate high-bandwidth memory subsystem."""
        code = []
        
        # Check for memory requirements
        memory_vars = [(name, var) for name, var in func.local_vars.items() 
                      if var.data_type == "ARRAY" or var.memory_size > 1]
        
        if not memory_vars:
            return code
        
        code.append("// High-bandwidth memory subsystem")
        
        # Multiple memory banks for parallel access
        num_banks = min(4, len(memory_vars))
        for bank in range(num_banks):
            bank_size = max(256, sum(var.memory_size for _, var in memory_vars) // num_banks)
            addr_bits = (bank_size - 1).bit_length()
            
            code.append(f"reg [31:0] memory_bank_{bank} [0:{bank_size-1}];")
            code.append(f"reg [{addr_bits-1}:0] bank_{bank}_addr;")
            code.append(f"reg [31:0] bank_{bank}_data_in;")
            code.append(f"reg [31:0] bank_{bank}_data_out;")
            code.append(f"reg bank_{bank}_write_enable;")
            code.append("")
            
            # Bank access logic
            code.append(f"always @(posedge clk) begin")
            code.append(f"    if (bank_{bank}_write_enable)")
            code.append(f"        memory_bank_{bank}[bank_{bank}_addr] <= bank_{bank}_data_in;")
            code.append(f"    bank_{bank}_data_out <= memory_bank_{bank}[bank_{bank}_addr];")
            code.append(f"end")
            code.append("")
        
        return code
    
    def _generate_performance_optimized_pipeline(self, func: IRFunction) -> List[str]:
        """Generate pipeline registers for high frequency."""
        code = []
        code.append("// Pipeline registers for high frequency operation")
        
        pipeline_stages = min(3, self.optimization_context.pipeline_depth)
        
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        for stage in range(pipeline_stages):
            code.append(f"        pipeline_stage_{stage}_data <= 32'h0;")
            code.append(f"        pipeline_stage_{stage}_valid <= 1'b0;")
        code.append("    end else begin")
        
        # Pipeline data flow
        if pipeline_stages > 0:
            code.append("        pipeline_stage_0_data <= shared_temp_reg;")
            code.append("        pipeline_stage_0_valid <= (main_state == EXECUTE);")
        
        for stage in range(1, pipeline_stages):
            code.append(f"        pipeline_stage_{stage}_data <= pipeline_stage_{stage-1}_data;")
            code.append(f"        pipeline_stage_{stage}_valid <= pipeline_stage_{stage-1}_valid;")
        
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    # Power-optimized generation methods
    def _generate_power_optimized_header(self, func: IRFunction) -> List[str]:
        """Generate power-optimized module header."""
        code = []
        
        # Power management interface
        ports = []
        ports.append("    input wire clk")
        ports.append("    input wire rst_n")
        
        # Power management signals
        ports.append("    input wire power_enable")
        ports.append("    input wire sleep_mode")
        ports.append("    output wire power_ack")
        
        # Standard function interface
        for param in func.parameters:
            ports.append(f"    input wire [{param.bit_width-1}:0] {param.name}")
        
        if func.return_var:
            ports.append(f"    output reg [{func.return_var.bit_width-1}:0] {func.return_var.name}")
        else:
            ports.append("    output reg [31:0] result")
        
        ports.append("    output reg valid")
        ports.append("    output reg done")
        
        code.append(f"module {func.name} (")
        code.append(",\n".join(ports))
        code.append(");")
        code.append("")
        
        return code
    
    def _generate_power_optimized_signals(self, func: IRFunction) -> List[str]:
        """Generate power-optimized signal declarations."""
        code = []
        code.append("// Power-optimized signal declarations")
        
        # Power management signals
        code.append("reg power_state;")
        code.append("reg activity_monitor;")
        code.append("reg [3:0] idle_counter;")
        code.append("")
        
        # Gated clock signals
        code.append("wire gated_clk_datapath;")
        code.append("wire gated_clk_memory;")
        code.append("wire gated_clk_control;")
        code.append("")
        
        # Minimal active signals
        for var_name, var in func.local_vars.items():
            if var.bit_width > 1:
                code.append(f"reg [{var.bit_width-1}:0] {var_name};")
            else:
                code.append(f"reg {var_name};")
        
        code.append("")
        return code
    
    def _generate_power_optimized_fsm(self, func: IRFunction) -> List[str]:
        """Generate power-aware FSM with sleep states."""
        code = []
        code.append("// Power-aware FSM with sleep states")
        
        code.append("reg [2:0] power_state_reg;")
        code.append("reg [2:0] next_power_state;")
        code.append("")
        
        # Power-aware state definitions
        code.append("localparam PWR_SLEEP = 3'b000;")
        code.append("localparam PWR_WAKEUP = 3'b001;")
        code.append("localparam PWR_IDLE = 3'b010;")
        code.append("localparam PWR_ACTIVE = 3'b011;")
        code.append("localparam PWR_COMPUTE = 3'b100;")
        code.append("localparam PWR_DONE = 3'b101;")
        code.append("")
        
        # Power state machine
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        code.append("        power_state_reg <= PWR_SLEEP;")
        code.append("        idle_counter <= 4'h0;")
        code.append("    end else begin")
        code.append("        power_state_reg <= next_power_state;")
        code.append("        if (power_state_reg == PWR_IDLE)")
        code.append("            idle_counter <= idle_counter + 1;")
        code.append("        else")
        code.append("            idle_counter <= 4'h0;")
        code.append("    end")
        code.append("end")
        code.append("")
        
        # Power-aware next state logic
        code.append("always @(*) begin")
        code.append("    next_power_state = power_state_reg;")
        code.append("    case (power_state_reg)")
        code.append("        PWR_SLEEP: begin")
        code.append("            if (power_enable)")
        code.append("                next_power_state = PWR_WAKEUP;")
        code.append("        end")
        code.append("        PWR_WAKEUP: next_power_state = PWR_IDLE;")
        code.append("        PWR_IDLE: begin")
        code.append("            if (sleep_mode || idle_counter == 4'hF)")
        code.append("                next_power_state = PWR_SLEEP;")
        code.append("            else if (power_enable)")
        code.append("                next_power_state = PWR_ACTIVE;")
        code.append("        end")
        code.append("        PWR_ACTIVE: next_power_state = PWR_COMPUTE;")
        code.append("        PWR_COMPUTE: next_power_state = PWR_DONE;")
        code.append("        PWR_DONE: next_power_state = PWR_IDLE;")
        code.append("        default: next_power_state = PWR_SLEEP;")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_power_optimized_datapath(self, func: IRFunction) -> List[str]:
        """Generate clock-gated datapath for power optimization."""
        code = []
        code.append("// Clock-gated datapath for power optimization")
        
        # Power-gated ALU
        code.append("reg [31:0] power_gated_alu_input_a;")
        code.append("reg [31:0] power_gated_alu_input_b;")
        code.append("reg [31:0] power_gated_alu_result;")
        code.append("reg power_gated_alu_enable;")
        code.append("")
        
        # Power-aware ALU implementation
        code.append("always @(posedge gated_clk_datapath or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        code.append("        power_gated_alu_result <= 32'h0;")
        code.append("    end else if (power_gated_alu_enable) begin")
        code.append("        power_gated_alu_result <= power_gated_alu_input_a + power_gated_alu_input_b;")
        code.append("    end")
        code.append("end")
        code.append("")
        
        # Activity monitoring
        code.append("always @(posedge clk) begin")
        code.append("    activity_monitor <= power_gated_alu_enable || (power_state_reg == PWR_COMPUTE);")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_power_optimized_memory(self, func: IRFunction) -> List[str]:
        """Generate power-efficient memory subsystem."""
        code = []
        
        # Check for memory requirements
        memory_vars = [(name, var) for name, var in func.local_vars.items() 
                      if var.data_type == "ARRAY" or var.memory_size > 1]
        
        if not memory_vars:
            return code
        
        code.append("// Power-efficient memory subsystem")
        
        # Power-gated memory
        total_memory_size = sum(var.memory_size for _, var in memory_vars)
        addr_bits = max(8, (total_memory_size - 1).bit_length())
        
        code.append(f"reg [31:0] power_gated_memory [0:{total_memory_size-1}];")
        code.append(f"reg [{addr_bits-1}:0] power_gated_mem_addr;")
        code.append("reg [31:0] power_gated_mem_data_in;")
        code.append("reg [31:0] power_gated_mem_data_out;")
        code.append("reg power_gated_mem_enable;")
        code.append("")
        
        # Power-aware memory access
        code.append("always @(posedge gated_clk_memory) begin")
        code.append("    if (power_gated_mem_enable) begin")
        code.append("        power_gated_memory[power_gated_mem_addr] <= power_gated_mem_data_in;")
        code.append("        power_gated_mem_data_out <= power_gated_memory[power_gated_mem_addr];")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_power_optimized_power_management(self, func: IRFunction) -> List[str]:
        """Generate extensive power management logic."""
        code = []
        code.append("// Power management and clock gating")
        
        # Clock gating cells
        code.append("// Clock gating for different domains")
        code.append("assign gated_clk_datapath = clk & (power_state_reg == PWR_COMPUTE) & power_enable;")
        code.append("assign gated_clk_memory = clk & (power_state_reg >= PWR_ACTIVE) & power_enable;")
        code.append("assign gated_clk_control = clk & (power_state_reg != PWR_SLEEP);")
        code.append("")
        
        # Power acknowledgment
        code.append("assign power_ack = (power_state_reg == PWR_ACTIVE) || (power_state_reg == PWR_COMPUTE);")
        code.append("")
        
        # Output control based on power state
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        code.append("        valid <= 1'b0;")
        code.append("        done <= 1'b0;")
        code.append("    end else begin")
        code.append("        case (power_state_reg)")
        code.append("            PWR_COMPUTE: begin")
        code.append("                valid <= 1'b1;")
        code.append("                done <= 1'b0;")
        code.append("            end")
        code.append("            PWR_DONE: begin")
        code.append("                valid <= 1'b0;")
        code.append("                done <= 1'b1;")
        code.append("            end")
        code.append("            default: begin")
        code.append("                valid <= 1'b0;")
        code.append("                done <= 1'b0;")
        code.append("            end")
        code.append("        endcase")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    # Balanced generation methods
    def _generate_standard_header(self, func: IRFunction) -> List[str]:
        """Generate standard module header."""
        return self._generate_port_list(func)
    
    def _generate_balanced_signals(self, func: IRFunction) -> List[str]:
        """Generate balanced signal declarations."""
        return self._generate_signal_declarations(func)
    
    def _generate_balanced_fsm(self, func: IRFunction) -> List[str]:
        """Generate balanced FSM."""
        if self._needs_state_machine(func):
            return self._generate_state_machine_logic(func)
        return []
    
    def _generate_balanced_datapath(self, func: IRFunction) -> List[str]:
        """Generate balanced datapath."""
        return self._generate_datapath_logic(func)
    
    def _generate_balanced_memory(self, func: IRFunction) -> List[str]:
        """Generate balanced memory subsystem."""
        return self._generate_memory_components(func)
    
    def _generate_balanced_clock_gating(self, func: IRFunction) -> List[str]:
        """Generate selective clock gating."""
        code = []
        code.append("// Selective clock gating for balanced optimization")
        code.append("wire selective_gated_clk;")
        code.append("assign selective_gated_clk = clk & valid;")
        code.append("")
        return code
    
    # Helper methods
    def _identify_essential_variables(self, func: IRFunction) -> List[str]:
        """Identify essential variables that cannot be shared."""
        essential = []
        
        # Parameters and return variables are essential
        for param in func.parameters:
            essential.append(param.name)
        
        if func.return_var:
            essential.append(func.return_var.name)
        
        # Variables used in multiple blocks are essential
        var_usage = {}
        for block in func.blocks:
            for instruction in block.instructions:
                for operation in instruction.operations:
                    if operation.result and hasattr(operation.result, 'name'):
                        var_name = operation.result.name
                        if var_name not in var_usage:
                            var_usage[var_name] = 0
                        var_usage[var_name] += 1
        
        # Variables used more than once are essential
        for var_name, usage_count in var_usage.items():
            if usage_count > 1 and var_name in func.local_vars:
                essential.append(var_name)
        
        return essential
    
    def _add_resource_info_to_module(self, module: NetlistModule, func: IRFunction) -> None:
        """Add resource information to the module."""
        # Add allocated resources to the module
        for resource in self.netlist_resources:
            module.add_resource(resource)
        
        # Set module properties based on optimization context
        if self.optimization_context:
            module.latency = max(1, len(func.blocks))
            module.clock_frequency_mhz = self.optimization_context.target_frequency
            
            # Calculate area and power from resources
            total_area = sum(resource.area for resource in self.netlist_resources)
            total_power = sum(resource.power for resource in self.netlist_resources)
            
            module.area = total_area
            module.power = total_power
        
        logger.info(f"Added {len(self.netlist_resources)} resources to module {module.name}") 