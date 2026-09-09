"""
VHDL generator for HLS IR.
"""

from typing import Dict, List, Optional, Set, Union, Any
import os

from ..ir.ir_nodes import (
    IR, IRFunction, IRBlock, IRInstruction,
    IRVariable, IRConstant, IROperation, OperationType, DataType
)
from ..netlist import Netlist, NetlistModule, NetlistPort, NetlistSignal


class VHDLGenerator:
    """Generator for converting HLS IR to VHDL netlist."""
    
    def __init__(self):
        """Initialize the VHDL generator."""
        self.netlist = None
        self.current_module = None
        self.signal_map = {}
        self.operation_map = {
            OperationType.ADD: "+",
            OperationType.SUB: "-",
            OperationType.MUL: "*",
            OperationType.DIV: "/",
            OperationType.MOD: "mod",
            OperationType.POW: "**",
            OperationType.LSHIFT: "sll",
            OperationType.RSHIFT: "srl",
            OperationType.BIT_OR: "or",
            OperationType.BIT_AND: "and",
            OperationType.BIT_XOR: "xor",
            OperationType.LOGIC_OR: "or",
            OperationType.LOGIC_AND: "and",
            OperationType.EQ: "=",
            OperationType.NEQ: "/=",
            OperationType.LT: "<",
            OperationType.LTE: "<=",
            OperationType.GT: ">",
            OperationType.GTE: ">=",
            OperationType.NEG: "-",
            OperationType.NOT: "not",
            OperationType.BIT_NOT: "not",
        }
    
    def generate(self, ir: IR) -> Netlist:
        """
        Generate a VHDL netlist from the IR.
        
        Args:
            ir: IR to convert
            
        Returns:
            VHDL netlist
        """
        self.netlist = Netlist(target_language="vhdl")
        self.signal_map = {}
        
        # For each function, create an entity
        for func_name, func in ir.functions.items():
            self._generate_entity(func)
        
        return self.netlist
    
    def _generate_entity(self, func: IRFunction) -> NetlistModule:
        """
        Generate a VHDL entity from an IR function.
        
        Args:
            func: IR function
            
        Returns:
            VHDL entity
        """
        # Create module (entity in VHDL)
        module = NetlistModule(name=func.name)
        self.current_module = module
        
        # Create ports
        for param in func.parameters:
            port = NetlistPort(
                name=param.name,
                direction="in",
                width=param.bit_width,
                is_signed=param.data_type == DataType.INT
            )
            module.add_port(port)
            
            # Create corresponding signal
            signal = NetlistSignal(
                name=param.name,
                width=param.bit_width,
                is_signed=param.data_type == DataType.INT,
                is_reg=False
            )
            module.add_signal(signal)
            self.signal_map[param.name] = signal
        
        # Create return port if needed
        if func.return_var:
            port = NetlistPort(
                name="return_value",
                direction="out",
                width=func.return_var.bit_width,
                is_signed=func.return_var.data_type == DataType.INT
            )
            module.add_port(port)
            
            # Create corresponding signal
            signal = NetlistSignal(
                name="return_value",
                width=func.return_var.bit_width,
                is_signed=func.return_var.data_type == DataType.INT,
                is_reg=True
            )
            module.add_signal(signal)
            self.signal_map[func.return_var.name] = signal
        
        # Create signals for local variables
        for var_name, var in func.local_vars.items():
            signal = NetlistSignal(
                name=var_name,
                width=var.bit_width,
                is_signed=var.data_type == DataType.INT,
                is_reg=True
            )
            module.add_signal(signal)
            self.signal_map[var_name] = signal
        
        # Create state machine for control flow
        self._generate_state_machine(func, module)
        
        # Create datapath
        self._generate_datapath(func, module)
        
        # Add module to netlist
        self.netlist.add_module(module)
        
        return module
    
    def _generate_state_machine(self, func: IRFunction, module: NetlistModule) -> None:
        """
        Generate a state machine for the function's control flow.
        
        Args:
            func: IR function
            module: VHDL module
        """
        # Create state register
        state_signal = NetlistSignal(
            name="state",
            width=32,  # Enough bits to represent all states
            is_signed=False,
            is_reg=True
        )
        module.add_signal(state_signal)
        
        # Create next state signal
        next_state_signal = NetlistSignal(
            name="next_state",
            width=32,
            is_signed=False,
            is_reg=False
        )
        module.add_signal(next_state_signal)
        
        # Create state constants for each block
        state_constants = {}
        for i, block in enumerate(func.blocks):
            state_constants[block.name] = i
        
        # Generate state machine logic
        # This is a placeholder for the actual state machine generation
        state_machine_code = f"""
-- State machine
process(clk, rst_n)
begin
    if rst_n = '0' then
        state <= 0;  -- Initial state
    elsif rising_edge(clk) then
        state <= next_state;
    end if;
end process;

-- Next state logic
process(state)
begin
    next_state <= state;  -- Default: stay in current state
    
    case state is
        -- State transitions for each block
        -- This is a placeholder for the actual state transitions
    end case;
end process;
"""
        module.add_vhdl_block(state_machine_code)
    
    def _generate_datapath(self, func: IRFunction, module: NetlistModule) -> None:
        """
        Generate datapath for the function.
        
        Args:
            func: IR function
            module: VHDL module
        """
        # For each block
        for block in func.blocks:
            # For each instruction
            for instruction in block.instructions:
                # For each operation
                for operation in instruction.operations:
                    # Generate VHDL for the operation
                    self._generate_operation(operation, module)
    
    def _generate_operation(self, operation: IROperation, module: NetlistModule) -> None:
        """
        Generate VHDL for an operation.
        
        Args:
            operation: IR operation
            module: VHDL module
        """
        # Get operation type and result variable
        op_type = operation.op_type
        result_var = operation.result
        
        # Skip if no result (e.g., for side effects only)
        if not result_var:
            return
        
        # Get result signal name
        result_signal = self.signal_map.get(result_var.name)
        if not result_signal:
            return
            
        # Get operand signals
        operand_exprs = []
        for operand in operation.operands:
            if hasattr(operand, 'node_id'):
                # Variable operand
                if operand.name in self.signal_map:
                    operand_exprs.append(operand.name)
                else:
                    # Skip operation if operand signal not found
                    return
            else:
                # Constant operand
                operand_exprs.append(str(operand))
        
        # Create operation expression based on operation type
        op_str = self.operation_map.get(op_type)
        if not op_str:
            return
            
        if len(operand_exprs) == 1:
            # Unary operation
            expr = f"{op_str} {operand_exprs[0]}"
        elif len(operand_exprs) == 2:
            # Binary operation
            expr = f"({operand_exprs[0]} {op_str} {operand_exprs[1]})"
        else:
            # Unsupported operation arity
            return
        
        # Create assignment statement based on control step
        control_step = operation.control_step
        
        # Generate the VHDL assignment
        vhdl_code = f"""
-- Operation at control step {control_step}
process(clk)
begin
    if rising_edge(clk) then
        if state = {control_step} then
            {result_var.name} <= {expr};
        end if;
    end if;
end process;
"""
        module.add_vhdl_block(vhdl_code) 