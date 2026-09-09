"""
Intermediate Representation (IR) module.
"""

from .ir_generator import IRGenerator
from .ir_nodes import (
    IR, IRFunction, IRBlock, IRInstruction,
    IRVariable, IRConstant, IROperation
)
from .streaming_pragma import (
    StreamingPragma, 
    extract_streaming_pragmas,
    extract_pragmas_from_node
) 