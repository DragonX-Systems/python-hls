"""
Performance optimization patterns for Verilog generation.
Focus on parallel execution, pipelining, and maximum throughput.
"""

import logging
from typing import Dict, List, Optional, Set, Union, Any, Tuple
from dataclasses import dataclass

from ...ir.ir_nodes import (
    IRFunction, IRBlock, IRInstruction, IRVariable, IRConstant, 
    IROperation, OperationType, DataType
)
from ...netlist import NetlistResource

logger = logging.getLogger(__name__)

@dataclass
class ParallelExecutionGroup:
    """Represents a group of operations that can execute in parallel."""
    operations: List[IROperation]
    execution_cycle: int
    resource_requirements: Dict[str, int]
    dependencies: List[int]  # Indices of dependent groups

@dataclass
class PipelineStage:
    """Represents a pipeline stage."""
    stage_id: int
    operations: List[IROperation]
    latency: int
    resource_usage: Dict[str, int]

class PerformancePatternGenerator:
    """Generator for performance-optimized Verilog patterns."""
    
    def __init__(self, tech_node: int = 45, target_frequency: float = 100.0):
        """
        Initialize performance pattern generator.
        
        Args:
            tech_node: Technology node for performance optimization
            target_frequency: Target frequency in MHz
        """
        self.tech_node = tech_node
        self.target_frequency = target_frequency
        self.parallel_groups = []
        self.pipeline_stages = []
        
    def generate_parallel_datapath(self, func: IRFunction, operations: List[IROperation], 
                                 available_resources: Dict[str, int]) -> List[str]:
        """
        Generate performance-optimized datapath with parallel execution.
        
        Args:
            func: Function to generate datapath for
            operations: List of operations to implement
            available_resources: Available resources for parallel execution
            
        Returns:
            List of Verilog code lines
        """
        code = []
        code.append("// Performance-optimized parallel datapath")
        
        # Analyze operations for parallel execution
        parallel_groups = self._analyze_parallel_opportunities(operations, available_resources)
        
        # Generate parallel execution units
        for group in parallel_groups:
            code.extend(self._generate_parallel_execution_unit(group))
        
        # Generate parallel control logic
        code.extend(self._generate_parallel_control_logic(parallel_groups))
        
        # Generate result collection logic
        code.extend(self._generate_result_collection_logic(parallel_groups))
        
        return code
    
    def generate_pipelined_fsm(self, func: IRFunction, pipeline_depth: int = 3) -> List[str]:
        """
        Generate pipelined control logic for high-frequency operation.
        
        Args:
            func: Function to generate FSM for
            pipeline_depth: Number of pipeline stages
            
        Returns:
            List of Verilog code lines
        """
        code = []
        code.append("// Pipelined FSM for high-frequency operation")
        
        # Generate pipeline stages
        pipeline_stages = self._create_pipeline_stages(func, pipeline_depth)
        
        # Generate pipeline registers
        code.extend(self._generate_pipeline_registers(pipeline_stages))
        
        # Generate pipeline control logic
        code.extend(self._generate_pipeline_control_logic(pipeline_stages))
        
        # Generate pipeline stall and flush logic
        code.extend(self._generate_pipeline_stall_flush_logic(pipeline_stages))
        
        return code
    
    def generate_high_bandwidth_memory(self, func: IRFunction, memory_vars: List[Tuple[str, IRVariable]],
                                     num_banks: int = 4) -> List[str]:
        """
        Generate high-bandwidth memory subsystem with multiple banks.
        
        Args:
            func: Function containing memory variables
            memory_vars: List of (name, variable) tuples for memory variables
            num_banks: Number of memory banks for parallel access
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if not memory_vars:
            return code
        
        code.append("// High-bandwidth memory subsystem")
        
        # Generate memory banks
        for bank_id in range(num_banks):
            code.extend(self._generate_memory_bank(bank_id, memory_vars, num_banks))
        
        # Generate memory bank arbitration
        code.extend(self._generate_memory_bank_arbitration(num_banks))
        
        # Generate memory access scheduling
        code.extend(self._generate_memory_access_scheduling(memory_vars, num_banks))
        
        return code
    
    def generate_unroll_optimized_loop(self, func: IRFunction, loop_block: IRBlock, 
                                     unroll_factor: int) -> List[str]:
        """
        Generate loop structure optimized for unrolling.
        
        Args:
            func: Function containing the loop
            loop_block: Loop block to optimize
            unroll_factor: Loop unrolling factor
            
        Returns:
            List of Verilog code lines
        """
        code = []
        code.append(f"// Unroll-optimized loop (factor: {unroll_factor})")
        
        # Generate parallel loop iterations
        code.extend(self._generate_parallel_loop_iterations(loop_block, unroll_factor))
        
        # Generate unroll control logic
        code.extend(self._generate_unroll_control_logic(loop_block, unroll_factor))
        
        # Generate iteration management
        code.extend(self._generate_iteration_management(loop_block, unroll_factor))
        
        return code
    
    def generate_speculative_execution(self, func: IRFunction, branch_blocks: List[IRBlock]) -> List[str]:
        """
        Generate speculative execution logic for branches.
        
        Args:
            func: Function containing branches
            branch_blocks: List of blocks with branch conditions
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if not branch_blocks:
            return code
        
        code.append("// Speculative execution for branches")
        
        # Generate branch prediction logic
        code.extend(self._generate_branch_prediction_logic(branch_blocks))
        
        # Generate speculative execution units
        code.extend(self._generate_speculative_execution_units(branch_blocks))
        
        # Generate speculation resolution logic
        code.extend(self._generate_speculation_resolution_logic(branch_blocks))
        
        return code
    
    def generate_wide_datapath(self, func: IRFunction, operations: List[IROperation], 
                             data_width: int = 64) -> List[str]:
        """
        Generate wide datapath for higher throughput.
        
        Args:
            func: Function to generate datapath for
            operations: List of operations to implement
            data_width: Data width for wide operations
            
        Returns:
            List of Verilog code lines
        """
        code = []
        code.append(f"// Wide datapath ({data_width}-bit)")
        
        # Generate wide execution units
        code.extend(self._generate_wide_execution_units(operations, data_width))
        
        # Generate wide data routing
        code.extend(self._generate_wide_data_routing(operations, data_width))
        
        # Generate wide result handling
        code.extend(self._generate_wide_result_handling(operations, data_width))
        
        return code
    
    def _analyze_parallel_opportunities(self, operations: List[IROperation], 
                                      available_resources: Dict[str, int]) -> List[ParallelExecutionGroup]:
        """Analyze operations for parallel execution opportunities."""
        parallel_groups = []
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(operations)
        
        # Schedule operations into parallel groups
        scheduled_ops = set()
        cycle = 0
        
        while len(scheduled_ops) < len(operations):
            # Find operations ready for execution
            ready_ops = []
            for i, op in enumerate(operations):
                if i not in scheduled_ops and self._is_operation_ready(i, dependency_graph, scheduled_ops):
                    ready_ops.append((i, op))
            
            if not ready_ops:
                break
            
            # Group operations that can execute in parallel
            parallel_ops = []
            resource_usage = {}
            
            for i, op in ready_ops:
                resource_type = self._get_resource_type_for_operation(op)
                required_count = resource_usage.get(resource_type, 0) + 1
                
                if required_count <= available_resources.get(resource_type, 1):
                    parallel_ops.append(op)
                    resource_usage[resource_type] = required_count
                    scheduled_ops.add(i)
            
            if parallel_ops:
                group = ParallelExecutionGroup(
                    operations=parallel_ops,
                    execution_cycle=cycle,
                    resource_requirements=resource_usage,
                    dependencies=[]
                )
                parallel_groups.append(group)
            
            cycle += 1
        
        return parallel_groups
    
    def _generate_parallel_execution_unit(self, group: ParallelExecutionGroup) -> List[str]:
        """Generate parallel execution unit for a group of operations."""
        code = []
        
        group_id = group.execution_cycle
        code.append(f"// Parallel execution unit {group_id}")
        
        # Generate input registers
        for i, op in enumerate(group.operations):
            code.append(f"reg [31:0] exec_unit_{group_id}_op_{i}_input_a;")
            code.append(f"reg [31:0] exec_unit_{group_id}_op_{i}_input_b;")
            code.append(f"reg [31:0] exec_unit_{group_id}_op_{i}_result;")
            code.append(f"reg exec_unit_{group_id}_op_{i}_valid;")
        
        code.append("")
        
        # Generate execution logic
        for i, op in enumerate(group.operations):
            code.extend(self._generate_operation_execution_logic(group_id, i, op))
        
        return code
    
    def _generate_operation_execution_logic(self, group_id: int, op_id: int, op: IROperation) -> List[str]:
        """Generate execution logic for a specific operation."""
        code = []
        
        unit_prefix = f"exec_unit_{group_id}_op_{op_id}"
        
        if op.op_type == OperationType.ADD:
            code.append(f"always @(*) begin")
            code.append(f"    {unit_prefix}_result = {unit_prefix}_input_a + {unit_prefix}_input_b;")
            code.append(f"end")
        elif op.op_type == OperationType.MUL:
            code.append(f"always @(posedge clk) begin")
            code.append(f"    if ({unit_prefix}_valid)")
            code.append(f"        {unit_prefix}_result <= {unit_prefix}_input_a * {unit_prefix}_input_b;")
            code.append(f"end")
        elif op.op_type == OperationType.SUB:
            code.append(f"always @(*) begin")
            code.append(f"    {unit_prefix}_result = {unit_prefix}_input_a - {unit_prefix}_input_b;")
            code.append(f"end")
        else:
            # Generic ALU operation
            code.append(f"always @(*) begin")
            code.append(f"    {unit_prefix}_result = {unit_prefix}_input_a + {unit_prefix}_input_b;")
            code.append(f"end")
        
        code.append("")
        return code
    
    def _generate_parallel_control_logic(self, parallel_groups: List[ParallelExecutionGroup]) -> List[str]:
        """Generate control logic for parallel execution."""
        code = []
        
        if not parallel_groups:
            return code
        
        code.append("// Parallel execution control logic")
        
        # Generate execution cycle counter
        max_cycles = max(group.execution_cycle for group in parallel_groups) + 1
        cycle_bits = max(1, (max_cycles - 1).bit_length())
        
        code.append(f"reg [{cycle_bits-1}:0] execution_cycle;")
        code.append(f"reg execution_active;")
        code.append("")
        
        # Generate cycle control
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        code.append("        execution_cycle <= 0;")
        code.append("        execution_active <= 1'b0;")
        code.append("    end else if (execution_active) begin")
        code.append(f"        if (execution_cycle < {max_cycles - 1})")
        code.append("            execution_cycle <= execution_cycle + 1;")
        code.append("        else begin")
        code.append("            execution_cycle <= 0;")
        code.append("            execution_active <= 1'b0;")
        code.append("        end")
        code.append("    end")
        code.append("end")
        code.append("")
        
        # Generate enable signals for each group
        for group in parallel_groups:
            code.append(f"wire exec_group_{group.execution_cycle}_enable;")
            code.append(f"assign exec_group_{group.execution_cycle}_enable = ")
            code.append(f"    execution_active && (execution_cycle == {group.execution_cycle});")
        
        code.append("")
        
        return code
    
    def _generate_result_collection_logic(self, parallel_groups: List[ParallelExecutionGroup]) -> List[str]:
        """Generate logic to collect results from parallel execution units."""
        code = []
        
        if not parallel_groups:
            return code
        
        code.append("// Result collection logic")
        
        # Generate result registers
        total_ops = sum(len(group.operations) for group in parallel_groups)
        code.append(f"reg [31:0] collected_results [0:{total_ops-1}];")
        code.append(f"reg [{total_ops-1}:0] result_valid;")
        code.append("")
        
        # Generate result collection
        result_index = 0
        code.append("always @(posedge clk) begin")
        
        for group in parallel_groups:
            code.append(f"    if (exec_group_{group.execution_cycle}_enable) begin")
            
            for i, op in enumerate(group.operations):
                code.append(f"        collected_results[{result_index}] <= exec_unit_{group.execution_cycle}_op_{i}_result;")
                code.append(f"        result_valid[{result_index}] <= exec_unit_{group.execution_cycle}_op_{i}_valid;")
                result_index += 1
            
            code.append("    end")
        
        code.append("end")
        code.append("")
        
        return code
    
    def _create_pipeline_stages(self, func: IRFunction, pipeline_depth: int) -> List[PipelineStage]:
        """Create pipeline stages from function blocks."""
        stages = []
        
        # Distribute operations across pipeline stages
        all_operations = []
        for block in func.blocks:
            for instruction in block.instructions:
                all_operations.extend(instruction.operations)
        
        ops_per_stage = max(1, len(all_operations) // pipeline_depth)
        
        for stage_id in range(pipeline_depth):
            start_idx = stage_id * ops_per_stage
            end_idx = min((stage_id + 1) * ops_per_stage, len(all_operations))
            
            stage_ops = all_operations[start_idx:end_idx]
            
            # Calculate resource usage for this stage
            resource_usage = {}
            for op in stage_ops:
                resource_type = self._get_resource_type_for_operation(op)
                resource_usage[resource_type] = resource_usage.get(resource_type, 0) + 1
            
            stage = PipelineStage(
                stage_id=stage_id,
                operations=stage_ops,
                latency=1,  # Assume 1 cycle per stage
                resource_usage=resource_usage
            )
            stages.append(stage)
        
        return stages
    
    def _generate_pipeline_registers(self, pipeline_stages: List[PipelineStage]) -> List[str]:
        """Generate pipeline registers."""
        code = []
        
        code.append("// Pipeline registers")
        
        for stage in pipeline_stages:
            code.append(f"// Stage {stage.stage_id} registers")
            code.append(f"reg [31:0] pipeline_stage_{stage.stage_id}_data;")
            code.append(f"reg pipeline_stage_{stage.stage_id}_valid;")
            code.append(f"reg pipeline_stage_{stage.stage_id}_ready;")
        
        code.append("")
        
        # Generate pipeline register logic
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        
        for stage in pipeline_stages:
            code.append(f"        pipeline_stage_{stage.stage_id}_data <= 32'h0;")
            code.append(f"        pipeline_stage_{stage.stage_id}_valid <= 1'b0;")
        
        code.append("    end else begin")
        
        # Pipeline data flow
        for i, stage in enumerate(pipeline_stages):
            if i == 0:
                code.append(f"        pipeline_stage_{stage.stage_id}_data <= input_data;")
                code.append(f"        pipeline_stage_{stage.stage_id}_valid <= input_valid;")
            else:
                prev_stage = pipeline_stages[i-1]
                code.append(f"        pipeline_stage_{stage.stage_id}_data <= pipeline_stage_{prev_stage.stage_id}_data;")
                code.append(f"        pipeline_stage_{stage.stage_id}_valid <= pipeline_stage_{prev_stage.stage_id}_valid;")
        
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_pipeline_control_logic(self, pipeline_stages: List[PipelineStage]) -> List[str]:
        """Generate pipeline control logic."""
        code = []
        
        code.append("// Pipeline control logic")
        
        # Generate pipeline enable signals
        for stage in pipeline_stages:
            code.append(f"wire pipeline_stage_{stage.stage_id}_enable;")
        
        code.append("")
        
        # Generate enable logic
        for i, stage in enumerate(pipeline_stages):
            if i == 0:
                code.append(f"assign pipeline_stage_{stage.stage_id}_enable = input_valid;")
            else:
                prev_stage = pipeline_stages[i-1]
                code.append(f"assign pipeline_stage_{stage.stage_id}_enable = ")
                code.append(f"    pipeline_stage_{prev_stage.stage_id}_valid && ")
                code.append(f"    pipeline_stage_{stage.stage_id}_ready;")
        
        code.append("")
        
        return code
    
    def _generate_pipeline_stall_flush_logic(self, pipeline_stages: List[PipelineStage]) -> List[str]:
        """Generate pipeline stall and flush logic."""
        code = []
        
        code.append("// Pipeline stall and flush logic")
        
        # Generate stall signals
        code.append("reg pipeline_stall;")
        code.append("reg pipeline_flush;")
        code.append("")
        
        # Generate ready signals
        code.append("always @(*) begin")
        
        for stage in pipeline_stages:
            code.append(f"    pipeline_stage_{stage.stage_id}_ready = !pipeline_stall;")
        
        code.append("end")
        code.append("")
        
        # Generate flush logic
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n || pipeline_flush) begin")
        
        for stage in pipeline_stages:
            code.append(f"        pipeline_stage_{stage.stage_id}_valid <= 1'b0;")
        
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_memory_bank(self, bank_id: int, memory_vars: List[Tuple[str, IRVariable]], 
                            num_banks: int) -> List[str]:
        """Generate a memory bank."""
        code = []
        
        # Calculate bank size
        total_memory = sum(var.memory_size for _, var in memory_vars)
        bank_size = max(256, total_memory // num_banks)
        addr_bits = max(8, (bank_size - 1).bit_length())
        
        code.append(f"// Memory bank {bank_id}")
        code.append(f"reg [31:0] memory_bank_{bank_id} [0:{bank_size-1}];")
        code.append(f"reg [{addr_bits-1}:0] bank_{bank_id}_addr;")
        code.append(f"reg [31:0] bank_{bank_id}_data_in;")
        code.append(f"reg [31:0] bank_{bank_id}_data_out;")
        code.append(f"reg bank_{bank_id}_write_enable;")
        code.append(f"reg bank_{bank_id}_read_enable;")
        code.append("")
        
        # Generate bank access logic
        code.append(f"always @(posedge clk) begin")
        code.append(f"    if (bank_{bank_id}_write_enable)")
        code.append(f"        memory_bank_{bank_id}[bank_{bank_id}_addr] <= bank_{bank_id}_data_in;")
        code.append(f"    if (bank_{bank_id}_read_enable)")
        code.append(f"        bank_{bank_id}_data_out <= memory_bank_{bank_id}[bank_{bank_id}_addr];")
        code.append(f"end")
        code.append("")
        
        return code
    
    def _generate_memory_bank_arbitration(self, num_banks: int) -> List[str]:
        """Generate memory bank arbitration logic."""
        code = []
        
        code.append("// Memory bank arbitration")
        
        # Generate bank selection logic
        bank_select_bits = max(1, (num_banks - 1).bit_length())
        code.append(f"reg [{bank_select_bits-1}:0] bank_select;")
        code.append("")
        
        # Generate bank selection
        code.append("always @(*) begin")
        code.append("    bank_select = memory_addr[1:0];  // Simple bank selection")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_memory_access_scheduling(self, memory_vars: List[Tuple[str, IRVariable]], 
                                         num_banks: int) -> List[str]:
        """Generate memory access scheduling logic."""
        code = []
        
        code.append("// Memory access scheduling")
        
        # Generate access request signals
        for bank_id in range(num_banks):
            code.append(f"reg bank_{bank_id}_request;")
            code.append(f"reg bank_{bank_id}_grant;")
        
        code.append("")
        
        # Generate simple round-robin scheduling
        code.append("always @(*) begin")
        
        for bank_id in range(num_banks):
            code.append(f"    bank_{bank_id}_grant = bank_{bank_id}_request;")
        
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_parallel_loop_iterations(self, loop_block: IRBlock, unroll_factor: int) -> List[str]:
        """Generate parallel loop iterations."""
        code = []
        
        code.append(f"// Parallel loop iterations (unroll factor: {unroll_factor})")
        
        # Generate iteration variables
        for i in range(unroll_factor):
            code.append(f"reg [31:0] loop_iter_{i}_index;")
            code.append(f"reg [31:0] loop_iter_{i}_data;")
            code.append(f"reg loop_iter_{i}_valid;")
        
        code.append("")
        
        # Generate iteration logic
        code.append("always @(posedge clk) begin")
        
        for i in range(unroll_factor):
            code.append(f"    if (loop_iter_{i}_valid) begin")
            code.append(f"        // Iteration {i} logic")
            code.append(f"        loop_iter_{i}_data <= loop_iter_{i}_data + 1;")
            code.append(f"    end")
        
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_unroll_control_logic(self, loop_block: IRBlock, unroll_factor: int) -> List[str]:
        """Generate control logic for unrolled loops."""
        code = []
        
        code.append("// Unroll control logic")
        
        # Generate unroll counter
        code.append("reg [31:0] unroll_counter;")
        code.append("reg unroll_active;")
        code.append("")
        
        # Generate unroll control
        code.append("always @(posedge clk or negedge rst_n) begin")
        code.append("    if (!rst_n) begin")
        code.append("        unroll_counter <= 0;")
        code.append("        unroll_active <= 1'b0;")
        code.append("    end else if (unroll_active) begin")
        code.append(f"        if (unroll_counter < loop_bound - {unroll_factor}) begin")
        code.append(f"            unroll_counter <= unroll_counter + {unroll_factor};")
        code.append("        end else begin")
        code.append("            unroll_active <= 1'b0;")
        code.append("        end")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_iteration_management(self, loop_block: IRBlock, unroll_factor: int) -> List[str]:
        """Generate iteration management logic."""
        code = []
        
        code.append("// Iteration management")
        
        # Generate iteration enables
        for i in range(unroll_factor):
            code.append(f"always @(*) begin")
            code.append(f"    loop_iter_{i}_valid = unroll_active && ")
            code.append(f"        (unroll_counter + {i} < loop_bound);")
            code.append(f"end")
        
        code.append("")
        
        return code
    
    def _generate_branch_prediction_logic(self, branch_blocks: List[IRBlock]) -> List[str]:
        """Generate branch prediction logic."""
        code = []
        
        code.append("// Branch prediction logic")
        
        # Generate branch history table
        code.append("reg [1:0] branch_history [0:15];")
        code.append("reg [3:0] branch_pc;")
        code.append("reg branch_prediction;")
        code.append("")
        
        # Generate prediction logic
        code.append("always @(*) begin")
        code.append("    branch_prediction = branch_history[branch_pc][1];")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_speculative_execution_units(self, branch_blocks: List[IRBlock]) -> List[str]:
        """Generate speculative execution units."""
        code = []
        
        code.append("// Speculative execution units")
        
        # Generate speculative units for each branch path
        for i, block in enumerate(branch_blocks):
            code.append(f"// Speculative unit {i}")
            code.append(f"reg [31:0] spec_unit_{i}_data;")
            code.append(f"reg spec_unit_{i}_valid;")
            code.append(f"reg spec_unit_{i}_commit;")
            code.append("")
        
        return code
    
    def _generate_speculation_resolution_logic(self, branch_blocks: List[IRBlock]) -> List[str]:
        """Generate speculation resolution logic."""
        code = []
        
        code.append("// Speculation resolution logic")
        
        # Generate resolution control
        code.append("reg speculation_resolved;")
        code.append("reg speculation_correct;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (speculation_resolved) begin")
        code.append("        if (speculation_correct) begin")
        code.append("            // Commit speculative results")
        
        for i, block in enumerate(branch_blocks):
            code.append(f"            spec_unit_{i}_commit <= spec_unit_{i}_valid;")
        
        code.append("        end else begin")
        code.append("            // Flush speculative results")
        
        for i, block in enumerate(branch_blocks):
            code.append(f"            spec_unit_{i}_valid <= 1'b0;")
        
        code.append("        end")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_wide_execution_units(self, operations: List[IROperation], data_width: int) -> List[str]:
        """Generate wide execution units."""
        code = []
        
        code.append(f"// Wide execution units ({data_width}-bit)")
        
        # Generate wide ALU
        code.append(f"reg [{data_width-1}:0] wide_alu_input_a;")
        code.append(f"reg [{data_width-1}:0] wide_alu_input_b;")
        code.append(f"reg [{data_width-1}:0] wide_alu_result;")
        code.append(f"reg [3:0] wide_alu_operation;")
        code.append("")
        
        # Generate wide ALU logic
        code.append("always @(*) begin")
        code.append("    case (wide_alu_operation)")
        code.append("        4'b0000: wide_alu_result = wide_alu_input_a + wide_alu_input_b;")
        code.append("        4'b0001: wide_alu_result = wide_alu_input_a - wide_alu_input_b;")
        code.append("        4'b0010: wide_alu_result = wide_alu_input_a & wide_alu_input_b;")
        code.append("        4'b0011: wide_alu_result = wide_alu_input_a | wide_alu_input_b;")
        code.append("        default: wide_alu_result = wide_alu_input_a;")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_wide_data_routing(self, operations: List[IROperation], data_width: int) -> List[str]:
        """Generate wide data routing logic."""
        code = []
        
        code.append(f"// Wide data routing ({data_width}-bit)")
        
        # Generate wide interconnect
        code.append(f"reg [{data_width-1}:0] wide_interconnect_data;")
        code.append("reg [3:0] wide_interconnect_select;")
        code.append("")
        
        # Generate routing logic
        code.append("always @(*) begin")
        code.append("    case (wide_interconnect_select)")
        code.append("        4'b0000: wide_interconnect_data = wide_alu_result;")
        code.append("        default: wide_interconnect_data = {data_width{1'b0}};")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_wide_result_handling(self, operations: List[IROperation], data_width: int) -> List[str]:
        """Generate wide result handling logic."""
        code = []
        
        code.append(f"// Wide result handling ({data_width}-bit)")
        
        # Generate result registers
        code.append(f"reg [{data_width-1}:0] wide_result_reg;")
        code.append("reg wide_result_valid;")
        code.append("")
        
        # Generate result handling
        code.append("always @(posedge clk) begin")
        code.append("    wide_result_reg <= wide_interconnect_data;")
        code.append("    wide_result_valid <= 1'b1;")
        code.append("end")
        code.append("")
        
        return code
    
    def _build_dependency_graph(self, operations: List[IROperation]) -> Dict[int, List[int]]:
        """Build dependency graph for operations."""
        dependencies = {}
        
        # Initialize empty dependencies
        for i in range(len(operations)):
            dependencies[i] = []
        
        # Analyze data dependencies
        for i, op in enumerate(operations):
            for j in range(i):
                if self._has_dependency(operations[j], op):
                    dependencies[i].append(j)
        
        return dependencies
    
    def _has_dependency(self, op1: IROperation, op2: IROperation) -> bool:
        """Check if op2 depends on op1."""
        # Simple dependency check - op2 depends on op1 if op1's result is used by op2
        if op1.result and op2.operands:
            for operand in op2.operands:
                if hasattr(operand, 'name') and hasattr(op1.result, 'name'):
                    if operand.name == op1.result.name:
                        return True
        return False
    
    def _is_operation_ready(self, op_index: int, dependency_graph: Dict[int, List[int]], 
                          scheduled_ops: Set[int]) -> bool:
        """Check if operation is ready for scheduling."""
        dependencies = dependency_graph.get(op_index, [])
        return all(dep in scheduled_ops for dep in dependencies)
    
    def _get_resource_type_for_operation(self, op: IROperation) -> str:
        """Get resource type for an operation."""
        op_to_resource = {
            OperationType.ADD: "ADDER",
            OperationType.SUB: "ADDER",
            OperationType.MUL: "MULTIPLIER",
            OperationType.DIV: "DIVIDER",
            OperationType.MOD: "ALU",
            OperationType.BIT_AND: "ALU",
            OperationType.BIT_OR: "ALU",
            OperationType.BIT_XOR: "ALU",
            OperationType.LSHIFT: "SHIFTER",
            OperationType.RSHIFT: "SHIFTER",
            OperationType.EQ: "COMPARATOR",
            OperationType.NEQ: "COMPARATOR",
            OperationType.LT: "COMPARATOR",
            OperationType.GT: "COMPARATOR",
            OperationType.LTE: "COMPARATOR",
            OperationType.GTE: "COMPARATOR",
        }
        
        return op_to_resource.get(op.op_type, "ALU") 