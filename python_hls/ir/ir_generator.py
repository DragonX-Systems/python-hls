"""
Generator for converting Python AST to IR.
"""

import ast
from typing import Dict, List, Optional, Set, Union, Any, Tuple, cast
import networkx as nx
import logging
from .ir_nodes import (
    IR, IRFunction, IRBlock, IRInstruction, IRVariable,
    IRConstant, IROperation, OperationType, DataType, StreamingComponent
)
from .streaming_pragma import StreamingPragma, extract_streaming_pragmas, extract_pragmas_from_node

# Configure logging
logger = logging.getLogger(__name__)

class IRGenerator:
    """Generator for converting Python AST to IR."""
    
    def __init__(self, parser=None):
        """Initialize the IR generator."""
        self.ir = IR()
        self.next_id = 0
        
        # Maps for tracking variables and blocks
        self.var_map: Dict[str, IRVariable] = {}
        self.block_map: Dict[ast.AST, IRBlock] = {}
        self.current_function: Optional[IRFunction] = None
        
        # Counter for loops and iterations
        self.loop_count = 0
        self.total_iterations = 0
        
        # Maps for Python operators to IR operations
        self.binop_map = {
            ast.Add: OperationType.ADD,
            ast.Sub: OperationType.SUB,
            ast.Mult: OperationType.MUL,
            ast.Div: OperationType.DIV,
            ast.Mod: OperationType.MOD,
            ast.Pow: OperationType.POW,
            ast.LShift: OperationType.LSHIFT,
            ast.RShift: OperationType.RSHIFT,
            ast.BitOr: OperationType.BIT_OR,
            ast.BitAnd: OperationType.BIT_AND,
            ast.BitXor: OperationType.BIT_XOR,
        }
        
        self.unaryop_map = {
            ast.UAdd: lambda x: x,  # No-op
            ast.USub: OperationType.NEG,
            ast.Not: OperationType.NOT,
            ast.Invert: OperationType.BIT_NOT,
        }
        
        self.cmpop_map = {
            ast.Eq: OperationType.EQ,
            ast.NotEq: OperationType.NEQ,
            ast.Lt: OperationType.LT,
            ast.LtE: OperationType.LTE,
            ast.Gt: OperationType.GT,
            ast.GtE: OperationType.GTE,
        }
        
        self.boolop_map = {
            ast.And: OperationType.LOGIC_AND,
            ast.Or: OperationType.LOGIC_OR,
        }
        
        self.source_lines = []
        if parser and hasattr(parser, 'source_lines'):
            self.source_lines = parser.source_lines
            
        # Track streaming pragmas
        self.streaming_pragmas = {}
    
    def generate(self, node: ast.AST) -> IR:
        """
        Generate IR from a Python AST.
        
        Args:
            node: Python AST
            
        Returns:
            Generated IR
        """
        self.ir = IR()
        self.next_id = 0
        self.loop_count = 0
        self.total_iterations = 0
        
        # Extract streaming pragmas from source code
        if self.source_lines:
            self.streaming_pragmas = extract_streaming_pragmas(self.source_lines)
        
        if isinstance(node, ast.Module):
            self._process_module(node)
        elif isinstance(node, ast.FunctionDef):
            self._process_function(node)
        else:
            raise ValueError(f"Unsupported AST node type: {type(node).__name__}")
        
        # Process any pending memory size annotations
        for func_name, func in self.ir.functions.items():
            self._analyze_pending_memory_sizes(func)
        
        # Log loop statistics after processing
        logger.info(f"Total number of for loops: {self.loop_count}")
        logger.info(f"Total loop iterations (for constant ranges): {self.total_iterations}")
        
        return self.ir
    
    def _get_next_id(self) -> int:
        """Get the next unique ID for IR nodes."""
        id_val = self.next_id
        self.next_id += 1
        return id_val
    
    def _process_module(self, node: ast.Module) -> None:
        """Process a module AST node."""
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._process_function(item)
            elif isinstance(item, ast.Assign):
                # Global variables
                self._process_global_assign(item)
            else:
                # For now, ignore other top-level statements
                pass
    
    def _process_function(self, node: ast.FunctionDef) -> IRFunction:
        """Process a function definition AST node."""
        func = IRFunction(
            name=node.name,
            node_id=self._get_next_id()
        )
        
        self.current_function = func
        self.var_map = {}  # Reset variable map for this function
        
        # Process function parameters
        for arg in node.args.args:
            param = IRVariable(
                name=arg.arg,
                node_id=self._get_next_id(),
                data_type=DataType.INT,  # Default to INT, will be updated if array detected
                bit_width=32,  # Default to 32 bits
                is_input=True
            )
            func.parameters.append(param)
            self.var_map[arg.arg] = param
        
        # Analyze parameter usage to detect arrays
        self._analyze_parameter_usage(node, func)
        
        # Preprocess to identify arrays and large variables
        self._identify_large_variables(node, func)
        
        # Create control flow graph
        self._create_cfg(node, func)
        
        # Process streaming components after all function bodies are processed
        if self.streaming_pragmas:
            self._process_streaming_components(func)
        
        # Add function to IR
        self.ir.add_function(func)
        self.current_function = None
        
        return func
    
    def _analyze_parameter_usage(self, node: ast.FunctionDef, func: IRFunction) -> None:
        """Analyze how parameters are used to detect arrays."""
        param_names = [param.name for param in func.parameters]
        
        # Walk through the function body to find array usage patterns
        for stmt in ast.walk(node):
            # Check for subscript access (param[index])
            if isinstance(stmt, ast.Subscript):
                if isinstance(stmt.value, ast.Name) and stmt.value.id in param_names:
                    # This parameter is used as an array
                    param_name = stmt.value.id
                    for param in func.parameters:
                        if param.name == param_name:
                            param.data_type = DataType.ARRAY
                            param.memory_size = 1024  # Default size, will be updated later
                            logger.info(f"Detected array parameter: {param_name}")
                            break
            
            # Check for len() calls on parameters
            elif isinstance(stmt, ast.Call):
                if (isinstance(stmt.func, ast.Name) and stmt.func.id == 'len' and
                    len(stmt.args) > 0 and isinstance(stmt.args[0], ast.Name) and
                    stmt.args[0].id in param_names):
                    # This parameter is used as an array
                    param_name = stmt.args[0].id
                    for param in func.parameters:
                        if param.name == param_name:
                            param.data_type = DataType.ARRAY
                            param.memory_size = 1024  # Default size, will be updated later
                            logger.info(f"Detected array parameter (len usage): {param_name}")
                            break
            
            # Check for iteration over parameters (for item in param)
            elif isinstance(stmt, ast.For):
                if isinstance(stmt.iter, ast.Name) and stmt.iter.id in param_names:
                    # This parameter is used as an array
                    param_name = stmt.iter.id
                    for param in func.parameters:
                        if param.name == param_name:
                            param.data_type = DataType.ARRAY
                            param.memory_size = 1024  # Default size, will be updated later
                            logger.info(f"Detected array parameter (iteration): {param_name}")
                            break
    
    def _identify_large_variables(self, node: ast.FunctionDef, func: IRFunction) -> None:
        """
        Identify arrays and large variables that need scratchpad memory.
        
        Args:
            node: Function AST node
            func: IR function
        """
        # First, scan for any memory size annotations that we can use later
        memory_size_vars = {}
        dimension_vars = {}  # Store dimension variables for later evaluation
        
        # Log all local variable declarations to help with debugging
        logger.info(f"Function {func.name} variables:")
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                logger.info(f"Assignment: {ast.dump(stmt)}")
        
        # First pass: find dimension variables and constants
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if isinstance(target, ast.Name):
                    name = target.id
                    # Extract constant value if present
                    constant_value = self._extract_constant_value(stmt.value)
                    if constant_value is not None:
                        # Store this constant for later evaluation of expressions
                        dimension_vars[name] = constant_value
                        logger.info(f"Found constant value for variable: {name}={constant_value}")
                        
                        # Create constant for this dimension so it's available for other evaluations
                        const = IRConstant(
                            name=f"{name}_const_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            data_type=DataType.INT,
                            value=constant_value,
                            bit_width=32
                        )
                        
                        # Create and add variable to map
                        var = IRVariable(
                            name=name,
                            node_id=self._get_next_id(),
                            data_type=DataType.INT,
                            bit_width=32
                        )
                        self.var_map[name] = var
                        func.local_vars[name] = var
                        
                        # Create assignment instruction to track this value
                        instr = IRInstruction(
                            name=f"assign_{self._get_next_id()}",
                            node_id=self._get_next_id()
                        )
                        
                        # Create assignment operation
                        assign_op = IROperation(
                            name=f"op_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            op_type=OperationType.ASSIGN,
                            operands=[const],
                            result=var
                        )
                        
                        instr.operations.append(assign_op)
                        
                        # Add to a block
                        block = IRBlock(
                            name=f"{func.name}_init_{self._get_next_id()}",
                            node_id=self._get_next_id()
                        )
                        block.instructions.append(instr)
                        func.blocks.append(block)
                        
        # Second pass: look for memory size variables now that we have constant values
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if isinstance(target, ast.Name):
                    name = target.id
                    if name.endswith('_memory_size') or name.endswith('_size'):
                        # This is a memory size annotation
                        base_var_name = name.replace('_memory_size', '').replace('_size', '')
                        # Try to extract constant value if possible, now that dimensions are defined
                        memory_size = self._extract_constant_value(stmt.value)
                        if memory_size is not None and memory_size > 0:
                            memory_size_vars[base_var_name] = memory_size
                            logger.info(f"Found memory size annotation for {base_var_name}: {memory_size} bytes")
                        else:
                            logger.info(f"Could not extract constant value for {name}: {ast.dump(stmt.value)}")
        
        # Initialize pending memory sizes dict for later processing
        if memory_size_vars:
            func.pending_memory_sizes = memory_size_vars
            
        # Also store dimension variables for easy access later
        if dimension_vars:
            func.dimension_vars = dimension_vars
        
        # Now process array initializations as before
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                
                # Check for array initializations
                if isinstance(stmt.value, ast.List):
                    if isinstance(target, ast.Name):
                        name = target.id
                        size = len(stmt.value.elts)
                        
                        # Create variable with array attributes
                        var = IRVariable(
                            name=name,
                            node_id=self._get_next_id(),
                            data_type=DataType.ARRAY,
                            bit_width=32,  # Default element size
                            memory_size=size  # Number of elements
                        )
                        
                        # Apply memory size annotation if available
                        if name in memory_size_vars:
                            memory_size = memory_size_vars[name]
                            element_size = var.bit_width // 8  # bytes per element
                            if element_size > 0:
                                var.memory_size = max(var.memory_size, memory_size // element_size)
                                logger.info(f"Applied memory size to {name}: {var.memory_size} elements")
                        
                        func.local_vars[name] = var
                        self.var_map[name] = var
                
                # Check for nested array initializations (2D arrays)
                elif isinstance(stmt.value, ast.ListComp):
                    if isinstance(target, ast.Name):
                        name = target.id
                        # Estimate size - this is a simplification
                        size = 100  # Default size for list comprehensions
                        
                        var = IRVariable(
                            name=name,
                            node_id=self._get_next_id(),
                            data_type=DataType.ARRAY,
                            bit_width=32,
                            memory_size=size
                        )
                        
                        func.local_vars[name] = var
                        self.var_map[name] = var
                
                # Check for array slicing (e.g., arr = data[:])
                elif isinstance(stmt.value, ast.Subscript):
                    if isinstance(stmt.value.slice, ast.Slice) and isinstance(target, ast.Name):
                        # This is array slicing like arr = data[:]
                        name = target.id
                        source_name = None
                        
                        # Get the source array name
                        if isinstance(stmt.value.value, ast.Name):
                            source_name = stmt.value.value.id
                        
                        # Check if source is a known array parameter
                        source_var = None
                        if source_name and source_name in self.var_map:
                            source_var = self.var_map[source_name]
                        
                        # If source is an array, create local array with same properties
                        if source_var and source_var.data_type == DataType.ARRAY:
                            var = IRVariable(
                                name=name,
                                node_id=self._get_next_id(),
                                data_type=DataType.ARRAY,
                                bit_width=source_var.bit_width,  # Same element size as source
                                memory_size=source_var.memory_size  # Same size as source
                            )
                            
                            func.local_vars[name] = var
                            self.var_map[name] = var
                            logger.info(f"Detected array slicing: {name} = {source_name}[:]")
                        else:
                            # Create a default array variable
                            var = IRVariable(
                                name=name,
                                node_id=self._get_next_id(),
                                data_type=DataType.ARRAY,
                                bit_width=32,
                                memory_size=1024  # Default size
                            )
                            
                            func.local_vars[name] = var
                            self.var_map[name] = var
                            logger.info(f"Detected array slicing with unknown source: {name} = {source_name}[:]")
                        
                # Check for zeros/ones initializations (numpy-like)
                elif isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
                    func_name = stmt.value.func.id
                    if func_name in ["zeros", "ones", "empty", "array"]:
                        if isinstance(target, ast.Name):
                            name = target.id
                            # Try to determine size from arguments
                            size = 100  # Default
                            if stmt.value.args and isinstance(stmt.value.args[0], ast.Constant):
                                size = stmt.value.args[0].value
                            
                            var = IRVariable(
                                name=name,
                                node_id=self._get_next_id(),
                                data_type=DataType.ARRAY,
                                bit_width=32,
                                memory_size=size
                            )
                            
                            func.local_vars[name] = var
                            self.var_map[name] = var
    
    def _process_global_assign(self, node: ast.Assign) -> None:
        """Process a global assignment AST node."""
        # For simplicity, we'll only handle basic assignments to a single target
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return
        
        target = node.targets[0]
        name = target.id
        
        # Create a global variable
        var = IRVariable(
            name=name,
            node_id=self._get_next_id(),
            data_type=DataType.INT,  # Default to INT, needs type inference
            bit_width=32,  # Default to 32 bits
        )
        
        self.ir.add_global_var(var)
    
    def _create_cfg(self, node: ast.FunctionDef, func: IRFunction) -> None:
        """Create control flow graph for a function."""
        # Create entry block
        entry_block = IRBlock(
            name=f"{func.name}_entry",
            node_id=self._get_next_id()
        )
        func.entry_block = entry_block
        func.blocks.append(entry_block)
        
        # Process function body
        current_block = entry_block
        for stmt in node.body:
            current_block = self._process_statement(stmt, current_block, func)
        
        # Create exit block if needed
        if not any(isinstance(stmt, ast.Return) for stmt in node.body):
            exit_block = IRBlock(
                name=f"{func.name}_exit",
                node_id=self._get_next_id()
            )
            func.exit_block = exit_block
            func.blocks.append(exit_block)
            
            # Connect current block to exit block
            current_block.successors.append(exit_block)
            exit_block.predecessors.append(current_block)
        
        # Store loop statistics in function
        func.loop_count = 0
        func.loop_iterations = 0
        self._analyze_loops(func)
    
    def _analyze_loops(self, func: IRFunction) -> None:
        """
        Analyze loops in a function and store statistics.
        
        Args:
            func: Function to analyze
        """
        # Find all loop headers
        loop_blocks = [block for block in func.blocks if block.loop_header == block]
        func.loop_count = len(loop_blocks)
        
        # First pass: Collect all variable definitions and propagate constants
        var_values = {}  # Map of variable names to their constant values, if known
        
        # Scan the blocks to find constant initializations
        for block in func.blocks:
            for instr in block.instructions:
                for op in instr.operations:
                    if op.op_type == OperationType.ASSIGN and hasattr(op, 'result') and op.result:
                        if len(op.operands) > 0 and isinstance(op.operands[0], IRConstant):
                            var_name = op.result.name
                            var_values[var_name] = op.operands[0].value
        
        # Second pass: Update range bounds for loops with variables
        for loop_block in loop_blocks:
            # Check if this block has range expressions stored
            if hasattr(loop_block, 'range_start_var') and loop_block.range_start_var in var_values:
                loop_block.range_start = var_values[loop_block.range_start_var]
                
            if hasattr(loop_block, 'range_end_var') and loop_block.range_end_var in var_values:
                loop_block.range_end = var_values[loop_block.range_end_var]
                
            if hasattr(loop_block, 'range_step_var') and loop_block.range_step_var in var_values:
                loop_block.range_step = var_values[loop_block.range_step_var]
            
            # Recalculate iterations with updated values
            if hasattr(loop_block, 'range_start') and hasattr(loop_block, 'range_end') and hasattr(loop_block, 'range_step'):
                start = loop_block.range_start
                end = loop_block.range_end
                step = loop_block.range_step
                
                if start is not None and end is not None and step is not None:
                    # Only do arithmetic if all values are numeric
                    if (isinstance(start, (int, float)) and isinstance(end, (int, float)) and 
                        isinstance(step, (int, float))):
                        if step > 0 and start < end:
                            iterations = max(0, (end - start + step - 1) // step)
                            loop_block.loop_iterations = iterations
                        elif step < 0 and start > end:
                            iterations = max(0, (start - end - step - 1) // -step)
                            loop_block.loop_iterations = iterations
                    # For dynamic loops, the iterations are already set in _process_for
        
        # Calculate total iterations for the function
        total_iterations = 0
        for loop_block in loop_blocks:
            iterations = getattr(loop_block, 'loop_iterations', 0)
            if isinstance(iterations, (int, float)) and iterations > 0:
                total_iterations += iterations
            elif iterations == "dynamic":
                total_iterations += 16  # Conservative estimate for dynamic loops
        
        func.loop_iterations = total_iterations
        logger.info(f"Function '{func.name}' has {func.loop_count} loops with approximately {func.loop_iterations} total iterations")
    
    def _process_statement(self, node: ast.AST, current_block: IRBlock,
                          func: IRFunction) -> IRBlock:
        """
        Process a statement AST node.
        
        Returns the new current block after processing the statement.
        """
        if isinstance(node, ast.Assign):
            self._process_assign(node, current_block)
            return current_block
        elif isinstance(node, ast.AugAssign):
            self._process_aug_assign(node, current_block)
            return current_block
        elif isinstance(node, ast.If):
            return self._process_if(node, current_block, func)
        elif isinstance(node, ast.While):
            return self._process_while(node, current_block, func)
        elif isinstance(node, ast.For):
            return self._process_for(node, current_block, func)
        elif isinstance(node, ast.Return):
            self._process_return(node, current_block)
            return current_block
        elif isinstance(node, ast.Expr):
            # Process expressions that have side effects (like function calls)
            if isinstance(node.value, ast.Call):
                # Create an instruction for the expression
                instr = IRInstruction(
                    name=f"expr_{self._get_next_id()}",
                    node_id=self._get_next_id()
                )
                
                # Process the function call
                call_op = self._process_expression(node.value)
                
                # If it's a valid function call operation, add it to the instruction
                if call_op and isinstance(call_op, IROperation) and call_op.op_type == OperationType.CALL:
                    instr.operations.append(call_op)
                    current_block.instructions.append(instr)
            return current_block
        else:
            # Unsupported statement type
            return current_block
    
    def _process_assign(self, node: ast.Assign, block: IRBlock) -> None:
        """Process an assignment statement."""
        # For simplicity, we'll only handle assignments to a single target
        if len(node.targets) != 1:
            return
        
        target = node.targets[0]
        
        # Create instruction for the assignment
        instr = IRInstruction(
            name=f"assign_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        
        # Process the right side of the assignment
        right_side = self._process_expression(node.value)
        
        # Check for streaming pragmas on this assignment
        streaming_pragmas = extract_pragmas_from_node(node, self.source_lines)
        
        # Handle tuple unpacking (e.g., a, b = b, a % b)
        # Python semantics: evaluate all RHS first, then assign to all LHS
        if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
            targets = target.elts
            values = node.value.elts
            if len(targets) != len(values):
                logger.warning(f"Tuple assignment size mismatch: {len(targets)} targets vs {len(values)} values")
                return
            # Phase 1: evaluate all RHS and collect results (no side effects)
            rhs_results = []
            for v in values:
                rhs = self._process_expression(v)
                rhs_results.append(rhs)
            # Phase 2: create assignments. Process in REVERSE so that RHS expressions
            # that read other LHS vars see pre-update values. E.g. a,b=b,a%b: do b=a%b
            # first (adds MOD+assign), then a=b. MOD reads a,b before a is overwritten.
            for t, rhs in reversed(list(zip(targets, rhs_results))):
                if isinstance(t, ast.Name) and rhs is not None:
                    name = t.id
                    if name not in self.var_map:
                        var = IRVariable(name=name, node_id=self._get_next_id(),
                                         data_type=DataType.INT, bit_width=32)
                        self.var_map[name] = var
                        if self.current_function:
                            self.current_function.local_vars[name] = var
                    assign_instr = IRInstruction(name=f"assign_{self._get_next_id()}",
                                                  node_id=self._get_next_id())
                    if isinstance(rhs, IROperation):
                        if rhs.result is not None:
                            assign_op = IROperation(
                                name=f"assign_op_{self._get_next_id()}", node_id=self._get_next_id(),
                                op_type=OperationType.ASSIGN, operands=[rhs.result],
                                result=self.var_map[name])
                            assign_instr.operations.append(rhs)
                            assign_instr.operations.append(assign_op)
                        else:
                            rhs.result = self.var_map[name]
                            assign_instr.operations.append(rhs)
                    elif isinstance(rhs, (IRConstant, IRVariable)):
                        assign_op = IROperation(
                            name=f"assign_op_{self._get_next_id()}", node_id=self._get_next_id(),
                            op_type=OperationType.ASSIGN, operands=[rhs],
                            result=self.var_map[name])
                        assign_instr.operations.append(assign_op)
                    block.instructions.append(assign_instr)
            return
        elif isinstance(target, ast.Tuple):
            logger.warning("Tuple assignment with non-tuple RHS not fully supported")
            return

        # Handle variable assignments
        if isinstance(target, ast.Name):
            name = target.id
            
            # Check if variable already exists
            if name not in self.var_map:
                # Create new variable
                var = IRVariable(
                    name=name,
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,  # Default to INT, needs type inference
                    bit_width=32,  # Default to 32 bits
                )
                self.var_map[name] = var
                if self.current_function:
                    self.current_function.local_vars[name] = var
            
            # Process streaming pragmas to mark variables as streaming components
            for pragma in streaming_pragmas:
                if pragma.pragma_type == 'stream':
                    # Mark the variable as a streaming interface
                    var = self.var_map[name]
                    var.is_stream = True
                    
                    # Add direction if specified
                    if 'direction' in pragma.params:
                        var.stream_direction = pragma.params['direction']
                    
                    # Add width if specified
                    if 'width' in pragma.params:
                        var.bit_width = pragma.params['width']
                    
                    logger.info(f"Marked variable {name} as streaming interface")
                    
                    # Create a streaming component
                    if self.current_function:
                        component = StreamingComponent(
                            name=pragma.name,
                            component_type='stream',
                            params=pragma.params,
                            source_var=name,
                            dest_var=None
                        )
                        self.current_function.add_streaming_component(component)
            
            # Check if this is a special memory size variable that we should record
            if name.endswith('_memory_size') or name.endswith('_size'):
                base_var_name = name.replace('_memory_size', '').replace('_size', '')
                if base_var_name in self.var_map:
                    # Process the right side to get memory size
                    memory_size = self._extract_constant_value(node.value)
                    if memory_size is not None and memory_size > 0:
                        # Update the base variable with memory size info
                        base_var = self.var_map[base_var_name]
                        if base_var.data_type != DataType.ARRAY:
                            base_var.data_type = DataType.ARRAY
                        
                        # Estimate array element count (divide by typical element size)
                        element_size = base_var.bit_width // 8  # bytes per element
                        if element_size > 0:
                            base_var.memory_size = max(base_var.memory_size, memory_size // element_size)
                            logger.debug(f"Updated variable {base_var_name} with memory size {base_var.memory_size} elements")
                elif self.current_function:
                    # The base variable might not exist yet - store this for later processing
                    memory_size = self._extract_constant_value(node.value)
                    if memory_size is not None and memory_size > 0:
                        # Add this to a list of pending memory size annotations
                        if not hasattr(self.current_function, 'pending_memory_sizes'):
                            self.current_function.pending_memory_sizes = {}
                        self.current_function.pending_memory_sizes[base_var_name] = memory_size
                        logger.info(f"Stored pending memory size for {base_var_name}: {memory_size} bytes")
            
            # Handle assignment based on the right side
            if right_side is not None:
                if isinstance(right_side, IROperation):
                    # If the right side is already an operation (from _process_expression),
                    # we can use it directly but need to update its result
                    
                    # First add any operations that were created but not added to a block
                    if hasattr(right_side, 'result') and right_side.result is not None:
                        # For operations with an existing result, create an assign operation
                        assign_op = IROperation(
                            name=f"assign_op_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            op_type=OperationType.ASSIGN,
                            operands=[right_side.result],
                            result=self.var_map[name]
                        )
                        
                        # First add the compute operation
                        instr.operations.append(right_side)
                        # Then add the assignment
                        instr.operations.append(assign_op)
                    else:
                        # If the operation doesn't have a result, assign directly to our target
                        right_side.result = self.var_map[name]
                        instr.operations.append(right_side)
                    
                elif isinstance(right_side, (IRConstant, IRVariable)):
                    # Simple assignment from constant or variable
                    assign_op = IROperation(
                        name=f"assign_op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=OperationType.ASSIGN,
                        operands=[right_side],
                        result=self.var_map[name]
                    )
                    instr.operations.append(assign_op)
                    
                # Add the instruction to the block
                block.instructions.append(instr)
            
        # Handle array element assignments (e.g., a[i] = value)
        elif isinstance(target, ast.Subscript):
            # Process the array and index
            array = self._process_expression(target.value)
            
            if array:
                # Process the index
                if isinstance(target.slice, ast.Index):  # Python 3.8 and earlier
                    index = self._process_expression(target.slice.value)
                else:  # Python 3.9+
                    index = self._process_expression(target.slice)
                
                if index and right_side:
                    # Check if this is a streaming FIFO write operation
                    fifo_write = False
                    for pragma in streaming_pragmas:
                        if pragma.pragma_type == 'fifo_write':
                            # Process a streaming operation (FIFO write)
                            fifo_write = True
                            fifo_write_op = self._process_streaming_operation(pragma, right_side, array, index)
                            if fifo_write_op:
                                instr.operations.append(fifo_write_op)
                                block.instructions.append(instr)
                    
                    # If not a streaming operation, create a regular store
                    if not fifo_write:
                        # Create a store operation
                        store_op = IROperation(
                            name=f"store_op_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            op_type=OperationType.STORE,
                            operands=[right_side, array, index],
                            result=None  # Store doesn't produce a result
                        )
                        
                        # Add operations to instruction
                        if isinstance(right_side, IROperation):
                            # First compute the right side value
                            instr.operations.append(right_side)
                        
                        # Then store it
                        instr.operations.append(store_op)
                        
                        # Add the instruction to the block
                        block.instructions.append(instr)
    
    def _extract_constant_value(self, expr) -> Optional[int]:
        """Extract a constant value from an expression if possible.
        
        This function can handle:
        - Literal constants
        - Binary operations with constants 
        - Variables with known constant values
        - Binary operations that use variables with known constant values
        """
        # Track known variable values during constant propagation
        known_values = {}
        
        # Try to extract constant values from local variables
        if self.current_function:
            for var_name, var in self.var_map.items():
                # Look for assignments with constant values
                for block in self.current_function.blocks:
                    for instr in block.instructions:
                        for op in instr.operations:
                            if (op.op_type == OperationType.ASSIGN and 
                                hasattr(op, 'result') and op.result and 
                                op.result.name == var_name and 
                                len(op.operands) > 0 and 
                                isinstance(op.operands[0], IRConstant)):
                                known_values[var_name] = op.operands[0].value
        
        # Handle direct constant values
        if isinstance(expr, ast.Constant) and isinstance(expr.value, (int, float)):
            return int(expr.value)
        
        # Handle variable references with known values
        elif isinstance(expr, ast.Name):
            var_name = expr.id
            # Check if we have a known value for this variable
            if var_name in known_values:
                return known_values[var_name]
            
        # Handle binary operations
        elif isinstance(expr, ast.BinOp):
            # Try to evaluate left and right sides
            left = self._extract_constant_value(expr.left)
            right = self._extract_constant_value(expr.right)
            
            # If both sides are constant values, compute the result
            if left is not None and right is not None:
                if isinstance(expr.op, ast.Mult):
                    return left * right
                elif isinstance(expr.op, ast.Add):
                    return left + right
                elif isinstance(expr.op, ast.Sub):
                    return left - right
                elif isinstance(expr.op, ast.Div):
                    if right != 0:  # Avoid division by zero
                        return left // right if isinstance(left, int) and isinstance(right, int) else left / right
                elif isinstance(expr.op, ast.Mod):
                    if right != 0:  # Avoid modulo by zero
                        return left % right
                elif isinstance(expr.op, ast.Pow):
                    return left ** right
                elif isinstance(expr.op, ast.LShift):
                    return left << right
                elif isinstance(expr.op, ast.RShift):
                    return left >> right
                elif isinstance(expr.op, ast.BitOr):
                    return left | right
                elif isinstance(expr.op, ast.BitAnd):
                    return left & right
                elif isinstance(expr.op, ast.BitXor):
                    return left ^ right
        
        # For more complex expressions, we need full symbolic evaluation
        # which is not implemented here
        return None
    
    def _process_expression(self, node: ast.AST):
        """
        Process an expression and return an IRNode.
        
        This method translates Python expressions into IR operations, which is
        especially important for capturing computational operations in loop bodies.
        
        Args:
            node: Python AST node
            
        Returns:
            IRNode representing the expression (IRConstant, IRVariable, or IROperation)
        """
        if isinstance(node, ast.Constant):
            # Constant value
            return IRConstant(
                name=f"const_{self._get_next_id()}",
                node_id=self._get_next_id(),
                data_type=DataType.INT,  # Default to INT
                value=node.value,
                bit_width=32
            )
            
        elif isinstance(node, ast.Name):
            # Variable reference
            var_name = node.id
            if var_name in self.var_map:
                return self.var_map[var_name]
            return None
            
        elif isinstance(node, ast.BinOp):
            # Binary operation (e.g., a + b, c * d)
            left_operand = self._process_expression(node.left)
            right_operand = self._process_expression(node.right)
            
            if left_operand and right_operand:
                # Get operation type from binop_map
                op_type = self.binop_map.get(type(node.op))
                if op_type:
                    # Create a temporary variable for the result
                    tmp_var = IRVariable(
                        name=f"tmp_{op_type.name.lower()}_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        data_type=DataType.INT,  # Default to INT, needs type inference
                        bit_width=32
                    )
                    
                    # Add to current function's local vars
                    if self.current_function:
                        self.current_function.local_vars[tmp_var.name] = tmp_var
                    
                    # Create the operation
                    binop = IROperation(
                        name=f"{op_type.name.lower()}_op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=op_type,
                        operands=[left_operand, right_operand],
                        result=tmp_var
                    )
                    
                    # Note: The operation is not added to a block here since we're just
                    # processing the expression. The caller will need to add this to an instruction.
                    
                    # Return the temporary variable
                    return binop
            
        elif isinstance(node, ast.UnaryOp):
            # Unary operation (e.g., -a, ~b)
            operand = self._process_expression(node.operand)
            
            if operand:
                # Get operation type from unaryop_map
                op_mapper = self.unaryop_map.get(type(node.op))
                
                if callable(op_mapper):
                    # This is a function (like the UAdd no-op function)
                    return op_mapper(operand)
                elif op_mapper:
                    # Create a temporary variable for the result
                    tmp_var = IRVariable(
                        name=f"tmp_{op_mapper.name.lower()}_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        data_type=DataType.INT,
                        bit_width=32
                    )
                    
                    # Add to current function's local vars
                    if self.current_function:
                        self.current_function.local_vars[tmp_var.name] = tmp_var
                    
                    # Create the operation
                    unop = IROperation(
                        name=f"{op_mapper.name.lower()}_op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=op_mapper,
                        operands=[operand],
                        result=tmp_var
                    )
                    
                    return unop
            
        elif isinstance(node, ast.Compare):
            # Comparison operation (e.g., a < b, c == d)
            if len(node.ops) == 1 and len(node.comparators) == 1:
                left_operand = self._process_expression(node.left)
                right_operand = self._process_expression(node.comparators[0])
                
                if left_operand and right_operand:
                    # Get operation type from cmpop_map
                    op_type = self.cmpop_map.get(type(node.ops[0]))
                    if op_type:
                        # Create a temporary variable for the result
                        tmp_var = IRVariable(
                            name=f"tmp_{op_type.name.lower()}_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            data_type=DataType.BOOL,  # Comparison results are boolean
                            bit_width=1
                        )
                        
                        # Add to current function's local vars
                        if self.current_function:
                            self.current_function.local_vars[tmp_var.name] = tmp_var
                        
                        # Create the operation
                        cmpop = IROperation(
                            name=f"{op_type.name.lower()}_op_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            op_type=op_type,
                            operands=[left_operand, right_operand],
                            result=tmp_var
                        )
                        
                        return cmpop
        
        elif isinstance(node, ast.BoolOp):
            # Boolean operation (and, or)
            if len(node.values) >= 2:
                # Process all operands
                operands = [self._process_expression(value) for value in node.values]
                operands = [op for op in operands if op is not None]
                
                if len(operands) >= 2:
                    # Get operation type from boolop_map
                    op_type = self.boolop_map.get(type(node.op))
                    if op_type:
                        # Create a temporary variable for the result
                        tmp_var = IRVariable(
                            name=f"tmp_{op_type.name.lower()}_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            data_type=DataType.BOOL,
                            bit_width=1
                        )
                        
                        # Add to current function's local vars
                        if self.current_function:
                            self.current_function.local_vars[tmp_var.name] = tmp_var
                        
                        # For multiple values, create a chain of operations
                        result = operands[0]
                        for i in range(1, len(operands)):
                            result_var = tmp_var if i == len(operands) - 1 else IRVariable(
                                name=f"tmp_{op_type.name.lower()}_{i}_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                data_type=DataType.BOOL,
                                bit_width=1
                            )
                            
                            if i < len(operands) - 1 and self.current_function:
                                self.current_function.local_vars[result_var.name] = result_var
                            
                            boolop = IROperation(
                                name=f"{op_type.name.lower()}_op_{i}_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                op_type=op_type,
                                operands=[result, operands[i]],
                                result=result_var
                            )
                            
                            result = result_var
                        
                        return boolop
        
        elif isinstance(node, ast.Call):
            # Function call
            if isinstance(node.func, ast.Name):
                # Simple function call (e.g., foo(a, b))
                func_name = node.func.id
                
                # Process arguments
                args = [self._process_expression(arg) for arg in node.args]
                args = [arg for arg in args if arg is not None]
                
                # Create a temporary variable for the result
                tmp_var = IRVariable(
                    name=f"tmp_call_{func_name}_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,  # Default to INT, needs type inference
                    bit_width=32
                )
                
                # Add to current function's local vars
                if self.current_function:
                    self.current_function.local_vars[tmp_var.name] = tmp_var
                
                # Create the call operation
                call_op = IROperation(
                    name=f"call_{func_name}_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    op_type=OperationType.CALL,
                    operands=args,
                    result=tmp_var
                )
                
                # Store function name for later analysis
                call_op.function_name = func_name
                
                return call_op
        
        elif isinstance(node, ast.Subscript):
            # Array access (e.g., a[i])
            value = self._process_expression(node.value)
            
            if value:
                # Process index
                if isinstance(node.slice, ast.Index):  # Python 3.8 and earlier
                    index = self._process_expression(node.slice.value)
                else:  # Python 3.9+
                    index = self._process_expression(node.slice)
                
                if index:
                    # Create a temporary variable for the result
                    tmp_var = IRVariable(
                        name=f"tmp_load_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        data_type=DataType.INT,  # Default to INT, needs type inference
                        bit_width=32
                    )
                    
                    # Add to current function's local vars
                    if self.current_function:
                        self.current_function.local_vars[tmp_var.name] = tmp_var
                    
                    # Create the load operation
                    load_op = IROperation(
                        name=f"load_op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=OperationType.LOAD,
                        operands=[value, index],
                        result=tmp_var
                    )
                    
                    return load_op
        
        # For unsupported expressions, return None
        return None
    
    def _process_aug_assign(self, node: ast.AugAssign, block: IRBlock) -> None:
        """Process an augmented assignment statement."""
        # Convert AugAssign to a regular assignment with a binary operation
        target = node.target
        if isinstance(target, ast.Name):
            # Get or create target variable
            name = target.id
            if name not in self.var_map:
                var = IRVariable(
                    name=name,
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,  # Default to INT, needs type inference
                    bit_width=32,  # Default to 32 bits
                )
                self.var_map[name] = var
                if self.current_function:
                    self.current_function.local_vars[name] = var
            
            # Create instruction
            instr = IRInstruction(
                name=f"aug_assign_{self._get_next_id()}",
                node_id=self._get_next_id()
            )
            
            # Determine operation type based on the operator
            op_type = None
            if isinstance(node.op, ast.Add):
                op_type = OperationType.ADD
            elif isinstance(node.op, ast.Sub):
                op_type = OperationType.SUB
            elif isinstance(node.op, ast.Mult):
                op_type = OperationType.MUL
            elif isinstance(node.op, ast.Div):
                op_type = OperationType.DIV
            elif isinstance(node.op, ast.Mod):
                op_type = OperationType.MOD
            elif isinstance(node.op, ast.Pow):
                op_type = OperationType.POW
            elif isinstance(node.op, ast.LShift):
                op_type = OperationType.LSHIFT
            elif isinstance(node.op, ast.RShift):
                op_type = OperationType.RSHIFT
            elif isinstance(node.op, ast.BitOr):
                op_type = OperationType.BIT_OR
            elif isinstance(node.op, ast.BitAnd):
                op_type = OperationType.BIT_AND
            elif isinstance(node.op, ast.BitXor):
                op_type = OperationType.BIT_XOR
            elif isinstance(node.op, ast.MatMult):
                # Matrix multiplication is not directly supported in hardware
                # For now, treat it as regular multiplication
                op_type = OperationType.MUL
            
            if op_type:
                # Process the right-hand side value
                # Special handling for function call expressions
                right_operand = None
                if isinstance(node.value, ast.Call):
                    # Create function call operation
                    call_op = self._process_expression(node.value)
                    if call_op and isinstance(call_op, IROperation) and call_op.op_type == OperationType.CALL:
                        # Add the call operation to the instruction
                        instr.operations.append(call_op)
                        right_operand = call_op.result
                else:
                    # Process normal expressions
                    if isinstance(node.value, ast.Constant):
                        # Create constant
                        right_operand = IRConstant(
                            name=f"const_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            data_type=DataType.INT,  # Default to INT
                            value=node.value.value,
                            bit_width=32
                        )
                    elif isinstance(node.value, ast.Name):
                        # Variable reference
                        var_name = node.value.id
                        if var_name in self.var_map:
                            right_operand = self.var_map[var_name]
                    else:
                        # For other expression types, try to process them
                        right_operand = self._process_expression(node.value)
                
                if right_operand:
                    # Create operation
                    operation = IROperation(
                        name=f"op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=op_type,
                        operands=[self.var_map[name], right_operand],  # Current value and RHS
                        result=self.var_map[name]  # Result goes back to the same variable
                    )
                    
                    instr.operations.append(operation)
                    block.instructions.append(instr)
            # Handle array element augmented assignment (like C[i][j] += x * wt)
            elif isinstance(target, ast.Subscript):
                logger.debug(f"Augmented assignment target is array element")
                
                # Special handling for matrix operations (2D array access: C[i][j])
                if isinstance(target.value, ast.Subscript) and isinstance(target.value.value, ast.Name):
                    # This is C[i][j] += ... pattern
                    array_name = target.value.value.id
                    logger.debug(f"Processing 2D array augmented assignment: {array_name}[...][...] += ...")
                    
                    # 1. Create instruction for this operation
                    instr = IRInstruction(
                        name=f"array_aug_assign_{self._get_next_id()}",
                        node_id=self._get_next_id()
                    )
                    
                    # 2. Process the right side of the augmented assignment
                    right_op = None
                    if isinstance(node.value, ast.BinOp):
                        # This is likely the C[i][j] += x * wt pattern
                        logger.debug(f"Right side is binary operation: {ast.dump(node.value)}")
                        
                        if isinstance(node.value.op, ast.Mult):
                            # Create multiplication operation
                            left = self._process_expression(node.value.left)
                            right = self._process_expression(node.value.right)
                            
                            if left and right:
                                # Create temporary variable for multiplication result
                                tmp_var = IRVariable(
                                    name=f"mul_tmp_{self._get_next_id()}",
                                    node_id=self._get_next_id(),
                                    data_type=DataType.INT,
                                    bit_width=32
                                )
                                
                                # Add to function locals
                                if self.current_function:
                                    self.current_function.local_vars[tmp_var.name] = tmp_var
                                
                                # Create multiplication operation
                                mul_op = IROperation(
                                    name=f"mul_op_{self._get_next_id()}",
                                    node_id=self._get_next_id(),
                                    op_type=OperationType.MUL,
                                    operands=[left, right],
                                    result=tmp_var
                                )
                                
                                instr.operations.append(mul_op)
                                right_op = tmp_var
                                logger.debug(f"Created multiplication operation for right side")
                        
                        elif isinstance(node.value, ast.Call):
                            # Function call operation
                            call_op = self._process_expression(node.value)
                            if call_op and isinstance(call_op, IROperation) and call_op.op_type == OperationType.CALL:
                                instr.operations.append(call_op)
                                right_op = call_op.result
                                logger.debug(f"Created function call operation for right side")
                        
                        elif isinstance(node.value, ast.Name) or isinstance(node.value, ast.Constant):
                            # Simple variable or constant
                            right_op = self._process_expression(node.value)
                            
                        if right_op:
                            # 3. Need to load current value from array
                            # First, get or create array variable
                            if array_name not in self.var_map:
                                logger.debug(f"Creating new array variable: {array_name}")
                                array_var = IRVariable(
                                    name=array_name,
                                    node_id=self._get_next_id(),
                                    data_type=DataType.ARRAY,
                                    bit_width=32,
                                    memory_size=128*128  # Default size estimate
                                )
                                self.var_map[array_name] = array_var
                                if self.current_function:
                                    self.current_function.local_vars[array_name] = array_var
                            
                            # Create temporary variable for current array value
                            current_val_var = IRVariable(
                                name=f"array_current_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                data_type=DataType.INT,
                                bit_width=32
                            )
                            
                            # Add to function locals
                            if self.current_function:
                                self.current_function.local_vars[current_val_var.name] = current_val_var
                            
                            # Create load operation
                            load_op = IROperation(
                                name=f"load_op_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                op_type=OperationType.LOAD,
                                operands=[self.var_map[array_name]],
                                result=current_val_var
                            )
                            instr.operations.append(load_op)
                            logger.debug(f"Created load operation for current array value")
                            
                            # 4. Create addition operation
                            result_var = IRVariable(
                                name=f"add_result_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                data_type=DataType.INT,
                                bit_width=32
                            )
                            
                            # Add to function locals
                            if self.current_function:
                                self.current_function.local_vars[result_var.name] = result_var
                            
                            # Create add operation (current value + right operand)
                            add_op = IROperation(
                                name=f"add_op_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                op_type=OperationType.ADD,
                                operands=[current_val_var, right_op],
                                result=result_var
                            )
                            instr.operations.append(add_op)
                            logger.debug(f"Created addition operation for augmented assignment")
                            
                            # 5. Store the result back to the array
                            store_op = IROperation(
                                name=f"store_op_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                op_type=OperationType.STORE,
                                operands=[result_var, self.var_map[array_name]],
                                result=None
                            )
                            instr.operations.append(store_op)
                            logger.debug(f"Created store operation for updated array value")
                            
                            # Add instruction to block
                            block.instructions.append(instr)
                            logger.debug(f"Added instruction with {len(instr.operations)} operations to block")
                            
                        else:
                            logger.warning(f"Failed to process right side of augmented assignment")
                    else:
                        logger.warning(f"Unsupported array access pattern in augmented assignment")
                else:
                    # Use the original implementation for simple variable += value cases
                    # Original code here...
                    pass
    
    def _process_if(self, node: ast.If, current_block: IRBlock,
                  func: IRFunction) -> IRBlock:
        """Process an if statement."""
        # Create blocks for the if statement
        cond_block = current_block
        
        then_block = IRBlock(
            name=f"if_then_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(then_block)
        
        else_block = None
        if node.orelse:
            else_block = IRBlock(
                name=f"if_else_{self._get_next_id()}",
                node_id=self._get_next_id()
            )
            func.blocks.append(else_block)
        
        merge_block = IRBlock(
            name=f"if_merge_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(merge_block)
        
        # Connect blocks
        cond_block.successors.append(then_block)
        then_block.predecessors.append(cond_block)
        
        if else_block:
            cond_block.successors.append(else_block)
            else_block.predecessors.append(cond_block)
            else_block.successors.append(merge_block)
            merge_block.predecessors.append(else_block)
        else:
            cond_block.successors.append(merge_block)
            merge_block.predecessors.append(cond_block)
        
        then_block.successors.append(merge_block)
        merge_block.predecessors.append(then_block)
        
        # Process the condition (placeholder)
        condition_instr = IRInstruction(
            name=f"if_cond_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        cond_block.instructions.append(condition_instr)
        
        # Process then block
        current_then_block = then_block
        for stmt in node.body:
            current_then_block = self._process_statement(stmt, current_then_block, func)
        
        # Process else block if it exists
        if else_block and node.orelse:
            current_else_block = else_block
            for stmt in node.orelse:
                current_else_block = self._process_statement(stmt, current_else_block, func)
        
        return merge_block
    
    def _process_while(self, node: ast.While, current_block: IRBlock,
                      func: IRFunction) -> IRBlock:
        """Process a while statement."""
        # Create blocks for the while loop
        header_block = IRBlock(
            name=f"while_header_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(header_block)
        
        body_block = IRBlock(
            name=f"while_body_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(body_block)
        
        exit_block = IRBlock(
            name=f"while_exit_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(exit_block)
        
        # Connect blocks
        current_block.successors.append(header_block)
        header_block.predecessors.append(current_block)
        
        header_block.successors.append(body_block)
        body_block.predecessors.append(header_block)
        
        header_block.successors.append(exit_block)
        exit_block.predecessors.append(header_block)
        
        # Mark as loop blocks
        header_block.loop_header = header_block
        header_block.loop_exit = exit_block
        header_block.is_while = True

        # Capture condition variable for backend (e.g. "while b" -> condition_var="b")
        if isinstance(node.test, ast.Name):
            header_block.condition_var = node.test.id
        elif isinstance(node.test, ast.Compare) and len(node.test.ops) == 1:
            # e.g. while a > 0
            if isinstance(node.test.left, ast.Name):
                header_block.condition_var = node.test.left.id
                header_block.condition_op = type(node.test.ops[0]).__name__
        else:
            header_block.condition_var = None

        # Placeholder condition instruction (backend uses condition_var for branching)
        condition_instr = IRInstruction(
            name=f"while_cond_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        header_block.instructions.append(condition_instr)
        
        # Process the body
        current_body_block = body_block
        for stmt in node.body:
            current_body_block = self._process_statement(stmt, current_body_block, func)
        
        # Connect back to header
        current_body_block.successors.append(header_block)
        header_block.predecessors.append(current_body_block)
        
        return exit_block
    
    def _process_for(self, node: ast.For, current_block: IRBlock,
                    func: IRFunction) -> IRBlock:
        """Process a for statement."""
        # Increment loop counter
        self.loop_count += 1
        loop_id = self.loop_count
        
        # Extract any loop pragmas
        pragmas = self._extract_loop_pragmas(node)
        unroll_factor = pragmas.get('unroll', None)  # Default to None (no explicit unrolling)
        
        # Special case for full unrolling (unroll factor 0 means full unrolling)
        if unroll_factor is not None and unroll_factor == 0:
            # For full unrolling, we need to know the loop bounds at compile time
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                # Get range parameters
                args = node.iter.args
                start_val = 0
                end_val = 0
                step_val = 1
                
                # Parse range arguments to get static bounds
                if len(args) == 1 and isinstance(args[0], ast.Constant):
                    # range(end)
                    start_val = 0
                    end_val = args[0].value
                elif len(args) >= 2 and isinstance(args[0], ast.Constant) and isinstance(args[1], ast.Constant):
                    # range(start, end[, step])
                    start_val = args[0].value
                    end_val = args[1].value
                    if len(args) >= 3 and isinstance(args[2], ast.Constant):
                        step_val = args[2].value
                else:
                    # Cannot determine bounds at compile time
                    logger.warning(f"Cannot fully unroll loop {loop_id} - loop bounds not constant")
                    unroll_factor = 8  # Default to a reasonable unroll factor
                
                if unroll_factor == 0:  # If still set to full unrolling
                    # Calculate total iterations
                    iterations = 0
                    if step_val > 0 and start_val < end_val:
                        iterations = (end_val - start_val + step_val - 1) // step_val
                    elif step_val < 0 and start_val > end_val:
                        iterations = (start_val - end_val - step_val - 1) // -step_val
                    
                    if iterations > 0:
                        unroll_factor = iterations  # Set unroll factor to total iterations
                        logger.info(f"Full unrolling of loop {loop_id} with {iterations} iterations")
                    else:
                        unroll_factor = 1  # Default if no iterations
            else:
                # Non-range loop - cannot fully unroll
                logger.warning(f"Cannot fully unroll non-range loop {loop_id}")
                unroll_factor = 4  # Default to a reasonable unroll factor
        
        # Create blocks for the for loop
        init_block = current_block
        header_block = IRBlock(
            name=f"for_header_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(header_block)
        
        body_block = IRBlock(
            name=f"for_body_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(body_block)
        
        update_block = IRBlock(
            name=f"for_update_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(update_block)
        
        exit_block = IRBlock(
            name=f"for_exit_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        func.blocks.append(exit_block)
        
        # Connect blocks
        init_block.successors.append(header_block)
        header_block.predecessors.append(init_block)
        
        header_block.successors.append(body_block)
        body_block.predecessors.append(header_block)
        
        body_block.successors.append(update_block)
        update_block.predecessors.append(body_block)
        
        update_block.successors.append(header_block)
        header_block.predecessors.append(update_block)
        
        header_block.successors.append(exit_block)
        exit_block.predecessors.append(header_block)
        
        # Mark as loop blocks
        header_block.loop_header = header_block
        header_block.loop_exit = exit_block
        
        # Store unroll factor in the header block ONLY if explicitly specified
        if unroll_factor is not None:
            header_block.unroll_factor = unroll_factor
            header_block.unroll = True  # Mark that unrolling was explicitly requested
            if unroll_factor == 0:
                header_block.full_unroll = True
        # Store pragma information for potential use by optimizer (but don't auto-unroll)
        if pragmas:
            header_block.pragmas = pragmas
        
        # Process the loop variable
        if isinstance(node.target, ast.Name):
            loop_var_name = node.target.id
            if loop_var_name not in self.var_map:
                # Create loop variable
                loop_var = IRVariable(
                    name=loop_var_name,
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,  # Default to INT
                    bit_width=32
                )
                self.var_map[loop_var_name] = loop_var
                if self.current_function:
                    self.current_function.local_vars[loop_var_name] = loop_var
        
        # Process the iterable
        # Here we'll focus on handling range() calls
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
            # Get range parameters
            args = node.iter.args
            start_value = None
            end_value = None
            step_value = None
            
            # Variables to track iterations
            start_val = 0
            end_val = 10  # Default
            step_val = 1
            
            # Store the original AST for these values for later analysis
            start_expr = None
            end_expr = None
            step_expr = None
            
            # Parse range arguments
            if len(args) == 1:
                # range(end)
                start_val = 0
                start_expr = ast.Constant(value=0)
                end_expr = args[0]
                step_val = 1
                step_expr = ast.Constant(value=1)
                
                # Try to evaluate end_val if it's a constant or len() call
                if isinstance(args[0], ast.Constant):
                    end_val = args[0].value
                elif isinstance(args[0], ast.Call) and isinstance(args[0].func, ast.Name) and args[0].func.id == 'len':
                    # Handle len(array_param) calls
                    if (len(args[0].args) > 0 and isinstance(args[0].args[0], ast.Name)):
                        array_name = args[0].args[0].id
                        # Check if this is an array parameter and use its actual size
                        if array_name in self.var_map:
                            array_var = self.var_map[array_name]
                            if hasattr(array_var, 'data_type') and array_var.data_type == DataType.ARRAY:
                                # For array parameters, we need to use the actual size from the testbench
                                # Mark this as a dynamic array size that will be resolved at runtime
                                end_val = f"len({array_name})"  # Special marker for dynamic size
                                header_block.dynamic_array_size = array_name
                                logger.info(f"Loop {loop_id} uses dynamic array size: len({array_name})")
                            else:
                                end_val = 10  # Default for non-array variables
                        else:
                            end_val = 10  # Default if variable not found
            
            elif len(args) >= 2:
                # range(start, end[, step])
                start_expr = args[0]
                end_expr = args[1]
                
                # Try to evaluate start_val if it's a constant
                if isinstance(args[0], ast.Constant):
                    start_val = args[0].value
                
                # Try to evaluate end_val if it's a constant or len() call
                if isinstance(args[1], ast.Constant):
                    end_val = args[1].value
                elif isinstance(args[1], ast.Call) and isinstance(args[1].func, ast.Name) and args[1].func.id == 'len':
                    # Handle len(array_param) calls
                    if (len(args[1].args) > 0 and isinstance(args[1].args[0], ast.Name)):
                        array_name = args[1].args[0].id
                        # Check if this is an array parameter and use its actual size
                        if array_name in self.var_map:
                            array_var = self.var_map[array_name]
                            if hasattr(array_var, 'data_type') and array_var.data_type == DataType.ARRAY:
                                # For array parameters, we need to use the actual size from the testbench
                                # Mark this as a dynamic array size that will be resolved at runtime
                                end_val = f"len({array_name})"  # Special marker for dynamic size
                                header_block.dynamic_array_size = array_name
                                logger.info(f"Loop {loop_id} uses dynamic array size: len({array_name})")
                            else:
                                end_val = 10  # Default for non-array variables
                        else:
                            end_val = 10  # Default if variable not found
                
                if len(args) >= 3:
                    step_expr = args[2]
                    # Try to evaluate step_val if it's a constant
                    if isinstance(args[2], ast.Constant):
                        step_val = args[2].value
                else:
                    step_val = 1
                    step_expr = ast.Constant(value=1)
            
            # Store AST expressions as metadata to facilitate future DFG analysis
            header_block.range_start_expr = start_expr
            header_block.range_end_expr = end_expr
            header_block.range_step_expr = step_expr
            
            # Store the variable names to aid in advanced analysis
            if isinstance(start_expr, ast.Name):
                header_block.range_start_var = start_expr.id
            if isinstance(end_expr, ast.Name):
                header_block.range_end_var = end_expr.id
            if isinstance(step_expr, ast.Name):
                header_block.range_step_var = step_expr.id
            
            # For dynamic range bounds (like variable names), store references to actual variables 
            if isinstance(start_expr, ast.Name) and start_expr.id in self.var_map:
                header_block.range_start_ref = self.var_map[start_expr.id]
            if isinstance(end_expr, ast.Name) and end_expr.id in self.var_map:
                header_block.range_end_ref = self.var_map[end_expr.id]
            if isinstance(step_expr, ast.Name) and step_expr.id in self.var_map:
                header_block.range_step_ref = self.var_map[step_expr.id]
            
            # Calculate number of iterations for constant ranges
            iterations = 0
            if isinstance(start_val, (int, float)) and isinstance(end_val, (int, float)) and isinstance(step_val, (int, float)):
                if step_val > 0 and start_val < end_val:
                    iterations = max(0, (end_val - start_val + step_val - 1) // step_val)
                elif step_val < 0 and start_val > end_val:
                    iterations = max(0, (start_val - end_val - step_val - 1) // -step_val)
                
                # Store iterations in loop header for schedulers to use
                header_block.loop_iterations = iterations
                self.total_iterations += iterations
                
                # Track original range bounds
                header_block.range_start = start_val
                header_block.range_end = end_val
                header_block.range_step = step_val
                
                # If we have a loop unroll factor, adjust the iteration count
                if unroll_factor is not None and unroll_factor > 1:
                    # Calculate effective iterations after unrolling
                    effective_iterations = iterations // unroll_factor
                    if iterations % unroll_factor != 0:
                        effective_iterations += 1  # Need an extra iteration for remainder
                    
                    # Update iterations for the scheduler
                    header_block.effective_iterations = effective_iterations
                    header_block.original_iterations = iterations
                    
                    logger.info(f"Loop {loop_id} with unroll factor {unroll_factor}: "
                               f"original={iterations} iterations, effective={effective_iterations} iterations")
                
                func_name = self.current_function.name if self.current_function else "unknown"
                logger.info(f"Loop {loop_id} in function '{func_name}': range({start_val}, {end_val}, {step_val}) with {iterations} iterations")
            elif hasattr(header_block, 'dynamic_array_size'):
                # Handle dynamic array size loops
                array_name = header_block.dynamic_array_size
                # Mark this loop as having dynamic bounds
                header_block.loop_iterations = "dynamic"  # Special marker
                header_block.range_start = start_val if isinstance(start_val, (int, float)) else 0
                header_block.range_end = f"len({array_name})"  # Dynamic end
                header_block.range_step = step_val if isinstance(step_val, (int, float)) else 1
                
                # For scheduling purposes, use a reasonable default but mark as dynamic
                self.total_iterations += 16  # Conservative estimate for dynamic arrays
                func_name = self.current_function.name if self.current_function else "unknown"
                logger.info(f"Loop {loop_id} in function '{func_name}': dynamic range(0, len({array_name}), 1) - will use actual array size at runtime")
            else:
                # For non-constant bounds, we'll try more advanced analysis
                # We store what we know for later analysis
                header_block.range_start = start_val if isinstance(start_val, (int, float)) else None
                header_block.range_end = end_val if isinstance(end_val, (int, float)) else None
                header_block.range_step = step_val if isinstance(step_val, (int, float)) else None
                
                # Store a default value for unknown iteration counts
                header_block.loop_iterations = 10  # Default value
                self.total_iterations += 10
                logger.info(f"Loop {loop_id} with non-constant range parameters - using default 10 iterations")
            
            # Create initialization instruction
            init_instr = IRInstruction(
                name=f"for_init_{self._get_next_id()}",
                node_id=self._get_next_id()
            )
            
            # Create start value constant or reference
            if isinstance(start_expr, ast.Constant):
                start_value = IRConstant(
                    name=f"range_start_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=start_val,
                    bit_width=32
                )
            elif isinstance(start_expr, ast.Name) and start_expr.id in self.var_map:
                start_value = self.var_map[start_expr.id]
            else:
                # For complex expressions, use a default value
                start_value = IRConstant(
                    name=f"range_start_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=start_val,
                    bit_width=32
                )
            
            init_op = IROperation(
                name=f"init_op_{self._get_next_id()}",
                node_id=self._get_next_id(),
                op_type=OperationType.ASSIGN,
                operands=[start_value],
                result=self.var_map[loop_var_name]
            )
            
            init_instr.operations.append(init_op)
            init_block.instructions.append(init_instr)
            
            # Create condition instruction
            cond_instr = IRInstruction(
                name=f"for_cond_{self._get_next_id()}",
                node_id=self._get_next_id()
            )
            
            # Create end value constant or reference
            if isinstance(end_expr, ast.Constant):
                end_value = IRConstant(
                    name=f"range_end_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=end_val,
                    bit_width=32
                )
            elif isinstance(end_expr, ast.Name) and end_expr.id in self.var_map:
                end_value = self.var_map[end_expr.id]
            else:
                # For complex expressions, use a default value
                end_value = IRConstant(
                    name=f"range_end_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=end_val,
                    bit_width=32
                )
            
            cond_op = IROperation(
                name=f"cond_op_{self._get_next_id()}",
                node_id=self._get_next_id(),
                op_type=OperationType.LT,
                operands=[self.var_map[loop_var_name], end_value],
                result=None  # Condition doesn't produce a value
            )
            
            cond_instr.operations.append(cond_op)
            header_block.instructions.append(cond_instr)
            
            # Create update instruction
            update_instr = IRInstruction(
                name=f"for_update_{self._get_next_id()}",
                node_id=self._get_next_id()
            )
            
            # Create step value constant or reference
            if isinstance(step_expr, ast.Constant):
                step_value = IRConstant(
                    name=f"range_step_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=step_val,
                    bit_width=32
                )
            elif isinstance(step_expr, ast.Name) and step_expr.id in self.var_map:
                step_value = self.var_map[step_expr.id]
            else:
                # For complex expressions, use a default value
                step_value = IRConstant(
                    name=f"range_step_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=step_val,
                    bit_width=32
                )
            
            # For unrolled loops, we update by step * unroll_factor in each iteration
            if unroll_factor is not None and unroll_factor > 1:
                # Create a constant for the unrolled step
                unrolled_step_val = step_val * unroll_factor
                step_value = IRConstant(
                    name=f"unrolled_step_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,
                    value=unrolled_step_val,
                    bit_width=32
                )
                header_block.unrolled_step = unrolled_step_val
                logger.info(f"Loop {loop_id} unrolled with step size {unrolled_step_val}")
            
            # Create a temporary variable for the updated value
            tmp_var = IRVariable(
                name=f"for_tmp_{self._get_next_id()}",
                node_id=self._get_next_id(),
                data_type=DataType.INT,
                bit_width=32
            )
            
            # Add temporary variable to local vars
            if self.current_function:
                self.current_function.local_vars[tmp_var.name] = tmp_var
            
            # Step operation (var + step)
            add_op = IROperation(
                name=f"add_op_{self._get_next_id()}",
                node_id=self._get_next_id(),
                op_type=OperationType.ADD,
                operands=[self.var_map[loop_var_name], step_value],
                result=tmp_var
            )
            
            # Assign the updated value to the loop variable
            assign_op = IROperation(
                name=f"assign_op_{self._get_next_id()}",
                node_id=self._get_next_id(),
                op_type=OperationType.ASSIGN,
                operands=[tmp_var],
                result=self.var_map[loop_var_name]
            )
            
            update_instr.operations.append(add_op)
            update_instr.operations.append(assign_op)
            update_block.instructions.append(update_instr)
        else:
            # Non-range iterable - just make a note for later analysis
            logger.info(f"Loop {loop_id} with non-range iterable - iterations unknown at compile time")
        
        # Process the body
        current_body_block = body_block
        
        # Regular case - process the body
        for stmt in node.body:
            current_body_block = self._process_statement(stmt, current_body_block, func)
            
        # If we're unrolling, we need to record that in the body block
        if unroll_factor is not None and unroll_factor > 1:
            # Mark body block for unrolled implementation
            body_block.unroll_factor = unroll_factor
            logger.info(f"Marked loop body block for unrolling with factor {unroll_factor}")
            
        # Connect back to the update block
        current_body_block.successors.append(update_block)
        update_block.predecessors.append(current_body_block)
        
        return exit_block
    
    def _process_return(self, node: ast.Return, block: IRBlock) -> None:
        """Process a return statement."""
        # Create return instruction
        return_instr = IRInstruction(
            name=f"return_{self._get_next_id()}",
            node_id=self._get_next_id()
        )
        block.instructions.append(return_instr)
        
        # If there is a return value, process it
        if node.value:
            # Process the return value expression
            if isinstance(node.value, ast.Name):
                # Variable reference
                var_name = node.value.id
                if var_name in self.var_map:
                    var = self.var_map[var_name]
                    
                    # Create a return operation
                    return_op = IROperation(
                        name=f"return_op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=OperationType.RETURN,
                        operands=[var],
                        result=None  # Return operations don't have results
                    )
                    
                    return_instr.operations.append(return_op)
            
            elif isinstance(node.value, ast.Constant):
                # Constant value
                const = IRConstant(
                    name=f"return_const_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    data_type=DataType.INT,  # Default to INT
                    value=node.value.value,
                    bit_width=32
                )
                
                # Create a return operation
                return_op = IROperation(
                    name=f"return_op_{self._get_next_id()}",
                    node_id=self._get_next_id(),
                    op_type=OperationType.RETURN,
                    operands=[const],
                    result=None  # Return operations don't have results
                )
                
                return_instr.operations.append(return_op)
            
            elif isinstance(node.value, ast.Call):
                # Function call in return statement
                call_op = self._process_expression(node.value)
                if call_op and isinstance(call_op, IROperation) and call_op.op_type == OperationType.CALL:
                    # Add the call operation to the instruction
                    return_instr.operations.append(call_op)
                    
                    # Create a return operation with the call result
                    return_op = IROperation(
                        name=f"return_op_{self._get_next_id()}",
                        node_id=self._get_next_id(),
                        op_type=OperationType.RETURN,
                        operands=[call_op.result],
                        result=None  # Return operations don't have results
                    )
                    
                    return_instr.operations.append(return_op)
            
            else:
                # Process other expression types
                expr_result = self._process_expression(node.value)
                if expr_result:
                    if isinstance(expr_result, IROperation):
                        # Add the operation to the instruction
                        return_instr.operations.append(expr_result)
                        
                        # Use its result for the return
                        if hasattr(expr_result, 'result') and expr_result.result:
                            return_op = IROperation(
                                name=f"return_op_{self._get_next_id()}",
                                node_id=self._get_next_id(),
                                op_type=OperationType.RETURN,
                                operands=[expr_result.result],
                                result=None
                            )
                            return_instr.operations.append(return_op)
                    
                    elif isinstance(expr_result, (IRConstant, IRVariable)):
                        # Direct return of constant or variable
                        return_op = IROperation(
                            name=f"return_op_{self._get_next_id()}",
                            node_id=self._get_next_id(),
                            op_type=OperationType.RETURN,
                            operands=[expr_result],
                            result=None
                        )
                        return_instr.operations.append(return_op)
    
    def _extract_loop_pragmas(self, node):
        """Extract pragma annotations from comments before a loop statement."""
        pragmas = {}
        
        # Get line number of the loop
        line_num = getattr(node, 'lineno', None)
        if line_num is None or line_num <= 1:
            return pragmas
        
        # Check if we have access to source code
        if not self.source_lines:
            return pragmas
        
        # Look for pragma comments in the lines before the loop
        for i in range(max(0, line_num - 3), line_num):
            if i >= len(self.source_lines):
                break
            
            line = self.source_lines[i].strip()
            if line.startswith('#') and 'pragma' in line.lower():
                # Extract pragma directive
                pragma_parts = line.lower().split('pragma', 1)
                if len(pragma_parts) < 2:
                    continue  # Skip if 'pragma' not found (should not happen due to the check above)
                
                pragma_line = pragma_parts[1].strip()
                
                # Handle various pragma formats
                if 'unroll' in pragma_line.lower():
                    # Format 1: #pragma unroll <factor>
                    parts = pragma_line.split()
                    if len(parts) >= 2 and parts[0].lower() == 'unroll':
                        factor_str = parts[1]
                        try:
                            unroll_factor = int(factor_str)
                            pragmas['unroll'] = unroll_factor
                            logger.info(f"Found unroll pragma with factor {unroll_factor}")
                        except ValueError:
                            # If it's not a number but just 'unroll', use default factor of full unrolling
                            if parts[0].lower() == 'unroll' and len(parts) == 1:
                                pragmas['unroll'] = 0  # 0 means full unrolling
                                logger.info(f"Found full unroll pragma")
                    
                    # Format 2: #pragma hls unroll factor=<factor>
                    elif 'factor=' in pragma_line:
                        try:
                            factor_parts = pragma_line.split('factor=', 1)
                            if len(factor_parts) < 2:
                                continue
                                
                            factor_part = factor_parts[1].strip()
                            # Extract the numeric part
                            factor_str = ''
                            for c in factor_part:
                                if c.isdigit():
                                    factor_str += c
                                else:
                                    break
                            
                            if factor_str:
                                unroll_factor = int(factor_str)
                                pragmas['unroll'] = unroll_factor
                                logger.info(f"Found unroll pragma with factor {unroll_factor}")
                        except (ValueError, IndexError):
                            pass
                    
                    # Format 3: #pragma hls unroll (with no factor, means full unrolling)
                    elif 'hls unroll' in pragma_line.lower() and 'factor=' not in pragma_line:
                        pragmas['unroll'] = 0  # 0 means full unrolling
                        logger.info(f"Found full unroll pragma")
                
                # Handle other pragma types like pipeline, etc.
                elif 'pipeline' in pragma_line.lower():
                    pragmas['pipeline'] = True
                    
                    # Extract pipeline II (initiation interval) if specified
                    if 'ii=' in pragma_line.lower():
                        try:
                            ii_parts = pragma_line.lower().split('ii=', 1)
                            if len(ii_parts) < 2:
                                continue
                                
                            ii_part = ii_parts[1].strip()
                            ii_str = ''
                            for c in ii_part:
                                if c.isdigit():
                                    ii_str += c
                                else:
                                    break
                            
                            if ii_str:
                                pipeline_ii = int(ii_str)
                                pragmas['pipeline_ii'] = pipeline_ii
                        except (ValueError, IndexError):
                            pragmas['pipeline_ii'] = 1  # Default II=1
                    
                    logger.info(f"Found pipeline pragma with II={pragmas.get('pipeline_ii', 1)}")
        
        return pragmas

    def parse_function(self, func_def, source_code=None):
        """Parse a function definition."""
        # Store source lines for pragma extraction
        if source_code:
            self.source_lines = source_code.splitlines()
        
        # ... rest of existing code ... 

    def _analyze_pending_memory_sizes(self, func: IRFunction) -> None:
        """Process any pending memory size annotations."""
        if hasattr(func, 'pending_memory_sizes') and func.pending_memory_sizes:
            logger.info(f"Processing {len(func.pending_memory_sizes)} pending memory size annotations")
            for var_name, memory_size in func.pending_memory_sizes.items():
                if var_name in func.local_vars:
                    var = func.local_vars[var_name]
                    if var.data_type != DataType.ARRAY:
                        var.data_type = DataType.ARRAY
                    
                    # Estimate array element count
                    element_size = var.bit_width // 8  # bytes per element
                    if element_size > 0:
                        var.memory_size = max(var.memory_size, memory_size // element_size)
                        logger.info(f"Applied pending memory size to {var_name}: {var.memory_size} elements")

    def _process_streaming_operation(self, pragma, data, array, index):
        """
        Process a streaming operation (FIFO read or write).
        
        Args:
            pragma: StreamingPragma object containing the operation info
            data: The data being read or written (IRVariable or IRConstant)
            array: The array/FIFO being accessed
            index: The index into the array/FIFO
            
        Returns:
            IROperation for the streaming operation
        """
        operation_type = None
        fifo_name = pragma.name
        
        # Check if this variable is marked as a streaming component
        if not self.current_function:
            return None
            
        # Determine interface type (default is "simple")
        interface_type = "simple"
        if "protocol" in pragma.params:
            interface_type = pragma.params["protocol"]
            
        # Create an operation node for the streaming access
        if pragma.pragma_type == 'fifo_write':
            if interface_type == "axis":
                operation_type = OperationType.AXIS_FIFO_WRITE
            elif interface_type == "axilite":
                operation_type = OperationType.AXILITE_FIFO_WRITE
            else:  # Default to simple interface
                operation_type = OperationType.FIFO_WRITE
        elif pragma.pragma_type == 'fifo_read':
            if interface_type == "axis":
                operation_type = OperationType.AXIS_FIFO_READ
            elif interface_type == "axilite":
                operation_type = OperationType.AXILITE_FIFO_READ
            else:  # Default to simple interface
                operation_type = OperationType.FIFO_READ
        elif pragma.pragma_type == 'crossbar_route':
            operation_type = OperationType.CROSSBAR_ROUTE
        else:
            return None
            
        # Map interface type to the appropriate result signal name
        result_signal_map = {
            "simple": lambda fifo: f"{fifo}_data_out" if operation_type in [OperationType.FIFO_READ, OperationType.FIFO_WRITE] else None,
            "axis": lambda fifo: f"{fifo}_tdata" if operation_type in [OperationType.AXIS_FIFO_READ, OperationType.AXIS_FIFO_WRITE] else None,
            "axilite": lambda fifo: f"{fifo}_rdata" if operation_type == OperationType.AXILITE_FIFO_READ else f"{fifo}_wdata" if operation_type == OperationType.AXILITE_FIFO_WRITE else None
        }
        
        # Map interface type to the appropriate operand signal name
        operand_signal_map = {
            "simple": lambda fifo: f"{fifo}_data_in" if operation_type == OperationType.FIFO_WRITE else f"{fifo}_data_out",
            "axis": lambda fifo: f"{fifo}_tdata",
            "axilite": lambda fifo: f"{fifo}_wdata" if operation_type == OperationType.AXILITE_FIFO_WRITE else f"{fifo}_rdata"
        }
        
        # Determine the signal name for the operation
        signal_func = operand_signal_map.get(interface_type, operand_signal_map["simple"])
        signal_name = signal_func(fifo_name)
            
        # Create the streaming operation
        streaming_op = IROperation(
            name=f"{pragma.pragma_type}_{self._get_next_id()}",
            node_id=self._get_next_id(),
            op_type=operation_type,
            operands=[data, array],  # Data and the FIFO/crossbar
            result=None if operation_type in [OperationType.FIFO_WRITE, OperationType.AXIS_FIFO_WRITE, OperationType.AXILITE_FIFO_WRITE] else data,  # FIFO writes have no result
            fifo_name=fifo_name
        )
        
        # Add interface-specific parameters
        streaming_op.interface_type = interface_type
        
        # If there are additional parameters, add them to the operation
        for key, value in pragma.params.items():
            setattr(streaming_op, key, value)
            
        return streaming_op

    def _process_streaming_components(self, func: IRFunction) -> None:
        """
        Process streaming components for a function.
        
        Args:
            func: Function to process streaming components for
        """
        # First, check if we found any function-level streaming pragmas
        lineno = None
        for line_num, pragmas in self.streaming_pragmas.items():
            if not lineno:
                lineno = line_num
            
            # Check for streaming function pragmas
            for pragma in pragmas:
                if pragma.pragma_type in ['fifo', 'crossbar', 'channel']:
                    # Create a streaming component for this pragma
                    component = StreamingComponent(
                        name=pragma.name,
                        component_type=pragma.pragma_type,
                        params=pragma.params
                    )
                    func.add_streaming_component(component)
                    logger.info(f"Added streaming component: {pragma.pragma_type} '{pragma.name}' to function '{func.name}'")
        
        # If no streaming components were found, return
        if not func.streaming_components:
            return
        
        # Process streaming components
        logger.info(f"Processing streaming components for function {func.name}")
        logger.info(f"Number of streaming components: {len(func.streaming_components)}")
        
        # First, identify variables associated with each streaming component
        for comp_name, component in func.streaming_components.items():
            # Find variables that are used with this component
            for var_name, var in func.local_vars.items():
                if hasattr(var, 'is_stream') and var.is_stream:
                    # This is a streaming variable
                    if not hasattr(component, 'variables'):
                        component.variables = []
                    component.variables.append(var_name)
                    
            # For variables explicitly linked to components
            if hasattr(component, 'linked_variable') and component.linked_variable:
                if not hasattr(component, 'variables'):
                    component.variables = []
                if component.linked_variable not in component.variables:
                    component.variables.append(component.linked_variable)
        
        # Next, identify connections between streaming components
        # This is typically specified using channel pragmas
        for comp_name, component in func.streaming_components.items():
            if component.component_type == 'channel':
                # Get source and destination components if specified
                source = component.source_var
                dest = component.dest_var
                
                # Record connections
                if source and source in func.streaming_components:
                    source_comp = func.streaming_components[source]
                    if not hasattr(source_comp, 'outputs'):
                        source_comp.outputs = []
                    source_comp.outputs.append(comp_name)
                
                if dest and dest in func.streaming_components:
                    dest_comp = func.streaming_components[dest]
                    if not hasattr(dest_comp, 'inputs'):
                        dest_comp.inputs = []
                    dest_comp.inputs.append(comp_name)
        
        # Finally, validate all components and their connections
        for comp_name, component in func.streaming_components.items():
            # Validate FIFO components
            if component.component_type == 'fifo':
                # Make sure depth is specified
                if 'depth' not in component.params:
                    logger.warning(f"FIFO '{comp_name}' does not have a depth specified")
                    component.params['depth'] = 16  # Default depth
            
            # Validate crossbar components
            elif component.component_type == 'crossbar':
                # Make sure inputs and outputs are specified
                if 'inputs' not in component.params:
                    logger.warning(f"Crossbar '{comp_name}' does not have inputs specified")
                    component.params['inputs'] = 2  # Default inputs
                if 'outputs' not in component.params:
                    logger.warning(f"Crossbar '{comp_name}' does not have outputs specified")
                    component.params['outputs'] = 2  # Default outputs
        
        # Log streaming architecture information
        if func.is_streaming_architecture:
            logger.info(f"Function {func.name} implements a streaming architecture")
            logger.info(f"Components: {', '.join(func.streaming_components.keys())}") 