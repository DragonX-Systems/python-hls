"""
Main HLS compiler implementation.
"""

import os
import ast
import logging
from typing import Optional, Dict, Any, List, Union, Tuple, Sequence, Callable

try:
    from cairosvg import svg2png  # For SVG to PNG conversion
except ImportError:
    # Fallback if cairosvg is not available
    svg2png = None

from .frontend import PythonParser
from .ir import IRGenerator
from .optimizer import Optimizer
from .backend import VerilogGenerator, VHDLGenerator, PPAOptimizedVerilogGenerator
from .visualizer import DatapathVisualizer
from .netlist import Netlist
from .tech import TechLibrary
from .hls_engine import ASAPScheduler, ALAPScheduler, ListScheduler, Allocator, Binder
from .verification import RTLVerifier
from .constraints import (
    LatencyConstraint, LatencyViolationError, 
    extract_latency_constraints_from_source, enforce_latency_constraint,
    SemanticValidator, SemanticViolationError, SemanticValidatorConfig,
    EquivalenceChecker, EquivalenceResult, EquivalenceMode,
)

import graphviz
from graphviz import Source
from graphviz import render

# Set up logger
logger = logging.getLogger(__name__)

class HLS:
    """High-Level Synthesis compiler that converts Python to hardware netlists."""

    def __init__(self, optimization_level: int = 1, tech_node: int = 45, 
                 strict_mode: bool = False, deterministic: bool = False,
                 tech_library: Optional[TechLibrary] = None):
        """
        Initialize the HLS compiler.
        
        Args:
            optimization_level: Level of optimization to apply (0-3)
            tech_node: Technology node in nm (e.g., 45, 28, 16, 7)
            strict_mode: If True, enforce semantic rules and latency constraints
            deterministic: If True, use fixed seeds and deterministic ordering for reproducible builds
            tech_library: Optional technology library. Custom resource models
                are used for scheduling and early PPA estimates.
        """
        self.optimization_level = optimization_level
        self.tech_node = tech_node
        self.strict_mode = strict_mode
        self.deterministic = deterministic
        
        # Set random seed for deterministic mode
        if deterministic:
            import random
            random.seed(42)
            # Also set numpy seed if available
            try:
                import numpy as np
                np.random.seed(42)
            except ImportError:
                pass
        
        # Create technology library
        self.tech_library = tech_library or TechLibrary(tech_node=tech_node)
        self.tech_library.set_tech_node(tech_node)
        
        # Create components
        self.parser = PythonParser()
        self.ir_generator = IRGenerator()
        self.optimizer = Optimizer(optimization_level=optimization_level)
        self.verilog_generator = VerilogGenerator()
        self.vhdl_generator = VHDLGenerator()
        self.ppa_verilog_generator = None  # Will be created when needed
        self.visualizer = DatapathVisualizer()
        
        # Scheduling, allocation, and binding
        self.asap_scheduler = ASAPScheduler(self.tech_library)
        self.alap_scheduler = ALAPScheduler(self.tech_library)
        self.list_scheduler = ListScheduler(self.tech_library)
        self.allocator = Allocator(self.tech_library)
        self.binder = Binder()
        
        # RTL verification
        self.rtl_verifier = RTLVerifier()
        
        # Semantic validation (for strict mode)
        self.semantic_validator = SemanticValidator(
            SemanticValidatorConfig(strict=strict_mode)
        )
        
        # Latency constraints (populated from source)
        self.latency_constraints: Dict[str, LatencyConstraint] = {}
        
        # Current state
        self.ast = None
        self.ir = None
        self.optimized_ir = None
        self.scheduled_ir = None
        self.allocated_resources = None
        self.netlist_resources = None
        self.netlist_operations = None
        self.netlist = None
        self.source_file = None

    def compile_torch(self, model: Any, example_inputs: Any = (), target: str = "verilog",
                      output_file: Optional[str] = None, embed_weights: bool = False, **kwargs: Any) -> Any:
        """
        Compile a PyTorch module to a hardware netlist using PyTorch FX qualified lowering.
        
        Args:
            model: A torch.nn.Module instance
            example_inputs: Concrete example tensors for shape propagation
            target: Target hardware description language ("verilog" or "vhdl")
            output_file: Path to write generated RTL
            embed_weights: Whether to embed weights as constant arrays or parameter ports
            
        Returns:
            Tuple of (netlist, synthesis_logs)
        """
        from .frontend.torch_fx import compile_torch_model
        return compile_torch_model(
            model=model,
            example_inputs=example_inputs,
            target=target,
            output_file=output_file,
            opt_level=self.optimization_level,
            tech_node=self.tech_node,
            embed_weights=embed_weights,
            **kwargs,
        )

    def compile(self, source_file: str, target: str = "verilog", debug: bool = False, entry_function: Optional[str] = None, 
                ppa_optimization: bool = False, ppa_objective: str = "area", output_file: Optional[str] = None) -> Any:
        """
        Compile a Python file to a target hardware description language.
        
        Args:
            source_file: Python source file
            target: Target hardware description language
            debug: Whether to enable debug output
            entry_function: Entry function name (optional)
            ppa_optimization: Whether to use PPA-optimized code generation
            ppa_objective: PPA optimization objective ("area", "performance", "power", "balanced")
            output_file: Optional path to write the generated RTL (default: {source_base}.v or .vhd)
            
        Returns:
            Tuple of (netlist, synthesis_logs)
        """
        self.source_file = source_file
        
        # Create log file based on source file name
        base, _ = os.path.splitext(source_file)
        log_file_path = f"{base}_synthesis.log"
        
        # Configure file logger
        file_handler = logging.FileHandler(log_file_path, mode='w')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Add handler to root logger to ensure all modules use the same log file
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        # Also add to our specific logger
        logger.addHandler(file_handler)
        
        # Ensure schedulers and other modules log to the same file
        scheduler_logger = logging.getLogger('python_hls.hls_engine.scheduler')
        scheduler_logger.setLevel(logging.DEBUG)
        scheduler_logger.addHandler(file_handler)
        
        optimizer_logger = logging.getLogger('python_hls.optimizer')
        optimizer_logger.setLevel(logging.DEBUG)
        optimizer_logger.addHandler(file_handler)
        
        # Set the root logger level to ensure messages flow through
        root_logger.setLevel(logging.DEBUG)
        
        try:
            # Log compilation start
            logger.info(f"Starting compilation of {source_file} targeting {target}")
            logger.info(f"Technology node: {self.tech_node} nm")
            logger.info(f"Optimization level: {self.optimization_level}")
            logger.info(f"Strict mode: {self.strict_mode}")
            logger.info(f"Deterministic mode: {self.deterministic}")
            
            # Read source for constraint extraction
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            # Extract latency constraints from source
            logger.info("Extracting latency constraints from source")
            self.latency_constraints = extract_latency_constraints_from_source(source_code)
            if self.latency_constraints:
                for func_name, constraint in self.latency_constraints.items():
                    logger.info(f"  {func_name}: max {constraint.max_cycles} cycles ({constraint.mode} mode)")
            
            # Validate semantics in strict mode
            if self.strict_mode:
                logger.info("Validating semantic rules (strict mode)")
                try:
                    tree = ast.parse(source_code)
                    self.semantic_validator.validate_strict(tree)
                    logger.info("  Semantic validation passed")
                except SemanticViolationError as e:
                    logger.error(f"Semantic validation failed: {e}")
                    raise
            
            # Parse Python source code
            logger.info("Parsing Python source code")
            ast_tree = self.parser.parse_file(source_file, entry_function)
            
            # Generate IR
            logger.info("Generating Intermediate Representation (IR)")
            self.ir_generator = IRGenerator(self.parser)  # Pass parser to access source lines
            self.ir = self.ir_generator.generate(ast_tree)
            
            # Apply memory size information from the source code
            logger.info("Applying memory size information")
            self._apply_memory_sizes()
            
            # Check for optimization hints in pragmas
            logger.info("Processing optimization hints in pragmas")
            self._process_optimization_hints()
            
            # Apply optimizations
            logger.info("Applying optimizations")
            self.optimized_ir = self.optimizer.optimize(self.ir)
            
            # Schedule operations
            logger.info("Scheduling operations")
            self.scheduled_ir = self.asap_scheduler.schedule(self.optimized_ir)
            
            # Allocate resources
            logger.info("Allocating hardware resources")
            self._allocate_resources()
            
            # Generate netlist
            logger.info(f"Generating {target} netlist")
            if ppa_optimization:
                logger.info(f"Using PPA-optimized code generation with {ppa_objective} objective")
                self.netlist = self.generate_ppa_optimized_netlist(target, ppa_objective)
            else:
                self.netlist = self.generate_netlist(target)
            
            # Apply resource area/power to netlist modules (netlist must exist first)
            self._apply_resources_to_modules()
            
            # Log performance metrics
            logger.info("Collecting performance metrics")
            try:
                metrics = self.get_performance_metrics()
                logger.info(f"Area: {metrics['total_area']:.2f} μm²")
                logger.info(f"Power: {metrics['total_power']:.2f} mW")
                logger.info(f"Latency: {metrics['latency_cycles']} cycles")
                logger.info(f"Clock Frequency: {metrics['clock_frequency_mhz']:.2f} MHz")
                logger.info(f"Critical Path: {metrics['critical_path']:.2f} ns")
            except Exception as e:
                logger.warning(f"Error collecting metrics: {str(e)}")
            
            # Enforce latency constraints
            if self.latency_constraints:
                logger.info("Enforcing latency constraints")
                for func_name, constraint in self.latency_constraints.items():
                    if func_name in self.scheduled_ir.functions:
                        func = self.scheduled_ir.functions[func_name]
                        actual_latency = getattr(func, 'total_latency', 0)
                        logger.info(f"  {func_name}: required <= {constraint.max_cycles}, actual = {actual_latency}")
                        
                        if not constraint.validate(actual_latency):
                            error_msg = (
                                f"Latency constraint violated for '{func_name}': "
                                f"required {constraint.mode} {constraint.max_cycles} cycles, "
                                f"actual {actual_latency} cycles"
                            )
                            logger.error(error_msg)
                            if self.strict_mode:
                                raise LatencyViolationError(
                                    func_name, constraint.max_cycles, actual_latency
                                )
                            else:
                                logger.warning("  Constraint violated but strict mode is off")
                        else:
                            logger.info(f"  {func_name}: constraint satisfied")
            
            # Log optimization summary
            logger.info("Generating optimization summary")
            try:
                opt_summary = self.get_optimization_summary()
                logger.info("Optimization Summary:")
                for line in opt_summary.split('\n'):
                    if line.strip() and not line.startswith('=') and not line.startswith('OPTIMIZATION SUMMARY'):
                        logger.info(f"  {line}")
            except Exception as e:
                logger.warning(f"Error generating optimization summary: {str(e)}")
            
            # Log completion
            logger.info("Compilation completed successfully")
            
            # Store log file path for later reference
            self.synthesis_log_path = log_file_path
            
            # Save netlist to file if output path specified or derive from source
            save_path = output_file
            if save_path is None:
                ext = ".v" if target.lower() == "verilog" else ".vhd"
                save_path = f"{base}{ext}"
            if self.netlist and hasattr(self.netlist, 'modules'):
                try:
                    with open(save_path, 'w') as f:
                        for mod_name, mod in self.netlist.modules.items():
                            if hasattr(mod, 'verilog_blocks') and mod.verilog_blocks:
                                for block in mod.verilog_blocks:
                                    f.write(block)
                                    if not block.endswith('\n'):
                                        f.write('\n')
                                f.write('\n')
                            elif hasattr(mod, 'vhdl_blocks') and mod.vhdl_blocks:
                                for block in mod.vhdl_blocks:
                                    f.write(block)
                                    if not block.endswith('\n'):
                                        f.write('\n')
                                f.write('\n')
                    logger.info(f"RTL written to {save_path}")
                except Exception as e:
                    logger.warning(f"Could not save RTL to {save_path}: {e}")
            
            return self.netlist, self.get_synthesis_logs(log_file_path)
        
        except Exception as e:
            # Log any errors
            logger.error(f"Compilation failed: {str(e)}", exc_info=True)
            raise
        
        finally:
            # Always remove the file handler from all loggers to prevent duplicate entries
            logger.removeHandler(file_handler)
            root_logger.removeHandler(file_handler)
            
            try:
                scheduler_logger.removeHandler(file_handler)
                optimizer_logger.removeHandler(file_handler)
            except:
                pass  # In case the loggers weren't initialized yet
                
            file_handler.close()
    
    def compile_jax(
        self,
        func_or_graph: Any,
        example_inputs: Optional[Sequence[Any]] = None,
        array_specs: Optional[Dict[str, Any]] = None,
        target: str = "verilog",
        debug: bool = False,
        output_file: Optional[str] = None,
        ppa_optimization: bool = False,
        ppa_objective: str = "area",
    ) -> Any:
        """
        Compile a statically bounded JAX kernel to target hardware RTL.

        Args:
            func_or_graph: JAX callable decorated with @jax_kernel or a JaxprGraph instance.
            example_inputs: Sample input arrays for tracing.
            array_specs: Explicit mapping of parameter names to JAXArraySpecs.
            target: Target RTL language ("verilog" or "vhdl").
            debug: Enable debug logging.
            output_file: Optional path for generated RTL.
            ppa_optimization: Enable PPA optimization pass.
            ppa_objective: PPA objective ("area", "performance", "power", "balanced").

        Returns:
            Tuple of (netlist, synthesis_logs)
        """
        from .frontend.jax import trace_jax_kernel, lower_jaxpr_to_ast
        graph = trace_jax_kernel(func_or_graph, example_inputs=example_inputs, array_specs=array_specs)
        func_ast = lower_jaxpr_to_ast(graph)

        import tempfile
        lowered_code = ast.unparse(func_ast)
        entry_name = graph.name

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(lowered_code)
            temp_path = tf.name

        try:
            out_path = output_file or f"{entry_name}.v"
            return self.compile(
                temp_path,
                target=target,
                debug=debug,
                entry_function=entry_name,
                output_file=out_path,
                ppa_optimization=ppa_optimization,
                ppa_objective=ppa_objective,
            )
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _process_optimization_hints(self):
        """
        Process optimization hints from pragmas and annotations in the source code.
        """
        if not self.ir:
            logger.warning("No IR available to process optimization hints")
            return
        
        logger.info("Processing optimization hints from pragmas and annotations")
        
        # Check for matrix operation hints
        has_matrix_op = False
        matrix_op_type = None
        
        # Check all functions
        for func_name, func in self.ir.functions.items():
            logger.debug(f"Processing optimization hints for function {func_name}")
            
            # Count nested loops as an indicator of matrix operations
            loop_count = 0
            
            # Track if we have any unroll pragmas to ensure we use the right optimization level
            has_unroll_pragma = False
            
            for block in func.blocks:
                if hasattr(block, 'is_loop') and block.is_loop:
                    loop_count += 1
                    logger.debug(f"Found loop block: {block.name}")
                    
                    # Look for loop_count pragmas
                    if hasattr(block, 'loop_iterations') and block.loop_iterations > 0:
                        logger.debug(f"Found loop_iterations: {block.loop_iterations} for block {block.name}")
                    
                    # Look for EXPLICIT unroll pragmas (not loop_count)
                    if hasattr(block, 'pragmas') and block.pragmas:
                        # Check for loop unrolling pragma - ONLY explicit "unroll" pragma, not "loop_count"
                        if 'unroll' in block.pragmas:
                            has_unroll_pragma = True
                            unroll_value = block.pragmas['unroll']
                            logger.info(f"Found EXPLICIT unroll pragma with value '{unroll_value}' in block {block.name}")
                            
                            # Store unroll attributes in the block
                            block.unroll = True
                            
                            if unroll_value.lower() == 'full':
                                block.full_unroll = True
                                # If we have a known loop iteration count, use it as the factor
                                if hasattr(block, 'loop_iterations') and block.loop_iterations > 0:
                                    block.unroll_factor = block.loop_iterations
                                    logger.info(f"Setting full unroll factor to {block.loop_iterations} for block {block.name}")
                                else:
                                    # Unknown iteration count for full unrolling
                                    block.unroll_factor = 0  # 0 means intent for full unroll but unknown count
                                    logger.info(f"Full unrolling requested for block {block.name} but iteration count unknown")
                            else:
                                # Partial unrolling
                                try:
                                    unroll_factor = int(unroll_value)
                                    if unroll_factor > 0:
                                        block.unroll_factor = unroll_factor
                                        logger.info(f"Setting unroll factor to {unroll_factor} for block {block.name}")
                                    else:
                                        # Invalid unroll factor, default to 1
                                        block.unroll_factor = 1
                                        logger.warning(f"Invalid unroll factor {unroll_value}, defaulting to 1 for block {block.name}")
                                except ValueError:
                                    # Invalid unroll factor, default to 1
                                    block.unroll_factor = 1
                                    logger.warning(f"Non-numeric unroll factor '{unroll_value}', defaulting to 1 for block {block.name}")
                        
                        # Log loop_count pragmas but DO NOT enable unrolling for them
                        if 'loop_count' in block.pragmas:
                            loop_count_value = block.pragmas['loop_count']
                            logger.info(f"Found loop_count pragma with value '{loop_count_value}' in block {block.name} - NOT enabling unrolling")
                    
                    # Check operation patterns in
                    for instr in block.instructions:
                        for op in instr.operations:
                            # Look for matrix multiply patterns (MUL followed by ADD)
                            if op.op_type.name == "MUL":
                                # Find subsequent ADD operations using the same result
                                for next_op in instr.operations:
                                    if next_op.op_type.name == "ADD" and next_op != op:
                                        for operand in next_op.operands:
                                            if operand == op.result:
                                                has_matrix_op = True
                                                matrix_op_type = "gemm"
                                                logger.debug(f"Detected matrix multiplication pattern in block {block.name}")
                                                break
            
            # Set function attributes based on operation patterns
            func.loop_count = loop_count
            logger.debug(f"Function {func_name} has {loop_count} loops")
            
            # If we have matrix operations, set special optimization flags
            if has_matrix_op:
                func.has_matrix_operations = True
                func.matrix_operation_type = matrix_op_type
                
                # Enable pipelining for matrix operations
                func.enable_pipeline = True
                func.pipeline_depth = 4
                
                logger.info(f"Detected matrix operations in function {func_name} - enabling pipeline optimizations")
            
            # If we have any unroll pragmas, use optimization level 3 to enable loop unrolling
            if has_unroll_pragma:
                self.optimization_level = max(self.optimization_level, 3)
                logger.info(f"Loop unrolling pragmas detected in function {func_name} - using optimization level 3+")
        
        logger.info(f"Optimization level after processing hints: {self.optimization_level}")
    
    def _apply_memory_sizes(self):
        """
        Apply memory size information extracted from source code to the IR.
        This ensures that memory resources are properly allocated based on annotations in the code.
        """
        if not hasattr(self, 'ir') or not self.ir:
            logger.warning("No IR available to apply memory sizes")
            return
            
        # Log that we're applying memory sizes from annotations
        logger.info("Applying memory size information from source code annotations")
        
        # Process each function in the IR
        for func_name, func in self.ir.functions.items():
            logger.debug(f"Processing memory sizes for function {func_name}")
            
            # First, check for pending memory sizes from annotations
            if hasattr(func, 'pending_memory_sizes') and func.pending_memory_sizes:
                logger.info(f"Found {len(func.pending_memory_sizes)} pending memory size annotations for function {func_name}")
                for var_name, memory_size in func.pending_memory_sizes.items():
                    if var_name in func.local_vars:
                        var = func.local_vars[var_name]
                        if var.data_type != "ARRAY":
                            var.data_type = "ARRAY"
                        
                        # Calculate element size
                        element_size = var.bit_width // 8  # bytes per element
                        if element_size > 0:
                            var.memory_size = max(var.memory_size, memory_size // element_size)
                            logger.info(f"Applied pending memory size to {var_name}: {var.memory_size} elements ({memory_size} bytes)")
            
            # Look for memory size variables in the function
            memory_size_vars = {}
            memory_used = 0
            
            # Find all variables ending with _memory_size or _size
            for var_name, var in func.local_vars.items():
                if var_name.endswith('_memory_size') or var_name.endswith('_size'):
                    base_var_name = var_name.replace('_memory_size', '').replace('_size', '')
                    
                    # Try to extract value from operations
                    value = None
                    # Check all blocks and instructions for assignment operations
                    for block in func.blocks:
                        for instr in block.instructions:
                            for op in instr.operations:
                                if op.op_type == "ASSIGN" and hasattr(op, 'result') and op.result:
                                    if op.result.name == var_name and op.operands and hasattr(op.operands[0], 'value'):
                                        value = op.operands[0].value
                                        logger.debug(f"Found memory size value for {base_var_name}: {value} bytes")
                                        memory_size_vars[base_var_name] = value
            
            # Apply memory sizes to the corresponding variables
            for var_name, var in func.local_vars.items():
                if var_name in memory_size_vars:
                    memory_size = memory_size_vars[var_name]
                    element_size = var.bit_width // 8  # bytes per element
                    if element_size > 0:
                        var.memory_size = max(var.memory_size, memory_size // element_size)
                        logger.debug(f"Applied memory size to {var_name}: {var.memory_size} elements")
                        memory_used += var.memory_size * element_size
            
            # Look for dimension variables to compute derived memory sizes
            if hasattr(func, 'dimension_vars') and func.dimension_vars:
                # Use dimension variables to calculate memory sizes for arrays
                # without explicit memory size annotations
                logger.debug(f"Using dimension variables to calculate memory sizes for function {func_name}")
                
                # Process variables that look like arrays but don't have memory sizes yet
                for var_name, var in func.local_vars.items():
                    if var.data_type == "ARRAY" and var.memory_size <= 128:  # Default size or unset
                        # Look for dimension expressions in the code
                        # This is a general approach that doesn't assume specific matrix variables
                        estimated_size = 0
                        
                        # Check all blocks and instructions for array creation
                        for block in func.blocks:
                            for instr in block.instructions:
                                # Simple heuristic: if the variable appears on the left side of 
                                # an assignment with list comprehension or array operations,
                                # try to estimate its size
                                
                                # We've already processed variables with explicit memory sizes
                                if var_name in memory_size_vars:
                                    continue
                                    
                                # If we find information to compute a size, update it
                                if estimated_size > 0:
                                    var.memory_size = max(var.memory_size, estimated_size)
                                    logger.debug(f"Updated array {var_name} size to {var.memory_size} elements")
                                    memory_used += var.memory_size * (var.bit_width // 8)
            
            # Set total memory size for the function
            func.total_memory_size = max(func.total_memory_size if hasattr(func, 'total_memory_size') else 0, memory_used)
            # logger.info(f"Total memory size for function {func_name}: {func.total_memory_size} bytes")
    
    def _allocate_resources(self) -> None:
        """
        Allocate resources for the scheduled IR.
        This method selects the optimization target based on problem characteristics.
        """
        if self.scheduled_ir is None:
            logger.warning("No scheduled IR available to allocate resources")
            return
        
        logger.info("Allocating hardware resources based on problem characteristics")
        
        # Analyze the problem to determine the appropriate optimization target
        optimization_target = "area"  # Default
        
        # Check for compute-intensive patterns like matrix operations
        has_matrix_ops = False
        large_memory_footprint = False
        
        for func_name, func in self.scheduled_ir.functions.items():
            logger.debug(f"Analyzing function {func_name} for resource allocation")
            
            # Check for matrix operation patterns
            if hasattr(func, 'has_matrix_operations') and func.has_matrix_operations:
                has_matrix_ops = True
                logger.debug(f"Function {func_name} has matrix operations")
                
            # Check memory footprint
            memory_size = 0
            for var_name, var in func.local_vars.items():
                if hasattr(var, 'memory_size'):
                    memory_size += var.memory_size * var.bit_width // 8  # Size in bytes
            
            logger.debug(f"Function {func_name} memory footprint: {memory_size} bytes")
            
            # Consider larger than 1MB as large memory footprint
            if memory_size > 1024 * 1024:
                large_memory_footprint = True
                logger.info(f"Large memory footprint detected in function {func_name}: {memory_size} bytes")
                
            # Check loop complexity
            loop_count = getattr(func, 'loop_count', 0)
            if loop_count >= 3:  # Triple-nested loops or more indicate complex computation
                has_matrix_ops = True
                logger.debug(f"Function {func_name} has complex loop structure with {loop_count} nested loops")
        
        # Select optimization target based on problem characteristics
        if has_matrix_ops:
            # For matrix operations, prioritize performance
            optimization_target = "performance"
            logger.info("Selecting performance optimization target for matrix operations")
        elif large_memory_footprint:
            # For problems with large memory footprint, balance area and performance
            optimization_target = "area"
            logger.info("Selecting area optimization target for large memory footprint")
        else:
            logger.info(f"Using default '{optimization_target}' optimization target")
        
        # Allocate resources
        logger.info(f"Calling allocator with target: {optimization_target}")
        self.scheduled_ir, self.allocated_resources = self.allocator.allocate(
            self.scheduled_ir, optimization_target
        )
        
        # Log allocated resources
        if self.allocated_resources:
            logger.info("Resource allocation complete")
            for resource_type, count in self.allocated_resources.items():
                logger.debug(f"Allocated {count} instances of {resource_type}")
        
        # Create netlist resources
        logger.info("Creating netlist resources from allocated resources")
        self.netlist_resources = self.allocator.create_netlist_resources(self.allocated_resources)
        
        # Apply resources to modules
        logger.info("Applying resources to modules")
        self._apply_resources_to_modules()
    
    def _apply_resources_to_modules(self):
        """Ensure modules have correct resources and area values based on tech node."""
        if not self.netlist or not self.netlist_resources:
            return
        
        # Reset total area and power
        self.netlist.total_area = 0.0
        self.netlist.total_power = 0.0
        
        # Apply resources to each module
        for module_name, module in self.netlist.modules.items():
            # Clear existing resources to avoid duplicates
            module.resources.clear()
            module.area = 0.0  # Reset area
            module.power = 0.0  # Reset power
            module_resources = []  # Track all resources for this module
            
            # Add the netlist resources to the module
            for resource in self.netlist_resources:
                # Ensure the resource is using the current technology node
                resource_type = resource.type
                resource_model = self.tech_library.get_resource(resource_type, self.tech_node)
                
                # Create a new resource with correctly scaled values
                new_resource = type(resource)(
                    name=resource.name,
                    type=resource.type,
                    bit_width=resource.bit_width,
                    latency=resource.latency,
                    area=resource_model.area,  # Use correctly scaled area
                    power=self._calculate_resource_power(resource_model),  # Use target frequency for power calculation
                    technology_node=self.tech_node,  # Ensure tech_node is set correctly
                    supply_voltage=resource.supply_voltage,
                    memory_type=resource.memory_type,
                    memory_size=resource.memory_size
                )
                
                # Add resource to module and update area
                module.add_resource(new_resource)
                module_resources.append(new_resource)
            
            # Calculate total power with additional components
            base_power = module.power
            
            # Include additional power components if we have resources
            if module_resources:
                # Calculate design complexity statistics
                resource_count = len(module_resources)
                compute_resources = sum(1 for r in module_resources if r.memory_type == "none" and 
                                        any(t in r.type for t in ["ALU", "Adder", "Subtractor", "Multiplier", "Divider"]))
                memory_resources = sum(1 for r in module_resources if r.memory_type != "none")
                
                # Clock tree power (scales with design size and frequency)
                cts_factor = 0.15 + (0.15 * min(1.0, resource_count / 50))  # Scale up to 30% for larger designs
                cts_power = base_power * cts_factor
                
                # PDN losses (typically 5-10% overhead)
                pdn_factor = 0.05 + (0.05 * min(1.0, resource_count / 100))
                pdn_power = base_power * pdn_factor
                
                # Interconnect power (scales with design complexity)
                if compute_resources > 0:
                    # Complex designs with higher compute-to-memory ratio need more interconnect
                    compute_memory_ratio = compute_resources / max(1, memory_resources)
                    interconnect_factor = 0.2 + min(0.2, (0.1 * compute_memory_ratio) + (0.1 * resource_count / 50))
                else:
                    interconnect_factor = 0.2  # Default 20% for simple designs
                
                interconnect_power = base_power * interconnect_factor
                
                # Control logic power (state machines, decoders, etc.)
                control_factor = 0.1 + (0.05 * min(1.0, compute_resources / 20))
                control_power = base_power * control_factor
                
                # Total power with all components
                total_power = base_power + cts_power + pdn_power + interconnect_power + control_power
                
                # Update module power with total power
                module.power = total_power
                
                # # Store power breakdown in the module
                # module.power_breakdown = {
                #     "base_resource_power": base_power,
                #     "clock_tree_power": cts_power,
                #     "pdn_power": pdn_power,
                #     "interconnect_power": interconnect_power,
                #     "control_logic_power": control_power,
                #     "total_power": total_power
                # }
                
                # Log the power breakdown
                logger.info(f"Module {module_name} power breakdown:")
                logger.info(f"  Base resource power: {base_power:.2f} mW ({(base_power/total_power*100):.1f}%)")
                logger.info(f"  Clock tree power: {cts_power:.2f} mW ({(cts_power/total_power*100):.1f}%)")
                logger.info(f"  PDN power: {pdn_power:.2f} mW ({(pdn_power/total_power*100):.1f}%)")
                logger.info(f"  Interconnect power: {interconnect_power:.2f} mW ({(interconnect_power/total_power*100):.1f}%)")
                logger.info(f"  Control logic power: {control_power:.2f} mW ({(control_power/total_power*100):.1f}%)")
                logger.info(f"  Total power: {total_power:.2f} mW")
            
            # Update netlist total values
            self.netlist.total_area += module.area
            self.netlist.total_power += module.power
    
    def _calculate_resource_power(self, resource_model):
        """
        Calculate power consumption for a resource using the design's target frequency.
        
        Args:
            resource_model: Resource model with energy and frequency data
            
        Returns:
            Power in mW
        """
        # Use the target frequency if available, otherwise use resource model frequency
        operating_frequency = resource_model.frequency  # Default
        
        # Use the target frequency from the scheduled IR if available
        if hasattr(self, 'scheduled_ir') and self.scheduled_ir and hasattr(self.scheduled_ir, 'target_frequency_mhz'):
            if self.scheduled_ir.target_frequency_mhz > 0:
                operating_frequency = self.scheduled_ir.target_frequency_mhz
        
        # Calculate dynamic power using operating frequency and add leakage power
        # Power (mW) = Dynamic power + Leakage power
        # Dynamic power (mW) = Energy per operation (pJ) * Frequency (MHz) / 1000
        # Leakage power (mW) = Leakage power (µW) / 1000
        dynamic_power = resource_model.energy_per_op * operating_frequency / 1000
        leakage_power = resource_model.leakage_power / 1000
        
        return dynamic_power + leakage_power
    
    def schedule_asap(self) -> None:
        """Schedule operations using As Soon As Possible (ASAP) algorithm."""
        if self.optimized_ir is None:
            raise RuntimeError("No IR available. Run compile() first.")
        
        self.scheduled_ir = self.asap_scheduler.schedule(self.optimized_ir)
    
    def schedule_alap(self, latency_constraint: Optional[int] = None) -> None:
        """
        Schedule operations using As Late As Possible (ALAP) algorithm.
        
        Args:
            latency_constraint: Maximum latency in clock cycles
        """
        if self.optimized_ir is None:
            raise RuntimeError("No IR available. Run compile() first.")
        
        self.scheduled_ir = self.alap_scheduler.schedule(self.optimized_ir, latency_constraint)
    
    def schedule_list(self, resource_constraints: Dict[str, int]) -> None:
        """
        Schedule operations using list scheduling algorithm.
        
        Args:
            resource_constraints: Dictionary of resource types and their counts
        """
        if self.optimized_ir is None:
            raise RuntimeError("No IR available. Run compile() first.")
        
        self.scheduled_ir = self.list_scheduler.schedule(self.optimized_ir, resource_constraints)
    
    def allocate_resources(self, optimization_target: str = "area") -> Dict[str, int]:
        """
        Allocate resources for operations.
        
        Args:
            optimization_target: Target to optimize for ("area", "performance", "power")
            
        Returns:
            Dictionary of allocated resources
        """
        if self.scheduled_ir is None:
            raise RuntimeError("No scheduled IR available. Run scheduling first.")
        
        self.scheduled_ir, self.allocated_resources = self.allocator.allocate(
            self.scheduled_ir, optimization_target
        )
        
        self.netlist_resources = self.allocator.create_netlist_resources(self.allocated_resources)
        
        return self.allocated_resources
    
    def enable_loop_pipelining(self, function_name: str, pipeline_depth: int = 1) -> None:
        """
        Enable loop pipelining for a function.
        
        Args:
            function_name: Name of the function to enable pipelining for
            pipeline_depth: Pipeline depth (cycles between iterations)
        """
        if self.ir is None:
            raise RuntimeError("No IR available. Run parse() first.")
            
        # Get the function from the IR
        func = self.ir.get_function(function_name)
        if func is None:
            raise ValueError(f"Function '{function_name}' not found in IR")
            
        # Enable pipelining
        func.enable_pipeline = True
        func.pipeline_depth = max(1, pipeline_depth)  # Ensure valid depth
        
        logger.info(f"Enabled loop pipelining for function '{function_name}' with depth {func.pipeline_depth}")
        
        # If optimized IR exists, propagate the setting
        if self.optimized_ir is not None:
            opt_func = self.optimized_ir.get_function(function_name)
            if opt_func is not None:
                opt_func.enable_pipeline = True
                opt_func.pipeline_depth = func.pipeline_depth
                
        # If scheduled IR exists, propagate the setting and reschedule
        if self.scheduled_ir is not None:
            sched_func = self.scheduled_ir.get_function(function_name)
            if sched_func is not None:
                sched_func.enable_pipeline = True
                sched_func.pipeline_depth = func.pipeline_depth
                
                # Reschedule to update latency calculations
                logger.info(f"Rescheduling function '{function_name}' with pipelining...")
                self.schedule()
    
    def disable_loop_pipelining(self, function_name: str) -> None:
        """
        Disable loop pipelining for a function.
        
        Args:
            function_name: Name of the function to disable pipelining for
        """
        if self.ir is None:
            raise RuntimeError("No IR available. Run parse() first.")
            
        # Get the function from the IR
        func = self.ir.get_function(function_name)
        if func is None:
            raise ValueError(f"Function '{function_name}' not found in IR")
            
        # Disable pipelining
        func.enable_pipeline = False
        
        logger.info(f"Disabled loop pipelining for function '{function_name}'")
        
        # If optimized IR exists, propagate the setting
        if self.optimized_ir is not None:
            opt_func = self.optimized_ir.get_function(function_name)
            if opt_func is not None:
                opt_func.enable_pipeline = False
                
        # If scheduled IR exists, propagate the setting and reschedule
        if self.scheduled_ir is not None:
            sched_func = self.scheduled_ir.get_function(function_name)
            if sched_func is not None:
                sched_func.enable_pipeline = False
                
                # Reschedule to update latency calculations
                logger.info(f"Rescheduling function '{function_name}' without pipelining...")
                self.schedule()
    
    def visualize_datapath(self, output_file: Optional[str] = None) -> str:
        """
        Generate a visualization of the datapath.
        
        Args:
            output_file: Path to save the visualization
            
        Returns:
            Path to the generated visualization file
        """
        if self.ir is None:
            raise RuntimeError("No IR available. Run compile() first.")
        
        if output_file is None:
            base, _ = os.path.splitext(self.source_file)
            output_file = f"{base}_datapath.png"
        
        return self.visualizer.visualize_datapath(self.ir, output_file)
    
    def visualize_scheduled_datapath(self, output_file: Optional[str] = None) -> str:
        """
        Generate a visualization of the scheduled datapath.
        
        Args:
            output_file: Path to save the visualization
            
        Returns:
            Path to the generated visualization file
        """
        if self.scheduled_ir is None:
            raise RuntimeError("No scheduled IR available. Run scheduling first.")
        
        if output_file is None:
            base, _ = os.path.splitext(self.source_file)
            output_file = f"{base}_scheduled_datapath.png"
        
        return self.visualizer.visualize_scheduled_datapath(self.scheduled_ir, output_file)
    
    def visualize_control_flow(self, output_file: Optional[str] = None) -> str:
        """
        Generate a visualization of the control flow.
        
        Args:
            output_file: Path to save the visualization
            
        Returns:
            Path to the generated visualization file
        """
        if self.ir is None:
            raise RuntimeError("No IR available. Run compile() first.")
            
        if output_file is None:
            base, _ = os.path.splitext(self.source_file)
            output_file = f"{base}_control.png"
        
        return self.visualizer.visualize_control_flow(self.ir, output_file)
    
    def visualize_netlist(self, output_file: Optional[str] = None) -> str:
        """
        Visualize the netlist as a microarchitecture diagram.
        
        Args:
            output_file: Path to write the output visualization
            
        Returns:
            Path to the generated visualization
        """
        if not self.netlist or not self.netlist_resources:
            raise RuntimeError("No netlist available. Run compile() first.")
        
        # Gather operation types for better visualization
        operations = []
        if hasattr(self, 'scheduled_ir') and self.scheduled_ir:
            for func_name, func in self.scheduled_ir.functions.items():
                for block in func.blocks:
                    for instr in block.instructions:
                        for op in instr.operations:
                            operations.append(op.op_type.name)
        
        # Use the improved netlist visualization
        from python_hls.visualizer.netlist_microarch_dot import generate_netlist_microarch_visualization
        dot_str = generate_netlist_microarch_visualization(self.netlist_resources, operations, self.netlist)
        
        # Set output path
        if output_file:
            output_path = output_file
        else:
            output_path = f"{self.source_file}.netlist.png" if self.source_file else "netlist.png"
        
        # Generate visualization
        try:
            # Try using svg2png if available
            if svg2png is not None:
                svg_data = graphviz.Source(dot_str).pipe(format='svg')
                svg2png(bytestring=svg_data, write_to=output_path)
            else:
                # Direct graphviz rendering
                g = graphviz.Source(dot_str)
                output_path = g.render(filename=output_path.replace('.png', ''), format='png', cleanup=True)
        except Exception as e:
            # Fallback to direct graphviz render with simpler approach
            logger.warning(f"Error in SVG conversion: {e}")
            try:
                g = graphviz.Source(dot_str)
                output_path = g.render(filename="netlist", format='png', cleanup=True)
            except Exception as e2:
                logger.warning(f"Could not generate netlist visualization: {e2}")
                return "Failed to generate visualization"
        
        return output_path
    
    def visualize_netlist_microarch(self, output_file: Optional[str] = None) -> str:
        """
        Generate a detailed microarchitecture visualization of the hardware netlist.
        
        This visualization shows the connections between hardware resources, 
        including computational units, registers, memory, and control logic.
        
        Args:
            output_file: Path to save the visualization
            
        Returns:
            Path to the generated visualization file
        """
        if self.netlist is None or self.ir is None:
            raise RuntimeError("No netlist or IR available. Run compile() first.")
        
        if output_file is None:
            base, _ = os.path.splitext(self.source_file)
            output_file = f"{base}_microarch.png"
        
        return self.visualizer.visualize_netlist_microarch(self.ir, self.netlist, output_file)
    
    def get_resource_report(self) -> Dict[str, Any]:
        """
        Generate a report of hardware resource usage.
        
        Returns:
            Dictionary containing resource usage information
        """
        if self.netlist is None:
            raise RuntimeError("No netlist available. Run compile() first.")
        
        # Get the base report from netlist
        report = self.netlist.get_resource_report()
        
        # Add allocated resources information
        if hasattr(self, 'allocated_resources') and self.allocated_resources:
            report['allocated_resources'] = self.allocated_resources
        else:
            report['allocated_resources'] = {}
        
        # Add technology metadata and provenance
        if hasattr(self, 'tech_library') and self.tech_library:
            report['technology_metadata'] = self.tech_library.get_metadata_summary()
        
        return report
    
    def set_tech_node(self, tech_node: int) -> None:
        """
        Set the technology node.
        
        Args:
            tech_node: Technology node in nm
        """
        self.tech_node = tech_node
        self.tech_library.set_tech_node(tech_node)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the compiled design.
        
        Returns:
            A dictionary with performance metrics.
        """
        if not self.netlist or not self.scheduled_ir:
            return {
                "total_area": 0.0,
                "total_power": 0.0,
                "critical_path": 0.0,
                "latency_cycles": 0,
                "latency_ns": 0.0,
                "clock_frequency_mhz": 0.0,
                "technology_node": self.tech_node,
            }
            
        # Use the netlist's own total area and power which are calculated in _apply_resources_to_modules
        total_area = self.netlist.total_area
        total_power = self.netlist.total_power
        
        # Collect power breakdown across all modules
        power_breakdown = {}
        detailed_power_breakdown = {
            "base_resource_power": 0.0,
            "clock_tree_power": 0.0,
            "pdn_power": 0.0,
            "interconnect_power": 0.0,
            "control_logic_power": 0.0
        }
        
        for module_name, module in self.netlist.get_resource_report()["modules"].items():
            # Collect individual module breakdowns
            power_breakdown[module_name] = module["power_breakdown"]
                
        
        # Calculate percentages for the detailed power breakdown
        power_percentages = {}
        if total_power > 0:
            for component, value in detailed_power_breakdown.items():
                power_percentages[f"{component}_percent"] = (value / total_power) * 100
        
        max_latency_cycles = 0
        clock_frequency_mhz = 0.0
        
        # Get metrics from the netlist modules and scheduled IR
        for func_name, func in self.scheduled_ir.functions.items():
            # If we have a total_latency value from the scheduler that includes loop iterations,
            # use that as the primary latency source
            if hasattr(func, 'total_latency') and func.total_latency > 0:
                max_latency_cycles = max(max_latency_cycles, func.total_latency)
                logger.info(f"Function {func_name} has total latency of {func.total_latency} cycles")
            elif hasattr(func, 'single_iter_latency') and func.single_iter_latency > 0:
                max_latency_cycles = max(max_latency_cycles, func.single_iter_latency)
                logger.info(f"Function {func_name} has single iteration latency of {func.single_iter_latency} cycles")
        
        # If no valid latency from IR, fall back to netlist modules
        if max_latency_cycles == 0:
            for module_name, module in self.netlist.modules.items():
                if module.latency > max_latency_cycles:
                    max_latency_cycles = module.latency
                    logger.info(f"Using module {module_name} latency: {module.latency} cycles")
        
        # Check for IR target frequency
        if hasattr(self.scheduled_ir, 'target_frequency_mhz') and self.scheduled_ir.target_frequency_mhz > 0:
            clock_frequency_mhz = self.scheduled_ir.target_frequency_mhz
            logger.info(f"Using target frequency from IR: {clock_frequency_mhz:.2f} MHz")
        else:
            # Use the first valid clock frequency we find from modules
            for module_name, module in self.netlist.modules.items():
                if module.clock_frequency_mhz > 0 and clock_frequency_mhz == 0.0:
                    clock_frequency_mhz = module.clock_frequency_mhz
                    logger.info(f"Using clock frequency from module {module_name}: {clock_frequency_mhz:.2f} MHz")
        
        # Fall back to default if no frequency found
        if clock_frequency_mhz <= 0:
            clock_frequency_mhz = 100.0  # Default to 100 MHz
            logger.info(f"No valid frequency found, using default: {clock_frequency_mhz:.2f} MHz")
        
        # Calculate latency in nanoseconds
        latency_ns = 0.0
        if clock_frequency_mhz > 0:
            latency_ns = (max_latency_cycles * 1000.0) / clock_frequency_mhz
            
        # Get the critical path (clock period constraint)
        critical_path = 0.0
        if clock_frequency_mhz > 0:
            critical_path = 1000.0 / clock_frequency_mhz  # Convert MHz to ns period
            logger.info(f"Critical path calculation: 1000.0 / {clock_frequency_mhz:.2f} MHz = {critical_path:.2f} ns")
        
        # Create metrics dictionary with detailed power information
        metrics = {
            "total_area": total_area,
            "total_power": total_power,
            "power_breakdown": power_breakdown,
            "detailed_power": detailed_power_breakdown,
            "power_percentages": power_percentages,
            "critical_path": critical_path,
            "latency_cycles": max_latency_cycles,
            "latency_ns": latency_ns,
            "clock_frequency_mhz": clock_frequency_mhz,
            "technology_node": self.tech_node,
            "technology_metadata": self.tech_library.get_metadata_summary() if hasattr(self, 'tech_library') and self.tech_library else {},
        }
        
        # Log complete metrics for debugging
        # logger.info("Final performance metrics:")
        # logger.info(f"  Total area: {total_area:.2f} μm²")
        # logger.info(f"  Total power: {total_power:.2f} mW")
        # logger.info(f"    Base resource power: {detailed_power_breakdown.get('base_resource_power', 0):.2f} mW ({power_percentages.get('base_resource_power_percent', 0):.1f}%)")
        # logger.info(f"    Clock tree power: {detailed_power_breakdown.get('clock_tree_power', 0):.2f} mW ({power_percentages.get('clock_tree_power_percent', 0):.1f}%)")
        # logger.info(f"    PDN power: {detailed_power_breakdown.get('pdn_power', 0):.2f} mW ({power_percentages.get('pdn_power_percent', 0):.1f}%)")
        # logger.info(f"    Interconnect power: {detailed_power_breakdown.get('interconnect_power', 0):.2f} mW ({power_percentages.get('interconnect_power_percent', 0):.1f}%)")
        # logger.info(f"    Control logic power: {detailed_power_breakdown.get('control_logic_power', 0):.2f} mW ({power_percentages.get('control_logic_power_percent', 0):.1f}%)")
        # logger.info(f"  Critical path: {critical_path:.2f} ns")
        # logger.info(f"  Clock frequency: {clock_frequency_mhz:.2f} MHz")
        # logger.info(f"  Latency: {max_latency_cycles} cycles ({latency_ns:.2f} ns)")
        
        return metrics
    
    def generate_netlist(self, target: str = "verilog") -> Any:
        """
        Generate a netlist from the scheduled IR.
        
        Args:
            target: Target hardware description language
            
        Returns:
            Netlist representation
        """
        if not self.scheduled_ir:
            logger.error("No scheduled IR available. Run scheduling first.")
            raise RuntimeError("No scheduled IR available. Run scheduling first.")
        
        logger.info(f"Generating {target} netlist from scheduled IR")
        
        # Bind operations to resources
        logger.info("Binding operations to allocated resources")
        self.scheduled_ir, self.netlist_operations = self.binder.bind(
            self.scheduled_ir, self.allocated_resources, self.netlist_resources
        )
        
        # Generate target hardware description
        logger.info(f"Generating {target} hardware description")
        if target.lower() == "verilog":
            logger.info("Using Verilog generator")
            self.netlist = self.verilog_generator.generate(self.scheduled_ir)
        elif target.lower() == "vhdl":
            logger.info("Using VHDL generator")
            self.netlist = self.vhdl_generator.generate(self.scheduled_ir)
        else:
            logger.error(f"Unsupported target: {target}")
            raise ValueError(f"Unsupported target: {target}")
        
        # Update netlist technology info
        self.netlist.technology_node = self.tech_node
        logger.info(f"Netlist generation complete for technology node {self.tech_node} nm")
        
        # Log summary of generated netlist
        if self.netlist:
            module_count = len(self.netlist.modules) if hasattr(self.netlist, 'modules') else 0
            logger.info(f"Generated netlist with {module_count} modules")
            
            if hasattr(self.netlist, 'modules'):
                for module_name in self.netlist.modules:
                    logger.debug(f"Generated module: {module_name}")
        
        return self.netlist
    
    def generate_ppa_optimized_netlist(self, target: str = "verilog", ppa_objective: str = "area") -> Any:
        """
        Generate a PPA-optimized netlist from the scheduled IR.
        
        Args:
            target: Target hardware description language
            ppa_objective: PPA optimization objective ("area", "performance", "power", "balanced")
            
        Returns:
            PPA-optimized netlist representation
        """
        if not self.scheduled_ir:
            logger.error("No scheduled IR available. Run scheduling first.")
            raise RuntimeError("No scheduled IR available. Run scheduling first.")
        
        logger.info(f"Generating PPA-optimized {target} netlist with {ppa_objective} objective")
        
        # Bind operations to resources
        logger.info("Binding operations to allocated resources for PPA optimization")
        self.scheduled_ir, self.netlist_operations = self.binder.bind(
            self.scheduled_ir, self.allocated_resources, self.netlist_resources
        )
        
        # Generate PPA-optimized target hardware description
        logger.info(f"Generating PPA-optimized {target} hardware description")
        if target.lower() == "verilog":
            # Create PPA-optimized Verilog generator if not already created
            if self.ppa_verilog_generator is None:
                self.ppa_verilog_generator = PPAOptimizedVerilogGenerator(
                    ppa_objective=ppa_objective, 
                    tech_node=self.tech_node
                )
            
            logger.info(f"Using PPA-optimized Verilog generator with {ppa_objective} objective")
            self.netlist = self.ppa_verilog_generator.generate(self.scheduled_ir, self.netlist_resources)
        elif target.lower() == "vhdl":
            # For now, fall back to standard VHDL generator
            logger.info("Using standard VHDL generator (PPA optimization not yet implemented for VHDL)")
            self.netlist = self.vhdl_generator.generate(self.scheduled_ir)
        else:
            logger.error(f"Unsupported target: {target}")
            raise ValueError(f"Unsupported target: {target}")
        
        # Update netlist technology info
        self.netlist.technology_node = self.tech_node
        logger.info(f"PPA-optimized netlist generation complete for technology node {self.tech_node} nm")
        
        # Log summary of generated netlist
        if self.netlist:
            module_count = len(self.netlist.modules) if hasattr(self.netlist, 'modules') else 0
            logger.info(f"Generated PPA-optimized netlist with {module_count} modules")
            
            if hasattr(self.netlist, 'modules'):
                for module_name in self.netlist.modules:
                    logger.debug(f"Generated PPA-optimized module: {module_name}")
        
        return self.netlist
    
    def enable_loop_unrolling(self, function_name: str, loop_index: int = 0, unroll_factor: int = 2, full_unroll: bool = False) -> None:
        """
        Enable loop unrolling for a specific loop in a function.
        
        Args:
            function_name: Name of the function containing the loop
            loop_index: Index of the loop to unroll (0 = first loop in the function)
            unroll_factor: Unrolling factor (how many iterations to unroll)
            full_unroll: Whether to fully unroll the loop (ignores unroll_factor)
        """
        if self.ir is None:
            raise RuntimeError("No IR available. Run parse() first.")
        
        # Get the function from the IR
        func = self.ir.get_function(function_name)
        if func is None:
            raise ValueError(f"Function '{function_name}' not found in IR")
        
        # Find loops in the function
        loops = []
        for block in func.blocks:
            if block.loop_header == block:
                loops.append(block)
        
        if not loops:
            print(f"Function '{function_name}' does not contain any loops.")
            return
        
        if loop_index < 0 or loop_index >= len(loops):
            raise ValueError(f"Loop index {loop_index} is out of range (0-{len(loops)-1})")
        
        # Get the target loop header
        loop_header = loops[loop_index]
        
        # Set unrolling attributes
        loop_header.unroll = True
        
        if full_unroll:
            loop_header.full_unroll = True
            
            # If we know the iteration count, use it as the unroll factor
            if hasattr(loop_header, 'loop_iterations') and loop_header.loop_iterations > 0:
                loop_header.unroll_factor = loop_header.loop_iterations
                logger.info(f"Fully unrolling loop {loop_index} in function '{function_name}' with {loop_header.loop_iterations} iterations")
            else:
                loop_header.unroll_factor = 0  # 0 indicates full unroll but unknown count
                logger.info(f"Fully unrolling loop {loop_index} in function '{function_name}' with unknown iteration count")
        else:
            loop_header.full_unroll = False
            loop_header.unroll_factor = max(1, unroll_factor)
            logger.info(f"Partially unrolling loop {loop_index} in function '{function_name}' with factor {loop_header.unroll_factor}")
        
        # Update function's total unroll factor for resource allocation
        # Only update if unrolling was explicitly requested
        if loop_header.unroll:
            func.total_unroll_factor = getattr(func, 'total_unroll_factor', 1) * (loop_header.unroll_factor or 1)
        
        # Propagate settings to optimized IR if it exists
        if self.optimized_ir is not None:
            opt_func = self.optimized_ir.get_function(function_name)
            if opt_func is not None:
                # Find the corresponding loop in the optimized IR
                opt_loops = []
                for block in opt_func.blocks:
                    if block.loop_header == block:
                        opt_loops.append(block)
                
                if loop_index < len(opt_loops):
                    opt_loop_header = opt_loops[loop_index]
                    opt_loop_header.unroll = True
                    opt_loop_header.full_unroll = loop_header.full_unroll
                    opt_loop_header.unroll_factor = loop_header.unroll_factor
                    opt_func.total_unroll_factor = func.total_unroll_factor
        
        # Force reoptimization with unrolling applied
        self.optimization_level = max(self.optimization_level, 3)  # Ensure level 3 which includes loop unrolling
        if self.optimized_ir:
            logger.info(f"Reoptimizing IR with loop unrolling...")
            self.optimized_ir = self.optimizer.optimize(self.ir)
            
            # If scheduled IR exists, reschedule
            if self.scheduled_ir is not None:
                logger.info(f"Rescheduling with loop unrolling applied...")
                self.schedule()

    def disable_loop_unrolling(self, function_name: str, loop_index: int = 0) -> None:
        """
        Disable loop unrolling for a specific loop in a function.
        
        Args:
            function_name: Name of the function containing the loop
            loop_index: Index of the loop (0 = first loop in the function)
        """
        if self.ir is None:
            raise RuntimeError("No IR available. Run parse() first.")
        
        # Get the function from the IR
        func = self.ir.get_function(function_name)
        if func is None:
            raise ValueError(f"Function '{function_name}' not found in IR")
        
        # Find loops in the function
        loops = []
        for block in func.blocks:
            if block.loop_header == block:
                loops.append(block)
        
        if not loops:
            print(f"Function '{function_name}' does not contain any loops.")
            return
        
        if loop_index < 0 or loop_index >= len(loops):
            raise ValueError(f"Loop index {loop_index} is out of range (0-{len(loops)-1})")
        
        # Get the target loop header
        loop_header = loops[loop_index]
        
        # Disable unrolling attributes
        was_unrolled = getattr(loop_header, 'unroll', False)
        old_factor = getattr(loop_header, 'unroll_factor', 1)
        
        loop_header.unroll = False
        loop_header.full_unroll = False
        loop_header.unroll_factor = 1
        
        # Update function's total unroll factor if unrolling was previously enabled
        if was_unrolled and old_factor > 1 and hasattr(func, 'total_unroll_factor'):
            func.total_unroll_factor = max(1, func.total_unroll_factor // old_factor)
        
        logger.info(f"Disabled loop unrolling for loop {loop_index} in function '{function_name}'")
        
        # Propagate settings to optimized IR if it exists
        if self.optimized_ir is not None:
            opt_func = self.optimized_ir.get_function(function_name)
            if opt_func is not None:
                # Find the corresponding loop in the optimized IR
                opt_loops = []
                for block in opt_func.blocks:
                    if block.loop_header == block:
                        opt_loops.append(block)
                
                if loop_index < len(opt_loops):
                    opt_loop_header = opt_loops[loop_index]
                    opt_loop_header.unroll = False
                    opt_loop_header.full_unroll = False
                    opt_loop_header.unroll_factor = 1
                    
                    if was_unrolled and old_factor > 1 and hasattr(opt_func, 'total_unroll_factor'):
                        opt_func.total_unroll_factor = func.total_unroll_factor
        
        # If scheduled IR exists, reschedule
        if self.scheduled_ir is not None:
            logger.info(f"Rescheduling with loop unrolling disabled...")
            self.schedule()

    def get_loop_unrolling_report(self) -> Dict[str, Any]:
        """
        Generate a report on loop unrolling status in the IR.
        
        Returns:
            Dictionary containing unrolling status for each loop
        """
        if self.ir is None:
            return {
                "error": "No IR available. Run parse() first.",
                "loops": [],
                "unrolled_loops": 0,
                "partially_unrolled": 0,
                "fully_unrolled": 0
            }
        
        report = {
            "loops": [],
            "unrolled_loops": 0,
            "partially_unrolled": 0,
            "fully_unrolled": 0
        }
        
        # Gather loop information
        for func_name, func in self.ir.functions.items():
            # Find loops in the function
            loop_index = 0
            for block in func.blocks:
                if block.loop_header == block:
                    # Skip disabled blocks (already unrolled)
                    if hasattr(block, 'is_disabled') and block.is_disabled:
                        continue
                    
                    # Get unrolling status
                    is_unrolled = getattr(block, 'unroll', False)
                    is_full_unroll = getattr(block, 'full_unroll', False)
                    unroll_factor = getattr(block, 'unroll_factor', 1)
                    loop_count = getattr(block, 'loop_iterations', 0)
                    
                    # Create entry for this loop
                    loop_info = {
                        "function": func_name,
                        "loop_index": loop_index,
                        "loop_name": block.name,
                        "is_unrolled": is_unrolled,
                        "full_unroll": is_full_unroll,
                        "unroll_factor": unroll_factor,
                        "loop_iterations": loop_count
                    }
                    report["loops"].append(loop_info)
                    
                    # Update counts
                    if is_unrolled:
                        report["unrolled_loops"] += 1
                        if is_full_unroll:
                            report["fully_unrolled"] += 1
                        else:
                            report["partially_unrolled"] += 1
                    
                    loop_index += 1
        
        # Also check optimized IR if available
        if self.optimized_ir is not None:
            for func_name, func in self.optimized_ir.functions.items():
                # Collect loop information from optimized IR
                for block in func.blocks:
                    if block.loop_header == block:
                        # Skip disabled blocks (already unrolled)
                        if hasattr(block, 'is_disabled') and block.is_disabled:
                            continue
                        
                        is_unrolled = getattr(block, 'unroll', False)
                        is_full_unroll = getattr(block, 'full_unroll', False)
                        
                        # Only update counts if we find additional unrolled loops
                        if is_unrolled:
                            # Check if this loop was already counted in the original IR
                            already_counted = False
                            for loop_info in report["loops"]:
                                if loop_info["function"] == func_name and loop_info["loop_name"] == block.name:
                                    already_counted = True
                                    break
                            
                            if not already_counted:
                                report["unrolled_loops"] += 1
                                if is_full_unroll:
                                    report["fully_unrolled"] += 1
                                else:
                                    report["partially_unrolled"] += 1
        
        return report
    
    def schedule(self) -> None:
        """
        Schedule operations using the current scheduling algorithm.
        Defaults to ASAP scheduling.
        """
        if self.optimized_ir is None:
            raise RuntimeError("No optimized IR available. Run optimization first.")
        
        # Default to ASAP scheduling
        self.scheduled_ir = self.asap_scheduler.schedule(self.optimized_ir)
        
        # Allocate resources after scheduling
        if self.scheduled_ir:
            self._allocate_resources() 

    def verify_hardware_allocation(self) -> Dict[str, Any]:
        """
        Verify the quality of hardware resource allocation and provide an assessment.
        
        Returns:
            Dictionary with allocation quality metrics and recommendations
        """
        if not self.netlist or not self.allocated_resources:
            return {
                "allocation_score": "N/A",
                "assessment": "No allocated resources available",
                "recommendations": []
            }
        
        # Initialize verification report
        verification = {
            "allocation_score": 0.0,
            "assessment": "Unknown",
            "recommendations": [],
            "resource_balance": {},
            "critical_resources": []
        }
        
        # Get resource usage from the netlist
        resources = {}
        total_resources = 0
        
        # Collect all resource types and counts
        for module_name, module in self.netlist.modules.items():
            for resource in module.resources:
                resource_type = resource.type
                if resource_type not in resources:
                    resources[resource_type] = 0
                resources[resource_type] += 1
                total_resources += 1
        
        # Calculate resource balance (distribution)
        if total_resources > 0:
            for resource_type, count in resources.items():
                verification["resource_balance"][resource_type] = count / total_resources
        
        # Identify potential bottlenecks or inefficiencies
        
        # 1. Resource utilization analysis
        if self.scheduled_ir:
            # Check loop unrolling impact on resource usage
            for func_name, func in self.scheduled_ir.functions.items():
                # Check if we have unrolled loops that should be reflected in resource usage
                unrolled_loops = 0
                fully_unrolled = 0
                partially_unrolled = 0
                
                for block in func.blocks:
                    if hasattr(block, 'unroll') and block.unroll:
                        unrolled_loops += 1
                        if hasattr(block, 'full_unroll') and block.full_unroll:
                            fully_unrolled += 1
                        else:
                            partially_unrolled += 1
                
                # If we have unrolled loops but limited resources, make recommendations
                if unrolled_loops > 0:
                    if 'ALU_32bit' in resources and resources['ALU_32bit'] < 2 * unrolled_loops:
                        verification["recommendations"].append({
                            "resource": "ALU_32bit",
                            "message": "Insufficient ALUs for unrolled loops. Consider increasing allocation or reducing unroll factor.",
                            "severity": "high"
                        })
                        verification["critical_resources"].append("ALU_32bit")
        
        # 2. Analyze memory resources
        if 'memory' in resources or 'Memory' in resources:
            memory_count = resources.get('memory', 0) + resources.get('Memory', 0)
            if memory_count < 1 and unrolled_loops > 0:
                verification["recommendations"].append({
                    "resource": "Memory",
                    "message": "Unrolling loops without sufficient memory bandwidth may limit performance. Consider using dual-port memory.",
                    "severity": "medium"
                })
        
        # 3. Analyze special resources like multipliers
        if 'Multiplier_32bit' in resources:
            multiplier_count = resources['Multiplier_32bit']
            if multiplier_count < 1 and unrolled_loops > 1:
                verification["recommendations"].append({
                    "resource": "Multiplier_32bit",
                    "message": "Insufficient multipliers for unrolled loops. Add more multipliers for better performance.",
                    "severity": "medium"
                })
        
        # Calculate overall allocation score (0-100)
        # Start with a base score and adjust based on issues
        allocation_score = 80.0  # Default "good" score
        
        # Subtract points for each critical recommendation
        allocation_score -= len(verification["recommendations"]) * 10
        
        # Adjust based on resource balance (penalize extreme imbalances)
        if verification["resource_balance"]:
            balance_values = list(verification["resource_balance"].values())
            if max(balance_values) > 0.8:  # Dominated by one resource type
                allocation_score -= 15
        
        # Floor at 0
        allocation_score = max(0.0, allocation_score)
        verification["allocation_score"] = allocation_score
        
        # Provide qualitative assessment
        if allocation_score >= 90:
            verification["assessment"] = "Excellent"
        elif allocation_score >= 75:
            verification["assessment"] = "Good"
        elif allocation_score >= 50:
            verification["assessment"] = "Adequate"
        elif allocation_score >= 25:
            verification["assessment"] = "Poor"
        else:
            verification["assessment"] = "Critical"
        
        return verification
        
    def get_optimization_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive report of all optimizations applied during compilation.
        
        This collects information from multiple sources to give users a complete picture
        of what optimizations were performed and their impact on the hardware design.
        
        Returns:
            Dictionary containing detailed optimization information
        """
        # Log that we're generating an optimization report
        logger.debug("Generating comprehensive optimization report")
        
        report = {
            "optimization_level": self.optimization_level,
            "technology_node": self.tech_node,
            "applied_optimizations": [],
            "loop_optimizations": {
                "unrolling": None,
                "pipelining": []
            },
            "scheduling": {},
            "allocation": {},
            "resource_optimization": {},
            "optimizer_details": self._get_optimizer_details(),
            "suggestions": []
        }
        
        # 1. General optimization info
        if self.optimization_level == 0:
            report["applied_optimizations"].append("No optimizations applied (optimization level 0)")
        elif self.optimization_level == 1:
            report["applied_optimizations"].extend([
                "Common subexpression elimination",
                "Dead code elimination",
                "Constant propagation"
            ])
        elif self.optimization_level == 2:
            report["applied_optimizations"].extend([
                "Common subexpression elimination",
                "Dead code elimination", 
                "Constant propagation",
                "Register sharing",
                "Basic loop optimizations"
            ])
        elif self.optimization_level >= 3:
            report["applied_optimizations"].extend([
                "Advanced common subexpression elimination",
                "Dead code elimination",
                "Constant propagation",
                "Register sharing",
                "Advanced dataflow optimizations",
                "Loop unrolling",
                "Loop pipelining where possible"
            ])
        
        logger.debug(f"Applied {len(report['applied_optimizations'])} optimization techniques")
        
        # 2. Collect loop unrolling information
        logger.debug("Collecting loop unrolling information")
        unroll_report = self.get_loop_unrolling_report()
        report["loop_optimizations"]["unrolling"] = unroll_report
        
        if unroll_report and "unrolled_loops" in unroll_report:
            logger.debug(f"Found {unroll_report['unrolled_loops']} unrolled loops")
        
        # 3. Collect loop pipelining information
        logger.debug("Collecting loop pipelining information")
        if self.scheduled_ir:
            for func_name, func in self.scheduled_ir.functions.items():
                if hasattr(func, 'enable_pipeline') and func.enable_pipeline:
                    pipeline_info = {
                        "function": func_name,
                        "pipeline_depth": getattr(func, 'pipeline_depth', 1),
                        "enabled": True
                    }
                    report["loop_optimizations"]["pipelining"].append(pipeline_info)
                    logger.debug(f"Function {func_name} has pipelining enabled with depth {pipeline_info['pipeline_depth']}")
        
        # 4. Check for matrix operation optimizations
        logger.debug("Checking for matrix operation optimizations")
        if self.ir:
            for func_name, func in self.ir.functions.items():
                if hasattr(func, 'has_matrix_operations') and func.has_matrix_operations:
                    matrix_opt = f"Matrix operation optimizations for function {func_name}"
                    pipeline_opt = f"Automatic loop pipelining for matrix operations (depth: {getattr(func, 'pipeline_depth', 1)})"
                    report["applied_optimizations"].append(matrix_opt)
                    report["applied_optimizations"].append(pipeline_opt)
                    logger.debug(f"Applied {matrix_opt}")
                    logger.debug(f"Applied {pipeline_opt}")
        
        # 5. Resource allocation strategy
        logger.debug("Collecting resource allocation information")
        if hasattr(self, 'allocated_resources') and self.allocated_resources:
            strategy = "area" if self.optimization_level < 2 else "performance"
            report["allocation"] = {
                "strategy": strategy,
                "resources": self.allocated_resources
            }
            logger.debug(f"Resource allocation strategy: {strategy}")
            
        # 6. Get scheduling information
        logger.debug("Collecting scheduling information")
        if self.scheduled_ir:
            # Determine which scheduling algorithm was used
            if hasattr(self, 'asap_scheduler') and self.asap_scheduler:
                algorithm = "ASAP (As Soon As Possible)"
            elif hasattr(self, 'alap_scheduler') and self.alap_scheduler:
                algorithm = "ALAP (As Late As Possible)"
            elif hasattr(self, 'list_scheduler') and self.list_scheduler:
                algorithm = "List Scheduling"
            else:
                algorithm = "Unknown"
                
            report["scheduling"]["algorithm"] = algorithm
            logger.debug(f"Scheduling algorithm: {algorithm}")
                
            # Get max latency information from scheduled functions
            max_latency = 0
            for func_name, func in self.scheduled_ir.functions.items():
                if hasattr(func, 'total_latency') and func.total_latency > max_latency:
                    max_latency = func.total_latency
                elif hasattr(func, 'single_iter_latency') and func.single_iter_latency > max_latency:
                    max_latency = func.single_iter_latency
                    
            report["scheduling"]["max_latency_cycles"] = max_latency
            logger.debug(f"Maximum latency: {max_latency} cycles")
        
        # 7. Get verification/assessment information
        logger.debug("Verifying hardware allocation")
        verification = self.verify_hardware_allocation()
        if verification and verification["allocation_score"] != "N/A":
            report["resource_optimization"] = verification
            logger.debug(f"Resource allocation score: {verification['allocation_score']}")
            
            # Add verification recommendations to suggestions
            if "recommendations" in verification:
                for rec in verification["recommendations"]:
                    report["suggestions"].append(rec["message"])
        
        # 8. Add performance metrics if available
        metrics = self.get_performance_metrics()
        if metrics:
            report["performance"] = metrics
            
            # Add appropriate suggestions based on performance
            if metrics.get("latency_cycles", 0) > 100:
                report["suggestions"].append(
                    "Consider enabling more aggressive loop optimizations to reduce latency"
                )
            
            if metrics.get("total_area", 0) > 1000000:  # Large area
                report["suggestions"].append(
                    "Area utilization is high. Consider reducing bit-widths or resource sharing"
                )
                
        return report
        
    def _get_optimizer_details(self) -> Dict[str, Any]:
        """
        Generate detailed information about what happens during optimization.
        
        Returns:
            Dictionary containing details of each optimization pass
        """
        optimizer_details = {
            "optimization_level": self.optimization_level,
            "passes": [],
            "stats": {}
        }
        
        # Determine which passes are applied at the current optimization level
        if self.optimization_level == 0:
            optimizer_details["passes"] = []
        elif self.optimization_level == 1:
            optimizer_details["passes"] = ["constant_folding", "dead_code_elimination"]
        elif self.optimization_level == 2:
            optimizer_details["passes"] = [
                "constant_folding", 
                "dead_code_elimination", 
                "common_subexpression_elimination", 
                "loop_invariant_code_motion"
            ]
        elif self.optimization_level >= 3:
            optimizer_details["passes"] = [
                "constant_folding", 
                "dead_code_elimination", 
                "common_subexpression_elimination", 
                "loop_invariant_code_motion", 
                "function_inlining", 
                "loop_unrolling", 
                "resource_sharing"
            ]
        
        # Detailed description of each pass
        optimizer_details["pass_details"] = {
            "constant_folding": {
                "description": "Evaluates constant expressions at compile time",
                "process": "Identifies arithmetic operations with constant operands and computes them at compile time",
                "impact": "Reduces runtime computation and simplifies logic"
            },
            "dead_code_elimination": {
                "description": "Removes code that doesn't affect the output",
                "process": "Tracks variable usage from output backwards, removing operations that don't contribute to results",
                "impact": "Reduces resource usage by eliminating unnecessary operations"
            },
            "common_subexpression_elimination": {
                "description": "Identifies and removes redundant computations",
                "process": "Creates a map of expressions to results, reusing previously computed values when possible",
                "impact": "Reduces duplicate calculations, saving hardware resources"
            },
            "loop_invariant_code_motion": {
                "description": "Moves loop-invariant code outside of loops",
                "process": "Identifies operations in loops that have the same result each iteration, moving them before the loop",
                "impact": "Reduces redundant calculations and improves loop performance"
            },
            "function_inlining": {
                "description": "Replaces function calls with the function body",
                "process": "Substitutes function calls with the actual code from the function definition",
                "impact": "Eliminates function call overhead and enables more cross-function optimizations"
            },
            "loop_unrolling": {
                "description": "Replicates loop body to reduce loop iterations",
                "process": "Duplicates loop body operations to execute multiple iterations in parallel",
                "impact": "Reduces iteration count and increases parallelism at the cost of more hardware resources"
            },
            "resource_sharing": {
                "description": "Identifies operations that can share hardware resources",
                "process": "Maps operations that don't execute simultaneously to the same hardware units",
                "impact": "Reduces hardware resource usage at the cost of potential routing complexity"
            }
        }
        
        # Gather statistics if IR is available
        if self.optimized_ir and self.ir:
            # Basic statistics
            orig_op_count = 0
            opt_op_count = 0
            
            # Count operations in original IR
            for func_name, func in self.ir.functions.items():
                for block in func.blocks:
                    for instr in block.instructions:
                        orig_op_count += len(instr.operations)
            
            # Count operations in optimized IR
            for func_name, func in self.optimized_ir.functions.items():
                for block in func.blocks:
                    for instr in block.instructions:
                        opt_op_count += len(instr.operations)
            
            # Calculate reduction percentage
            reduction = 0
            if orig_op_count > 0:
                reduction = ((orig_op_count - opt_op_count) / orig_op_count) * 100
            
            optimizer_details["stats"] = {
                "original_operation_count": orig_op_count,
                "optimized_operation_count": opt_op_count,
                "operation_reduction_percent": reduction,
                "constants_folded": getattr(self.optimizer, "constants_folded", 0),
                "dead_ops_removed": getattr(self.optimizer, "dead_ops_removed", 0),
                "common_subexpr_eliminated": getattr(self.optimizer, "common_subexpr_eliminated", 0),
                "loops_unrolled": getattr(self.optimizer, "loops_unrolled", 0)
            }
        
        return optimizer_details
        
    def get_optimization_summary(self) -> str:
        """
        Generate a human-readable summary of optimizations applied during synthesis.
        
        Returns:
            String containing a text summary of all optimizations 
        """
        # Get the full report first
        report = self.get_optimization_report()
        if not report:
            return "No optimization report available."
        
        # Build a formatted summary
        summary = []
        summary.append("OPTIMIZATION SUMMARY")
        summary.append("===================")
        summary.append("")
        
        # Basic information
        summary.append(f"Technology node: {report['technology_node']} nm")
        summary.append(f"Optimization level: {report['optimization_level']}")
        if "scheduling" in report and "algorithm" in report["scheduling"]:
            summary.append(f"Scheduling algorithm: {report['scheduling']['algorithm']}")
        summary.append("")
        
        # Optimizer details section
        if "optimizer_details" in report:
            opt_details = report["optimizer_details"]
            summary.append("OPTIMIZER EXECUTION DETAILS")
            summary.append("---------------------------")
            
            # List optimization passes that were executed
            if "passes" in opt_details:
                summary.append("Optimization passes executed in sequence:")
                for pass_name in opt_details["passes"]:
                    if "pass_details" in opt_details and pass_name in opt_details["pass_details"]:
                        pass_info = opt_details["pass_details"][pass_name]
                        summary.append(f"  - {pass_name}: {pass_info['description']}")
                        summary.append(f"    Process: {pass_info['process']}")
                        summary.append(f"    Impact: {pass_info['impact']}")
            
            # Add optimization statistics if available
            if "stats" in opt_details and opt_details["stats"]:
                stats = opt_details["stats"]
                summary.append("")
                summary.append("Optimization statistics:")
                if "original_operation_count" in stats:
                    summary.append(f"  - Original operation count: {stats['original_operation_count']}")
                if "optimized_operation_count" in stats:
                    summary.append(f"  - Optimized operation count: {stats['optimized_operation_count']}")
                if "operation_reduction_percent" in stats:
                    summary.append(f"  - Operation reduction: {stats['operation_reduction_percent']:.1f}%")
                if "constants_folded" in stats and stats["constants_folded"] > 0:
                    summary.append(f"  - Constants folded: {stats['constants_folded']}")
                if "dead_ops_removed" in stats and stats["dead_ops_removed"] > 0:
                    summary.append(f"  - Dead operations removed: {stats['dead_ops_removed']}")
                if "common_subexpr_eliminated" in stats and stats["common_subexpr_eliminated"] > 0:
                    summary.append(f"  - Common subexpressions eliminated: {stats['common_subexpr_eliminated']}")
                if "loops_unrolled" in stats and stats["loops_unrolled"] > 0:
                    summary.append(f"  - Loops unrolled: {stats['loops_unrolled']}")
            
            summary.append("")
        
        # Applied optimizations
        summary.append("Applied optimizations:")
        for opt in report["applied_optimizations"]:
            summary.append(f"  - {opt}")
        summary.append("")
        
        # Loop optimizations
        unrolling = report["loop_optimizations"]["unrolling"]
        if unrolling and unrolling.get("unrolled_loops", 0) > 0:
            summary.append("Loop unrolling:")
            summary.append(f"  Total unrolled loops: {unrolling.get('unrolled_loops', 0)}")
            summary.append(f"  Fully unrolled loops: {unrolling.get('fully_unrolled', 0)}")
            summary.append(f"  Partially unrolled loops: {unrolling.get('partially_unrolled', 0)}")
            
            # Add details about each unrolled loop if available
            if "loops" in unrolling and unrolling["loops"]:
                summary.append("  Loop details:")
                for loop in unrolling["loops"]:
                    if loop.get("is_unrolled", False):
                        unroll_type = "fully" if loop.get("full_unroll", False) else f"partially (factor: {loop.get('unroll_factor', 1)})"
                        summary.append(f"    - {loop.get('function', 'Unknown function')}: Loop {loop.get('loop_name', 'at index ' + str(loop.get('loop_index', 0)))} unrolled {unroll_type}")
            summary.append("")
            
        pipelining = report["loop_optimizations"]["pipelining"]
        if pipelining:
            summary.append("Loop pipelining:")
            for pipeline in pipelining:
                summary.append(f"  - Function {pipeline['function']} with pipeline depth {pipeline['pipeline_depth']}")
            summary.append("")
        
        # Resource allocation
        if "allocation" in report and "strategy" in report["allocation"]:
            summary.append(f"Resource allocation strategy: {report['allocation']['strategy']}")
            summary.append("")
        
        # Performance metrics
        if "performance" in report:
            perf = report["performance"]
            summary.append("Performance metrics:")
            if "latency_cycles" in perf:
                summary.append(f"  - Latency: {perf['latency_cycles']} cycles")
            if "latency_ns" in perf:
                summary.append(f"  - Estimated execution time: {perf['latency_ns']:.2f} ns")
            if "clock_frequency_mhz" in perf:
                summary.append(f"  - Clock frequency: {perf['clock_frequency_mhz']:.2f} MHz")
            if "total_area" in perf:
                summary.append(f"  - Total area: {perf['total_area']:.2f} μm²")
            if "total_power" in perf:
                summary.append(f"  - Estimated power: {perf['total_power']:.2f} mW")
            summary.append("")
        
        # Resource assessment
        if "resource_optimization" in report:
            res_opt = report["resource_optimization"]
            if "assessment" in res_opt:
                summary.append(f"Resource allocation assessment: {res_opt['assessment']}")
            if "allocation_score" in res_opt and res_opt["allocation_score"] != "N/A":
                summary.append(f"Resource allocation score: {res_opt['allocation_score']:.1f}/100")
            summary.append("")
        
        # Suggestions
        if report["suggestions"]:
            summary.append("Optimization suggestions:")
            for suggestion in report["suggestions"]:
                summary.append(f"  - {suggestion}")
        
        # Join all lines with newlines
        return "\n".join(summary)

    def get_synthesis_logs(self, log_file_path: str = None) -> str:
        """
        Read the synthesis logs from a file.
        
        Args:
            log_file_path: Path to the synthesis log file.
                          If None, tries to use the stored synthesis log path.
        
        Returns:
            String containing the synthesis logs
        """
        if log_file_path is None:
            # Try to use the stored synthesis log path
            if hasattr(self, 'synthesis_log_path') and self.synthesis_log_path:
                log_file_path = self.synthesis_log_path
            elif self.source_file is not None:
                # Determine log file path based on source file
                base, _ = os.path.splitext(self.source_file)
                log_file_path = f"{base}_synthesis.log"
            else:
                return "No source file or log path available. Run compile() first."
            
        # Check if the log file exists
        if not os.path.exists(log_file_path):
            return f"Log file not found: {log_file_path}"
            
        # Read log file contents
        try:
            with open(log_file_path, 'r') as f:
                log_contents = f.read()
            return log_contents
        except Exception as e:
            return f"Error reading log file: {str(e)}"

    def get_synthesis_data_for_frontend(self, compilation_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get all synthesis data and logs in a format ready to send to a frontend application.
        
        Args:
            compilation_result: The result of a previous compilation.
                              If None, attempts to gather data from current state.
        
        Returns:
            Dictionary containing all synthesis data and logs
        """
        if compilation_result is None:
            # Try to gather data from current state
            if self.netlist is None or self.source_file is None:
                return {"error": "No compilation data available. Run compile() first."}
            
            # Determine log file path based on source file
            base, _ = os.path.splitext(self.source_file)
            log_file_path = f"{base}_synthesis.log"
            
            # Generate reports
            try:
                optimization_report = self.get_optimization_report()
                performance_metrics = self.get_performance_metrics()
                optimization_summary = self.get_optimization_summary()
                resource_report = self.get_resource_report()
            except Exception as e:
                return {"error": f"Error generating reports: {str(e)}"}
        else:
            # Extract data from the compilation result
            optimization_report = compilation_result.get("optimization_report", {})
            performance_metrics = compilation_result.get("performance_metrics", {})
            optimization_summary = compilation_result.get("optimization_summary", "")
            log_file_path = compilation_result.get("log_file_path", "")
            
            # Get resource report
            try:
                resource_report = self.get_resource_report()
            except Exception:
                resource_report = {}
        
        # Read the synthesis logs
        synthesis_logs = self.get_synthesis_logs(log_file_path)
        
        # Combine all data
        frontend_data = {
            "performance_metrics": performance_metrics,
            "optimization_report": optimization_report,
            "optimization_summary": optimization_summary,
            "resource_report": resource_report,
            "log_file_path": log_file_path,
            "synthesis_logs": synthesis_logs
        }
        
        return frontend_data 

    def get_synthesis_log_path(self) -> str:
        """
        Get the path to the current synthesis log file.
        
        Returns:
            Path to the synthesis log file, or None if no compilation has been done
        """
        if hasattr(self, 'synthesis_log_path') and self.synthesis_log_path:
            return self.synthesis_log_path
        elif self.source_file:
            # Generate log file path based on source file name
            base, _ = os.path.splitext(self.source_file)
            return f"{base}_synthesis.log"
        else:
            return None
    
    def verify_rtl(self, 
                   test_vectors: Optional[List[Dict[str, Any]]] = None,
                   num_random_tests: int = 100,
                   save_report: bool = True,
                   save_testbenches: bool = False) -> Dict[str, Any]:
        """
        Verify the generated RTL against the original Python source.
        
        Args:
            test_vectors: Optional list of test vectors to use
            num_random_tests: Number of random test vectors to generate if none provided
            save_report: Whether to save the verification report to a file
            save_testbenches: Whether to save the generated testbench code to files
            
        Returns:
            Verification results dictionary including all generated testbench code
        """
        if not self.source_file:
            logger.error("No source file available for verification")
            return {"error": "No source file available"}
        
        if not self.netlist:
            logger.error("No netlist available for verification. Run compilation first.")
            return {"error": "No netlist available"}
        
        logger.info("Starting RTL verification")
        
        # Run verification
        verification_results = self.rtl_verifier.verify_hls_compilation(
            self.source_file, 
            self,
            test_vectors=test_vectors,
            num_random_tests=num_random_tests
        )
        
        # Save report if requested
        if save_report and "report" in verification_results:
            base_name = os.path.splitext(os.path.basename(self.source_file))[0]
            report_file = f"{base_name}_verification_report.txt"
            
            try:
                with open(report_file, 'w') as f:
                    f.write(verification_results["report"])
                logger.info(f"Verification report saved to {report_file}")
                verification_results["report_file"] = report_file
            except Exception as e:
                logger.warning(f"Could not save verification report: {str(e)}")
        
        # Save testbench code if requested
        if save_testbenches and "generated_testbenches" in verification_results:
            base_name = os.path.splitext(os.path.basename(self.source_file))[0]
            
            for module_name, testbench_info in verification_results["generated_testbenches"].items():
                if "code" in testbench_info:
                    # Save Verilog testbench
                    if "verilog_testbench" in testbench_info["code"]:
                        verilog_tb_file = f"{base_name}_{module_name}_tb.v"
                        try:
                            with open(verilog_tb_file, 'w') as f:
                                f.write(testbench_info["code"]["verilog_testbench"])
                            logger.info(f"Verilog testbench saved to {verilog_tb_file}")
                            testbench_info["saved_files"] = testbench_info.get("saved_files", {})
                            testbench_info["saved_files"]["verilog_testbench"] = verilog_tb_file
                        except Exception as e:
                            logger.warning(f"Could not save Verilog testbench for {module_name}: {str(e)}")
                    
                    # Save C++ testbench
                    if "cpp_testbench" in testbench_info["code"]:
                        cpp_tb_file = f"{base_name}_{module_name}_tb.cpp"
                        try:
                            with open(cpp_tb_file, 'w') as f:
                                f.write(testbench_info["code"]["cpp_testbench"])
                            logger.info(f"C++ testbench saved to {cpp_tb_file}")
                            testbench_info["saved_files"] = testbench_info.get("saved_files", {})
                            testbench_info["saved_files"]["cpp_testbench"] = cpp_tb_file
                        except Exception as e:
                            logger.warning(f"Could not save C++ testbench for {module_name}: {str(e)}")
        
        return verification_results
    
    # ==========================================================================
    # Refactor Equivalence Checking
    # ==========================================================================
    
    def check_equivalence(
        self,
        other_source: str,
        mode: str = 'functional',
        test_vectors: Optional[List[Dict[str, int]]] = None,
    ) -> EquivalenceResult:
        """
        Check if the current compilation is equivalent to another source.
        
        This is the core "refactor safety" feature: verify that code changes
        preserve hardware behavior.
        
        Args:
            other_source: Path to another Python source file, or source code string
            mode: Equivalence mode - 'functional', 'bit_exact', or 'cycle_accurate'
            test_vectors: Optional test vectors (generates random if not provided)
            
        Returns:
            EquivalenceResult indicating pass/fail and details
            
        Example:
            >>> hls = HLS(strict_mode=True)
            >>> hls.compile('original.py')
            >>> result = hls.check_equivalence('refactored.py')
            >>> if not result:
            ...     print(f"Refactor broke behavior: {result.summary()}")
        """
        if not self.source_file:
            raise ValueError("No source file compiled. Call compile() first.")
        
        # Read current source
        with open(self.source_file, 'r') as f:
            current_source = f.read()
        
        # Read other source
        if os.path.isfile(other_source):
            with open(other_source, 'r') as f:
                other_source_code = f.read()
        else:
            other_source_code = other_source
        
        # Map mode string to enum
        mode_map = {
            'functional': EquivalenceMode.FUNCTIONAL,
            'bit_exact': EquivalenceMode.BIT_EXACT,
            'cycle_accurate': EquivalenceMode.CYCLE_ACCURATE,
        }
        equiv_mode = mode_map.get(mode.lower(), EquivalenceMode.FUNCTIONAL)
        
        # Run equivalence check
        checker = EquivalenceChecker(self)
        return checker.check_source_equivalence(
            current_source, 
            other_source_code, 
            equiv_mode,
            test_vectors
        )
    
    def create_equivalence_fingerprint(
        self,
        test_vectors: Optional[List[Dict[str, int]]] = None,
        num_random_tests: int = 100,
    ):
        """
        Create a fingerprint of the current compilation for later equivalence checks.
        
        Save this fingerprint to verify future versions against known-good behavior.
        
        Args:
            test_vectors: Optional explicit test vectors
            num_random_tests: Number of random tests if no vectors provided
            
        Returns:
            CompilationFingerprint that can be saved and compared later
        """
        if not self.source_file:
            raise ValueError("No source file compiled. Call compile() first.")
        
        with open(self.source_file, 'r') as f:
            source = f.read()
        
        checker = EquivalenceChecker(self)
        return checker.create_fingerprint(
            source,
            test_vectors=test_vectors,
            num_random_tests=num_random_tests,
        )

    def compile_pipeline(
        self,
        source: Union[str, Callable],
        entry_function: Optional[str] = None,
        ii: int = 1,
        depth: Optional[int] = None,
        interface: str = "axis",
        data_width: int = 32,
        output_file: Optional[str] = None,
    ) -> str:
        """
        Compile a Python function into a synthesizable, cycle-accounted hardware pipeline.
        
        Args:
            source: Path to Python file, source code string, or Python callable
            entry_function: Function name to compile
            ii: Initiation interval target (>= 1)
            depth: Pipeline depth / latency in cycles (>= 1)
            interface: Hardware interface ('axis', 'ready_valid', or 'memory')
            data_width: Data bus bit width
            output_file: Optional path to write generated Verilog
            
        Returns:
            Generated Verilog code as string
        """
        from .pipeline import PipelineSpec, PipelineVerilogGenerator
        
        spec = PipelineSpec(
            ii=ii,
            depth=depth or 2,
            interface=interface,
            data_width=data_width,
        )
        generator = PipelineVerilogGenerator(spec)
        
        if callable(source):
            code = generator.generate_from_function(source, spec)
        elif os.path.isfile(source):
            with open(source, 'r') as f:
                content = f.read()
            code = generator.generate_from_source(content, entry_function, spec)
        else:
            code = generator.generate_from_source(source, entry_function, spec)
            
        if output_file:
            with open(output_file, 'w') as f:
                f.write(code)
                
        return code

    def verify_pipeline(
        self,
        source: Union[str, Callable],
        entry_function: Optional[str] = None,
        ii: int = 1,
        depth: Optional[int] = None,
        interface: str = "axis",
        test_vectors: Optional[List[Tuple[Any, ...]]] = None,
        test_stalls: bool = True,
        test_bubbles: bool = True,
    ):
        """
        Co-simulate and verify a constraint-driven pipeline with Verilator.
        
        Args:
            source: Path to Python file, source code string, or Python callable
            entry_function: Function name to verify
            ii: Initiation interval target (>= 1)
            depth: Pipeline depth / latency in cycles (>= 1)
            interface: Hardware interface ('axis', 'ready_valid', or 'memory')
            test_vectors: Optional custom test vectors
            test_stalls: Whether to test backpressure stall handling
            test_bubbles: Whether to test bubble propagation
            
        Returns:
            PipelineVerificationResult
        """
        from .pipeline import PipelineSpec, PipelineVerifier
        
        spec = PipelineSpec(
            ii=ii,
            depth=depth or 2,
            interface=interface,
        )
        verifier = PipelineVerifier()
        
        if callable(source):
            return verifier.verify_pipeline(
                source, spec=spec, test_vectors=test_vectors,
                test_stalls=test_stalls, test_bubbles=test_bubbles
            )
        
        if os.path.isfile(source):
            with open(source, 'r') as f:
                src_code = f.read()
        else:
            src_code = source
            
        namespace: Dict[str, Any] = {}
        exec(src_code, namespace)
        fn_name = entry_function
        if fn_name is None:
            import ast
            tree = ast.parse(src_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    fn_name = node.name
                    break
        if not fn_name or fn_name not in namespace:
            raise ValueError(f"Function {fn_name} not found in source")
            
        func = namespace[fn_name]
        return verifier.verify_pipeline(
            func, spec=spec, test_vectors=test_vectors,
            test_stalls=test_stalls, test_bubbles=test_bubbles,
            source=src_code
        )

