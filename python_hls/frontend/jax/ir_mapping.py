"""
Direct mapping from JaxprGraph to Python-HLS Intermediate Representation (IR).

Converts functional Jaxpr primitive equations directly into Python-HLS
IRFunction, IRBlock, IRInstruction, and IROperation dataflow nodes.
"""

from typing import Dict, List, Optional, Union

from python_hls.ir.ir_nodes import (
    IR,
    IRFunction,
    IRBlock,
    IRInstruction,
    IROperation,
    IRVariable,
    IRConstant,
    OperationType,
    DataType,
)
from .tracing import JaxprGraph, JaxprNode, JaxprVariable
from .diagnostics import JAXUnsupportedPrimitiveError

PRIMITIVE_TO_IR_OP = {
    "add": OperationType.ADD,
    "sub": OperationType.SUB,
    "mul": OperationType.MUL,
    "div": OperationType.DIV,
    "floor_divide": OperationType.DIV,
    "neg": OperationType.NEG,
    "abs": OperationType.ASSIGN,
    "clamp": OperationType.ASSIGN,
    "convert_element_type": OperationType.ASSIGN,
    "dot_general": OperationType.MUL,  # Core linear algebra multiplier
    "reduce_sum": OperationType.ADD,   # Core reduction adder
    "max": OperationType.GT,
    "min": OperationType.LT,
    "transpose": OperationType.ASSIGN,
    "reshape": OperationType.ASSIGN,
    "broadcast_in_dim": OperationType.ASSIGN,
}


class JaxprIRMapper:
    """Maps a traced JaxprGraph directly into Python-HLS IR data structures."""

    def __init__(self):
        self._next_id = 1

    def _get_id(self) -> int:
        cur = self._next_id
        self._next_id += 1
        return cur

    def map_to_ir(self, graph: JaxprGraph) -> IRFunction:
        """
        Convert a JaxprGraph to an IRFunction.

        Args:
            graph: Traced JaxprGraph instance.

        Returns:
            An IRFunction ready for scheduling, resource allocation, and RTL synthesis.
        """
        ir_func = IRFunction(name=graph.name, node_id=self._get_id())
        entry_block = IRBlock(name="entry", node_id=self._get_id())
        ir_vars: Dict[str, IRVariable] = {}

        # 1. Map Inputs
        for jax_var in graph.inputs:
            is_arr = len(jax_var.shape) > 0
            dt = DataType.ARRAY if is_arr else (DataType.FLOAT if "float" in jax_var.dtype else DataType.INT)
            var = IRVariable(
                name=jax_var.name,
                node_id=self._get_id(),
                data_type=dt,
                bit_width=jax_var.bit_width,
                is_input=True,
                memory_size=jax_var.size_bytes if is_arr else 1,
            )
            ir_vars[jax_var.name] = var
            ir_func.parameters.append(var)
            ir_func.local_vars[jax_var.name] = var

        # 2. Map Intermediate Variables & Constants
        for name, jax_var in graph.variables.items():
            if name not in ir_vars:
                is_arr = len(jax_var.shape) > 0
                dt = DataType.ARRAY if is_arr else (DataType.FLOAT if "float" in jax_var.dtype else DataType.INT)
                var = IRVariable(
                    name=name,
                    node_id=self._get_id(),
                    data_type=dt,
                    bit_width=jax_var.bit_width,
                    is_input=False,
                    memory_size=jax_var.size_bytes if is_arr else 1,
                )
                ir_vars[name] = var
                ir_func.local_vars[name] = var

        # 3. Map Equations to Instructions and Operations
        for node in graph.nodes:
            if not node.lowerable or node.primitive not in PRIMITIVE_TO_IR_OP:
                raise JAXUnsupportedPrimitiveError(
                    f"Cannot map JAX primitive '{node.primitive}' to Python-HLS IR."
                )

            op_type = PRIMITIVE_TO_IR_OP[node.primitive]
            instr = IRInstruction(name=f"instr_{node.name}", node_id=self._get_id())

            # Resolve operands
            operands: List[Union[IRVariable, IRConstant, IROperation]] = []
            for inp_name in node.inputs:
                if inp_name in ir_vars:
                    operands.append(ir_vars[inp_name])
                else:
                    # Constant operand
                    val = 0
                    if inp_name.startswith("lit_"):
                        try:
                            val = int(inp_name.replace("lit_", "").replace("m", "-"))
                        except ValueError:
                            pass
                    operands.append(IRConstant(val, self._get_id()))

            # Primary output
            out_var = ir_vars[node.outputs[0]] if node.outputs else None

            op = IROperation(
                name=f"op_{node.name}",
                node_id=self._get_id(),
                op_type=op_type,
                operands=operands,
                result=out_var,
            )
            instr.operations.append(op)
            entry_block.instructions.append(instr)

        # 4. Map Return / Output
        if graph.outputs:
            out_name = graph.outputs[0].name
            if out_name in ir_vars:
                ret_var = ir_vars[out_name]
                ret_var.is_output = True
                ir_func.return_var = ret_var
                ret_op = IROperation(
                    name="return_op",
                    node_id=self._get_id(),
                    op_type=OperationType.RETURN,
                    operands=[ret_var],
                    result=None,
                )
                ret_instr = IRInstruction(name="return_instr", node_id=self._get_id(), operations=[ret_op])
                entry_block.instructions.append(ret_instr)

        # 5. Connect blocks to function
        ir_func.blocks = [entry_block]
        ir_func.entry_block = entry_block
        ir_func.exit_block = entry_block

        return ir_func


def jaxpr_to_ir(graph: JaxprGraph) -> IRFunction:
    """Convenience function to map a JaxprGraph to an IRFunction."""
    mapper = JaxprIRMapper()
    return mapper.map_to_ir(graph)
