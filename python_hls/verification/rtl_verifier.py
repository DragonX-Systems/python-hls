"""
RTL Verifier for comparing Verilog simulation results with Python execution.
"""

import os
import subprocess
import tempfile
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import json
import time
import re
import ast

from .testbench_generator import TestbenchGenerator
from .python_executor import PythonExecutor
from .exceptions import (
    RTLVerificationError,
    RTLVerificationInterfaceError,
    RTLSimulationTimeoutError,
    RTLMismatchError
)

logger = logging.getLogger(__name__)


class RTLVerifier:
    """
    Main class for verifying RTL generation by comparing simulation results
    with original Python execution.
    """
    
    def __init__(self, verilator_path: str = "verilator", max_cycles: int = 1000):
        """
        Initialize the RTL verifier.
        
        Args:
            verilator_path: Path to verilator executable
            max_cycles: Default maximum simulation cycles per test
        """
        self.verilator_path = verilator_path
        self.max_cycles = max_cycles
        self.testbench_generator = TestbenchGenerator(max_cycles=max_cycles)
        self.python_executor = PythonExecutor()
        
        # Check if verilator is available, searching standard toolchain fallbacks
        if not self._check_verilator():
            candidates = [
                "/Users/rigelsmacbook/oss-cad-suite/bin/verilator",
                "/usr/local/bin/verilator",
                "/opt/homebrew/bin/verilator",
                os.path.expanduser("~/oss-cad-suite/bin/verilator")
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    self.verilator_path = cand
                    if self._check_verilator():
                        break
        
        if not self._check_verilator():
            logger.warning("Verilator not found. RTL verification will be disabled.")
            self.verilator_available = False
        else:
            self.verilator_available = True
            logger.info(f"Verilator found at {self.verilator_path} and ready for RTL verification")
    
    def _check_verilator(self) -> bool:
        """Check if Verilator is available."""
        try:
            result = subprocess.run([self.verilator_path, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _get_warning_flags(self) -> List[str]:
        """Return warning suppression flags dynamically supported by the installed Verilator."""
        if hasattr(self, "_cached_warning_flags") and self._cached_warning_flags is not None:
            return self._cached_warning_flags

        candidate_flags = [
            "-Wno-DECLFILENAME",
            "-Wno-UNUSEDSIGNAL",
            "-Wno-UNUSEDPARAM",
            "-Wno-MULTIDRIVEN",
            "-Wno-MULTIDRIVENPROC",
            "-Wno-WIDTH",
            "-Wno-WIDTHTRUNC",
            "-Wno-WIDTHEXPAND",
        ]
        supported = []
        for flag in candidate_flags:
            try:
                res = subprocess.run(
                    [self.verilator_path, "--lint-only", flag, "/dev/null"],
                    capture_output=True, text=True, timeout=2
                )
                if "Unknown warning specified" not in res.stderr:
                    supported.append(flag)
            except Exception:
                pass
        self._cached_warning_flags = supported
        return self._cached_warning_flags
    
    @staticmethod
    def load_test_vectors(file_path: str) -> List[Dict[str, Any]]:
        """Load test vectors from a JSON or YAML file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Test vectors file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            if file_path.endswith(('.yaml', '.yml')):
                try:
                    import yaml
                    data = yaml.safe_load(f)
                except ImportError:
                    raise ImportError("PyYAML is required to load YAML test vector files")
            else:
                data = json.load(f)
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "test_vectors" in data:
            return data["test_vectors"]
        else:
            raise ValueError(f"Invalid test vector format in {file_path}: expected list or dict with 'test_vectors'")

    def verify_hls_compilation(self, 
                             source_file: str, 
                             hls_instance: Any,
                             test_vectors: Optional[List[Dict[str, Any]]] = None,
                             num_random_tests: int = 100,
                             seed: Optional[int] = 42,
                             max_cycles: int = 1000,
                             vcd: bool = False,
                             artifact_dir: Optional[str] = None,
                             strict: bool = False,
                             timeout: int = 60) -> Dict[str, Any]:
        """
        Verify HLS compilation by comparing RTL simulation with Python execution.
        
        Args:
            source_file: Path to Python source file
            hls_instance: HLS compiler instance with compiled netlist
            test_vectors: Optional list of test vectors to use
            num_random_tests: Number of random test vectors to generate
            seed: Seed for reproducible random test-vector generation
            max_cycles: Maximum simulation cycles before timeout
            vcd: Whether to dump VCD waveform trace
            artifact_dir: Directory to preserve artifacts (.v, .cpp, exe, vcd, logs)
            strict: Whether to raise RTLMismatchError / RTLVerificationError on failures
            timeout: Subprocess timeout in seconds
            
        Returns:
            Verification results dictionary including all generated testbench code
        """
        if not self.verilator_available:
            logger.error("Verilator not available. Cannot perform RTL verification.")
            if strict:
                raise RTLVerificationError("Verilator not available on host system")
            return {"error": "Verilator not available"}
        
        logger.info(f"Starting RTL verification for {source_file}")
        
        # Extract function information from HLS instance
        if not hasattr(hls_instance, 'netlist') or not hls_instance.netlist:
            logger.error("No netlist available in HLS instance")
            if strict:
                raise RTLVerificationError("No netlist available in HLS instance")
            return {"error": "No netlist available"}
        
        verification_results = {}
        generated_testbenches = {}  # Store all generated testbench code
        
        # RTL verification for all modules (including those with array parameters)
        for module_name, module in hls_instance.netlist.modules.items():
            logger.info(f"Verifying module: {module_name}")
            
            try:
                # Extract actual port information from generated Verilog
                port_info = self._extract_module_port_info(module)
                if not port_info:
                    logger.warning(f"Could not extract port info for {module_name}")
                    continue
                
                # Get function information from IR or source
                func_info = self._extract_function_info(hls_instance, module_name)
                
                # Check for explicit unsupported interfaces (e.g., multi-value tuple returns)
                if func_info and func_info.get("has_multi_return"):
                    data_outputs = [
                        p for p in port_info.get("output_ports", [])
                        if p["name"] not in ["valid", "done"] and not self._is_array_interface_signal(p["name"])
                    ]
                    if len(data_outputs) <= 1:
                        msg = (f"Function '{module_name}' contains a multi-value return, "
                               f"which is not yet qualified for automated RTL simulation verification.")
                        if strict:
                            raise RTLVerificationInterfaceError(msg, module_name=module_name)
                        else:
                            logger.warning(msg)
                            verification_results[module_name] = {
                                "error": msg,
                                "interface_unsupported": True
                            }
                            continue
                
                # Generate test vectors using port information and seed
                module_test_vectors = test_vectors
                if module_test_vectors is None:
                    logger.debug(f"Generating test vectors from ports for {module_name} (seed={seed})")
                    module_test_vectors = self._generate_test_vectors_from_ports(
                        port_info, num_random_tests, seed=seed
                    )
                
                # Execute Python function with original parameter names
                logger.debug(f"About to execute Python function - test_vectors count: {len(module_test_vectors)}")
                
                # Extract output bit width from port information for RTL simulation
                output_bitwidth = 32  # Default
                if port_info and "output_ports" in port_info and len(port_info["output_ports"]) > 0:
                    output_bitwidth = port_info["output_ports"][0]["bit_width"]
                    logger.debug(f"Using output bit width: {output_bitwidth}")
                
                python_results = self.python_executor.execute_function(
                    source_file, module_name, module_test_vectors,
                    simulate_rtl_bitwidth=True,
                    output_bitwidth=output_bitwidth
                )
                
                logger.debug(f"Python results count: {len(python_results.get('results', [])) if isinstance(python_results, dict) else 'N/A'}")
                
                # Generate Verilog for this module
                verilog_file = self._save_module_verilog(module, module_name)
                
                # Generate testbenches and capture their code
                testbench_files = {}
                testbench_code = {}
                
                # Generate Verilog testbench
                try:
                    verilog_testbench_file = self.testbench_generator.generate_testbench(
                        module, port_info, module_test_vectors, f"{module_name}_tb"
                    )
                    testbench_files["verilog_testbench"] = verilog_testbench_file
                    
                    with open(verilog_testbench_file, 'r') as f:
                        testbench_code["verilog_testbench"] = f.read()
                except Exception as e:
                    logger.warning(f"Failed to generate Verilog testbench for {module_name}: {str(e)}")
                    testbench_code["verilog_testbench"] = f"Error generating Verilog testbench: {str(e)}"
                
                # Generate C++ testbench with max_cycles and VCD support
                try:
                    cpp_testbench_file = self.testbench_generator.generate_cpp_testbench(
                        module, port_info, module_test_vectors, f"{module_name}_tb",
                        max_cycles=max_cycles,
                        vcd_file=f"{module_name}_tb.vcd" if vcd else None
                    )
                    testbench_files["cpp_testbench"] = cpp_testbench_file
                    
                    with open(cpp_testbench_file, 'r') as f:
                        testbench_code["cpp_testbench"] = f.read()
                except Exception as e:
                    logger.warning(f"Failed to generate C++ testbench for {module_name}: {str(e)}")
                    testbench_code["cpp_testbench"] = f"Error generating C++ testbench: {str(e)}"
                
                # Store testbench information
                generated_testbenches[module_name] = {
                    "files": testbench_files,
                    "code": testbench_code,
                    "port_info": port_info,
                    "test_vectors_count": len(module_test_vectors)
                }
                
                # Run RTL simulation only if we have a valid testbench file
                cpp_testbench_file = testbench_files.get("cpp_testbench")
                if cpp_testbench_file and os.path.exists(cpp_testbench_file):
                    logger.info(f"Running RTL simulation for {module_name}")
                    rtl_results = self._run_rtl_simulation(
                        verilog_file, cpp_testbench_file, module_name,
                        max_cycles=max_cycles,
                        vcd=vcd,
                        timeout=timeout,
                        artifact_dir=artifact_dir,
                        test_vectors=module_test_vectors
                    )
                else:
                    logger.warning(f"No valid testbench file for {module_name}, skipping RTL simulation")
                    rtl_results = {"error": "No valid testbench file available"}
                
                # Compare results
                comparison = self._compare_results(
                    python_results, rtl_results, module_test_vectors
                )
                
                verification_results[module_name] = {
                    "python_results": python_results,
                    "rtl_results": rtl_results,
                    "comparison": comparison,
                    "test_vectors": module_test_vectors
                }
                
            except RTLVerificationError:
                raise
            except Exception as e:
                logger.error(f"Error verifying module {module_name}: {str(e)}")
                if strict:
                    raise RTLVerificationError(f"Verification error in {module_name}: {str(e)}", module_name=module_name)
                verification_results[module_name] = {
                    "error": str(e)
                }
                generated_testbenches[module_name] = {
                    "error": f"Failed to generate testbench: {str(e)}"
                }
        
        # Generate verification report
        report = self._generate_verification_report(verification_results)
        
        # Preserve report in artifact dir if configured
        if artifact_dir:
            try:
                os.makedirs(artifact_dir, exist_ok=True)
                report_path = os.path.join(artifact_dir, "verification_report.txt")
                with open(report_path, 'w') as f:
                    f.write(report)
            except Exception as e:
                logger.warning(f"Could not save report to {artifact_dir}: {e}")
        
        # Strict mode verification checks
        if strict:
            for mod_name, res in verification_results.items():
                if "error" in res:
                    raise RTLVerificationError(f"Module {mod_name} verification error: {res['error']}", module_name=mod_name)
                comp = res.get("comparison", {})
                if comp.get("failed", 0) > 0:
                    raise RTLMismatchError(
                        f"RTL simulation mismatch in module {mod_name}: {comp['failed']}/{comp['total_tests']} tests failed",
                        mismatch_count=comp["failed"],
                        total_tests=comp["total_tests"],
                        module_name=mod_name,
                        mismatches=comp.get("mismatches")
                    )
                if comp.get("errors"):
                    raise RTLVerificationError(
                        f"Verification errors in module {mod_name}: {'; '.join(comp['errors'])}",
                        module_name=mod_name
                    )

        logger.info("RTL verification completed")
        return {
            "verification_results": verification_results,
            "generated_testbenches": generated_testbenches,
            "report": report
        }
    
    def _extract_function_info(self, hls_instance: Any, function_name: str) -> Optional[Dict[str, Any]]:
        """Extract function information from HLS IR."""
        if not hasattr(hls_instance, 'ir') or not hls_instance.ir:
            logger.warning(f"No IR available in HLS instance for function {function_name}")
            return self._extract_function_info_from_source(hls_instance.source_file, function_name)
        
        if function_name not in hls_instance.ir.functions:
            logger.warning(f"Function {function_name} not found in IR")
            return self._extract_function_info_from_source(hls_instance.source_file, function_name)
        
        func = hls_instance.ir.functions[function_name]
        
        info_from_source = self._extract_function_info_from_source(hls_instance.source_file, function_name)
        has_multi = info_from_source.get("has_multi_return", False) if info_from_source else False

        return {
            "name": function_name,
            "parameters": [
                {
                    "name": param.name,
                    "type": param.data_type.name if hasattr(param.data_type, 'name') else str(param.data_type),
                    "bit_width": param.bit_width
                }
                for param in func.parameters
            ],
            "return_type": {
                "type": func.return_var.data_type.name if func.return_var and hasattr(func.return_var.data_type, 'name') else "void",
                "bit_width": func.return_var.bit_width if func.return_var else 0
            } if func.return_var else None,
            "has_multi_return": has_multi
        }
    
    def _extract_function_info_from_source(self, source_file: str, function_name: str) -> Optional[Dict[str, Any]]:
        """Extract function signature information directly from Python source."""
        try:
            
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            # Parse the Python source
            tree = ast.parse(source_code)
            
            # Cache the AST tree for use by other methods
            self._current_ast_tree = tree
            
            # Find the function definition
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    # Detect multi-value return statements
                    has_multi_return = False
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.Return) and isinstance(subnode.value, (ast.Tuple, ast.List)):
                            has_multi_return = True
                            break

                    # Extract parameter information
                    parameters = []
                    for arg in node.args.args:
                        param_info = {
                            "name": arg.arg,
                            "type": "unknown",  # We'll infer from usage
                            "is_array": False,
                            "bit_width": 32
                        }
                        
                        # Try to infer if parameter is used as an array
                        param_info["is_array"] = self._infer_array_usage(node, arg.arg)
                        parameters.append(param_info)
                    
                    return {
                        "name": function_name,
                        "parameters": parameters,
                        "return_type": {"type": "float", "bit_width": 32},
                        "has_multi_return": has_multi_return
                    }
            
            logger.warning(f"Function {function_name} not found in {source_file}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting function info from source: {str(e)}")
            return None
    
    def _infer_array_usage(self, func_node: ast.FunctionDef, param_name: str) -> bool:
        """Analyze actual Python code to detect if a parameter is used as an array."""
        
        # Direct array usage detection from AST
        for node in ast.walk(func_node):
            # Check for subscript access (param[index])
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id == param_name:
                    return True
            
            # Check for len() calls
            elif isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Name) and node.func.id == 'len' and
                    len(node.args) > 0 and isinstance(node.args[0], ast.Name) and
                    node.args[0].id == param_name):
                    return True
                    
                # Check for range(len(param))
                if (isinstance(node.func, ast.Name) and node.func.id == 'range' and
                    len(node.args) > 0 and isinstance(node.args[0], ast.Call) and
                    isinstance(node.args[0].func, ast.Name) and node.args[0].func.id == 'len' and
                    len(node.args[0].args) > 0 and isinstance(node.args[0].args[0], ast.Name) and
                    node.args[0].args[0].id == param_name):
                    return True
                    
                # Check if parameter is passed to functions that typically take arrays
                if len(node.args) > 0:
                    for i, arg in enumerate(node.args):
                        if isinstance(arg, ast.Name) and arg.id == param_name:
                            # If passed as argument to array-processing functions
                            if isinstance(node.func, ast.Name) and node.func.id in [
                                'sum', 'max', 'min', 'sorted', 'reversed', 'enumerate', 
                                'zip', 'map', 'filter', 'any', 'all'
                            ]:
                                return True
                            # Special case: range() takes scalar arguments, not arrays
                            elif isinstance(node.func, ast.Name) and node.func.id == 'range':
                                return False  # range() arguments are scalars
                            # If passed to other functions, check if those functions use it as array
                            # This handles the case where wrapper functions pass arrays to implementation functions
                            elif isinstance(node.func, ast.Name):
                                # Check if the called function uses the parameter at this position as an array
                                return self._check_function_param_usage(node.func.id, i)
            
            # Check for iteration over parameter (for item in param)
            elif isinstance(node, ast.For):
                if isinstance(node.iter, ast.Name) and node.iter.id == param_name:
                    return True
                    
            # Check for list comprehensions or generator expressions using the parameter
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for generator in node.generators:
                    if isinstance(generator.iter, ast.Name) and generator.iter.id == param_name:
                        return True
        
        return False

    def _check_function_param_usage(self, func_name: str, param_index: int) -> bool:
        """Check if a called function uses the parameter at the given index as an array.
        
        This analyzes the actual function definition to see if the parameter at param_index
        is used as an array.
        """
        # We need to find the function definition in the same AST tree
        # Since we're already parsing the source file, we can look for the function
        if not hasattr(self, '_current_ast_tree'):
            # If we don't have the AST tree cached, fall back to conservative approach
            return True  # Assume it's an array to be safe
        
        # Find the function definition in the AST
        for node in ast.walk(self._current_ast_tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                # Found the function, now check if the parameter at param_index is used as an array
                if param_index < len(node.args.args):
                    param_name = node.args.args[param_index].arg
                    return self._infer_array_usage(node, param_name)
        
        # If we can't find the function definition, assume it uses arrays
        return True

    def _infer_parameter_types_from_usage(self, source_file: str, function_name: str) -> Dict[str, str]:
        """Infer parameter types from their usage patterns in the AST."""
        try:
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            tree = ast.parse(source_code)
            
            # Find the target function
            target_func = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    target_func = node
                    break
            
            if not target_func:
                return {}
            
            # Get parameter names
            param_names = [arg.arg for arg in target_func.args.args]
            param_types = {}
            
            class TypeInferenceVisitor(ast.NodeVisitor):
                def __init__(self, param_names: List[str]):
                    self.param_names = param_names
                    self.param_types = {name: "int" for name in param_names}  # Default to int
                    self.array_sizes = {}  # Track inferred array sizes
                    
                def visit_Call(self, node):
                    # Check for range(param) - indicates param is a size parameter
                    if (isinstance(node.func, ast.Name) and node.func.id == 'range' and 
                        len(node.args) >= 1 and isinstance(node.args[0], ast.Name) and 
                        node.args[0].id in self.param_names):
                        self.param_types[node.args[0].id] = "size"
                    
                    # Check for float operations
                    if isinstance(node.func, ast.Name) and node.func.id in ['float', 'math.sqrt', 'math.sin', 'math.cos']:
                        for arg in node.args:
                            if isinstance(arg, ast.Name) and arg.id in self.param_names:
                                self.param_types[arg.id] = "float"
                    
                    self.generic_visit(node)
                
                def visit_BinOp(self, node):
                    # Check for floating point operations
                    if isinstance(node.op, ast.Div):  # Division often produces floats
                        if isinstance(node.left, ast.Name) and node.left.id in self.param_names:
                            self.param_types[node.left.id] = "float"
                        if isinstance(node.right, ast.Name) and node.right.id in self.param_names:
                            self.param_types[node.right.id] = "float"
                    
                    self.generic_visit(node)
                
                def visit_Compare(self, node):
                    # Check for boolean comparisons
                    if isinstance(node.left, ast.Name) and node.left.id in self.param_names:
                        # If used directly in comparison, might be boolean
                        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot)):
                            if (len(node.comparators) == 1 and 
                                isinstance(node.comparators[0], ast.Constant) and
                                isinstance(node.comparators[0].value, bool)):
                                self.param_types[node.left.id] = "bool"
                    
                    self.generic_visit(node)
                
                def visit_If(self, node):
                    # Check if parameter is used directly as condition
                    if isinstance(node.test, ast.Name) and node.test.id in self.param_names:
                        self.param_types[node.test.id] = "bool"
                    
                    self.generic_visit(node)
                
                def visit_Subscript(self, node):
                    # Look for array access patterns that reveal size requirements
                    if isinstance(node.value, ast.Name) and node.value.id in self.param_names:
                        # Check if accessing with a constant or variable that suggests size
                        if isinstance(node.slice, ast.Constant):
                            # Direct constant access suggests minimum size
                            min_size = node.slice.value + 1
                            param_name = node.value.id
                            if param_name not in self.array_sizes or self.array_sizes[param_name] < min_size:
                                self.array_sizes[param_name] = min_size
                    
                    self.generic_visit(node)
                
                def visit_Assign(self, node):
                    # Look for size constants that might be used for array parameters
                    if isinstance(node.value, ast.Constant):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                # Check if this constant is used to size arrays
                                const_name = target.id
                                const_value = node.value.value
                                if isinstance(const_value, int) and const_value > 1:
                                    # Look for usage patterns that suggest this is an array size
                                    self._check_size_constant_usage(const_name, const_value)
                    
                    self.generic_visit(node)
                
                def _check_size_constant_usage(self, const_name: str, const_value: int):
                    """Check if a constant is used to indicate array size requirements."""
                    # Look for patterns like:
                    # FFT_SIZE = 256
                    # for i in range(FFT_SIZE):
                    #     ... input_data[i] ...
                    
                    # Common size constant names
                    size_indicators = ['SIZE', 'LENGTH', 'COUNT', 'NUM', 'MAX']
                    if any(indicator in const_name.upper() for indicator in size_indicators):
                        # This looks like a size constant - assume it applies to array parameters
                        for param_name in self.param_names:
                            # Record the size requirement for all array parameters
                            self.array_sizes[param_name] = const_value
            
            visitor = TypeInferenceVisitor(param_names)
            visitor.visit(target_func)
            param_types = visitor.param_types
            
            # Add array size information to the types
            for param_name, size in visitor.array_sizes.items():
                if param_name in param_types:
                    param_types[param_name] = f"{param_types[param_name]}:{size}"
            
            logger.debug(f"Inferred parameter types for {function_name}: {param_types}")
            return param_types
            
        except Exception as e:
            logger.error(f"Error inferring parameter types: {e}")
            return {}

    def _generate_test_vectors_for_python_function(self, source_file: str, function_name: str, num_tests: int, seed: Optional[int] = 42) -> List[Dict[str, Any]]:
        """Generate test vectors for Python function using only AST analysis, no naming patterns."""
        # Extract function information from source
        func_info = self._extract_function_info_from_source(source_file, function_name)
        if not func_info:
            logger.error(f"Could not extract function info for {function_name}")
            return []
        
        logger.debug(f"Function info for {function_name}: {func_info}")
        
        import random
        rng = random.Random(seed) if seed is not None else random.Random()
        test_vectors = []
        
        # Analyze the function to determine data types from usage patterns
        param_types = self._infer_parameter_types_from_usage(source_file, function_name)
        
        for _ in range(num_tests):
            test_vector = {}
            
            # First pass: determine array sizes from inferred types
            array_size = rng.randint(5, 20)  # Default size
            
            # Check if any parameter has a specific size requirement
            for param in func_info["parameters"]:
                param_name = param["name"]
                is_array = param["is_array"]
                inferred_type = param_types.get(param_name, "int")
                
                if is_array and ":" in inferred_type:
                    # Extract size from type annotation (e.g., "int:256")
                    _, size_str = inferred_type.split(":", 1)
                    try:
                        specific_size = int(size_str)
                        array_size = specific_size
                        break
                    except ValueError:
                        pass
            
            for param in func_info["parameters"]:
                param_name = param["name"]
                is_array = param["is_array"]
                inferred_type = param_types.get(param_name, "int")
                
                # Clean type (remove size annotation if present)
                base_type = inferred_type.split(":")[0] if ":" in inferred_type else inferred_type
                
                if is_array:
                    # Generate array based on inferred type only
                    if base_type == "bool":
                        test_vector[param_name] = [rng.choice([True, False]) for _ in range(array_size)]
                    elif base_type == "float":
                        test_vector[param_name] = [rng.uniform(-100.0, 100.0) for _ in range(array_size)]
                    else:  # int or unknown
                        test_vector[param_name] = [rng.randint(0, 1000) for _ in range(array_size)]
                else:
                    # Generate scalar based on inferred type
                    if base_type == "bool":
                        test_vector[param_name] = rng.choice([True, False])
                    elif base_type == "float":
                        test_vector[param_name] = rng.uniform(-100.0, 100.0)
                    elif base_type == "size":  # Special case: size parameters match array length
                        test_vector[param_name] = array_size
                    else:  # int or unknown
                        test_vector[param_name] = rng.randint(0, 1000)
            
            test_vectors.append(test_vector)
        
        logger.debug(f"Generated {len(test_vectors)} test vectors for Python function")
        if test_vectors:
            logger.debug(f"Sample test vector: {test_vectors[0]}")
        
        return test_vectors
    
    def _generate_test_vectors(self, func_info: Dict[str, Any], num_tests: int) -> List[Dict[str, Any]]:
        """Generate test vectors for a function."""
        import random
        
        test_vectors = []
        
        for _ in range(num_tests):
            test_vector = {}
            
            for param in func_info["parameters"]:
                param_name = param["name"]
                bit_width = param["bit_width"]
                param_type = param["type"]
                
                # Generate random values based on type and bit width
                if param_type.lower() in ["int", "integer"]:
                    if bit_width <= 32:
                        # Signed integer
                        max_val = (1 << (bit_width - 1)) - 1
                        min_val = -(1 << (bit_width - 1))
                        test_vector[param_name] = random.randint(min_val, max_val)
                    else:
                        # Large integer
                        test_vector[param_name] = random.randint(-1000000, 1000000)
                else:
                    # Default to unsigned integer
                    if bit_width <= 32:
                        max_val = (1 << bit_width) - 1
                        test_vector[param_name] = random.randint(0, max_val)
                    else:
                        test_vector[param_name] = random.randint(0, 1000000)
            
            test_vectors.append(test_vector)
        
        # Add some edge cases
        edge_cases = self._generate_edge_cases(func_info)
        test_vectors.extend(edge_cases)
        
        return test_vectors
    
    def _generate_edge_cases(self, func_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate edge case test vectors."""
        edge_cases = []
        
        # Zero case
        zero_case = {}
        for param in func_info["parameters"]:
            zero_case[param["name"]] = 0
        edge_cases.append(zero_case)
        
        # Max values case
        max_case = {}
        for param in func_info["parameters"]:
            bit_width = param["bit_width"]
            param_type = param["type"]
            
            if param_type.lower() in ["int", "integer"]:
                max_case[param["name"]] = (1 << (bit_width - 1)) - 1
            else:
                max_case[param["name"]] = (1 << bit_width) - 1
        edge_cases.append(max_case)
        
        # Min values case (for signed types)
        min_case = {}
        for param in func_info["parameters"]:
            bit_width = param["bit_width"]
            param_type = param["type"]
            
            if param_type.lower() in ["int", "integer"]:
                min_case[param["name"]] = -(1 << (bit_width - 1))
            else:
                min_case[param["name"]] = 0
        edge_cases.append(min_case)
        
        return edge_cases
    
    def _save_module_verilog(self, module: Any, module_name: str) -> str:
        """Save module Verilog to a temporary file."""
        # Use module name for the filename to ensure header name matches
        verilog_filename = f"{module_name}.v"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.v', delete=False, prefix=f"{module_name}_") as f:
            # Generate Verilog code for the module
            verilog_code = self._generate_module_verilog(module)
            f.write(verilog_code)
            temp_path = f.name
        
        # Rename to have the correct module name
        import shutil
        final_path = os.path.join(os.path.dirname(temp_path), verilog_filename)
        shutil.move(temp_path, final_path)
        return final_path
    
    def _generate_module_verilog(self, module: Any) -> str:
        """Generate Verilog code for a module."""
        # Use the existing Verilog from the netlist - should now be complete
        if hasattr(module, 'verilog_blocks') and module.verilog_blocks:
            # Extract the first Verilog block which should contain the complete module
            verilog_code = module.verilog_blocks[0]
            
            # Ensure it ends with a newline
            if not verilog_code.endswith('\n'):
                verilog_code += '\n'
            return verilog_code
        
        # This should not happen with the new Verilog generator, but keep as fallback
        raise RuntimeError(f"No Verilog code generated for module {module.name}. This indicates a problem with the Verilog generator.")
    
    def _extract_module_port_info(self, module: Any) -> Dict[str, Any]:
        """Extract actual port information from generated Verilog module."""
        try:
            if not hasattr(module, 'verilog_blocks') or not module.verilog_blocks:
                logger.warning(f"No Verilog blocks found in module {module.name}")
                return None
            
            verilog_code = module.verilog_blocks[0]
            
            # Parse the module declaration to extract port names
            # Find module declaration
            module_match = re.search(r'module\s+\w+\s*\((.*?)\);', verilog_code, re.DOTALL)
            if not module_match:
                logger.warning(f"Could not find module declaration in {module.name}")
                return None
            
            port_declarations = module_match.group(1)
            
            # Parse individual port declarations
            input_ports = []
            output_ports = []
            array_interfaces = {}  # Track array interface signals
            
            # Split by commas and parse each port
            for port_line in port_declarations.split(','):
                port_line = port_line.strip()
                if not port_line:
                    continue
                
                # Parse port declaration: input/output [wire/reg] [signed] [width] name
                port_match = re.search(r'(input|output)\s+(wire|reg)?\s*(signed)?\s*(\[[^\]]+\])?\s*(\w+)', port_line)
                if port_match:
                    direction = port_match.group(1)
                    is_signed = port_match.group(3) is not None
                    width_spec = port_match.group(4)
                    port_name = port_match.group(5)
                    
                    # Calculate bit width
                    if width_spec:
                        # Extract width from [MSB:LSB] format
                        width_match = re.search(r'\[(\d+):(\d+)\]', width_spec)
                        if width_match:
                            msb = int(width_match.group(1))
                            lsb = int(width_match.group(2))
                            bit_width = msb - lsb + 1
                        else:
                            bit_width = 32  # Default
                    else:
                        bit_width = 1
                    
                    port_info = {
                        "name": port_name,
                        "direction": direction,
                        "bit_width": bit_width,
                        "is_signed": is_signed
                    }
                    
                    # Check if this is an array interface signal
                    if self._is_array_interface_signal(port_name):
                        array_name = self._extract_array_name_from_port(port_name)
                        if array_name not in array_interfaces:
                            array_interfaces[array_name] = {
                                "type": "input" if direction == "input" else "output",
                                "signals": []
                            }
                        array_interfaces[array_name]["signals"].append(port_info)
                    
                    if direction == "input":
                        input_ports.append(port_info)
                    else:
                        output_ports.append(port_info)
            
            # Filter out control signals to get actual function parameters
            function_inputs = []
            for port in input_ports:
                if port["name"] not in ["clk", "rst_n"]:
                    function_inputs.append(port)
            
            function_outputs = []
            for port in output_ports:
                if port["name"] not in ["valid", "done"] and not self._is_array_interface_signal(port["name"]):
                    function_outputs.append(port)
            
            return {
                "name": module.name,
                "input_ports": function_inputs,
                "output_ports": function_outputs,
                "all_input_ports": input_ports,
                "all_output_ports": output_ports,
                "array_interfaces": array_interfaces
            }
            
        except Exception as e:
            logger.error(f"Error extracting port info from module {module.name}: {str(e)}")
            return None
    
    def _is_array_interface_signal(self, signal_name: str) -> bool:
        """Check if a signal is part of an array interface."""
        # Order suffixes from longest to shortest to ensure proper matching
        array_suffixes = ['_write_enable', '_read_enable', '_data_in', '_data_out', 
                         '_addr', '_enable', '_ready', '_valid', '_size']
        return any(signal_name.endswith(suffix) for suffix in array_suffixes)
    
    def _extract_array_name_from_port(self, signal_name: str) -> str:
        """Extract the array name from an array interface signal."""
        # Order suffixes from longest to shortest to ensure proper matching
        array_suffixes = ['_write_enable', '_read_enable', '_data_in', '_data_out', 
                         '_addr', '_enable', '_ready', '_valid', '_size']
        for suffix in array_suffixes:
            if signal_name.endswith(suffix):
                return signal_name[:-len(suffix)]
        return signal_name
    
    def _run_rtl_simulation(self, 
                           verilog_file: str, 
                           testbench_file: str, 
                           module_name: str,
                           max_cycles: int = 1000,
                           vcd: bool = False,
                           timeout: int = 60,
                           artifact_dir: Optional[str] = None,
                           test_vectors: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Run RTL simulation using Verilator with artifact preservation and timeout handling."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                sim_dir = temp_dir
                verilog_basename = os.path.basename(verilog_file)
                testbench_basename = os.path.basename(testbench_file)
                
                sim_verilog = os.path.join(sim_dir, verilog_basename)
                sim_testbench = os.path.join(sim_dir, testbench_basename)
                
                import shutil
                shutil.copy2(verilog_file, sim_verilog)
                shutil.copy2(testbench_file, sim_testbench)
                
                exe_name = f"V{module_name}"
                
                # Compile with Verilator
                compile_cmd = [
                    self.verilator_path,
                    "-Wall",
                    "--cc",
                    "--exe",
                    "--build",
                    "--no-timing",
                ] + self._get_warning_flags() + [
                    "-CFLAGS", "-std=c++14",
                    "-o", exe_name,
                    sim_verilog,
                    sim_testbench
                ]
                if vcd:
                    compile_cmd.insert(4, "--trace")
                
                logger.debug(f"Running Verilator compile: {' '.join(compile_cmd)}")
                
                compile_result = subprocess.run(
                    compile_cmd,
                    cwd=sim_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if artifact_dir:
                    os.makedirs(artifact_dir, exist_ok=True)
                    try:
                        shutil.copy2(sim_verilog, os.path.join(artifact_dir, verilog_basename))
                        shutil.copy2(sim_testbench, os.path.join(artifact_dir, testbench_basename))
                        with open(os.path.join(artifact_dir, f"{module_name}_compile.log"), 'w') as f:
                            f.write(f"STDOUT:\n{compile_result.stdout}\n\nSTDERR:\n{compile_result.stderr}\n")
                        if test_vectors is not None:
                            with open(os.path.join(artifact_dir, "test_vectors.json"), 'w') as f:
                                json.dump(test_vectors, f, indent=2)
                    except Exception as e:
                        logger.warning(f"Failed preserving compile artifacts: {e}")
                
                if compile_result.returncode != 0:
                    logger.error(f"Verilator compilation failed: {compile_result.stderr}")
                    return {"error": f"Compilation failed: {compile_result.stderr}"}
                
                # Run simulation
                exe_path = os.path.join(sim_dir, "obj_dir", exe_name)
                if not os.path.exists(exe_path):
                    logger.error(f"Simulation executable not found: {exe_path}")
                    return {"error": "Simulation executable not found"}
                
                logger.debug(f"Running simulation: {exe_path}")
                
                sim_result = subprocess.run(
                    [exe_path],
                    cwd=sim_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if artifact_dir:
                    try:
                        if os.path.exists(exe_path):
                            shutil.copy2(exe_path, os.path.join(artifact_dir, exe_name))
                        with open(os.path.join(artifact_dir, f"{module_name}_simulation.log"), 'w') as f:
                            f.write(f"STDOUT:\n{sim_result.stdout}\n\nSTDERR:\n{sim_result.stderr}\n")
                        vcd_cand = os.path.join(sim_dir, f"{module_name}_tb.vcd")
                        if os.path.exists(vcd_cand):
                            shutil.copy2(vcd_cand, os.path.join(artifact_dir, f"{module_name}_tb.vcd"))
                    except Exception as e:
                        logger.warning(f"Failed preserving simulation artifacts: {e}")
                
                if sim_result.returncode != 0:
                    logger.error(f"Simulation failed: {sim_result.stderr}")
                    return {"error": f"Simulation failed: {sim_result.stderr}"}
                
                # Parse simulation output
                return self._parse_simulation_output(sim_result.stdout)
                
        except subprocess.TimeoutExpired:
            logger.error(f"Simulation execution timed out after {timeout} seconds")
            return {"error": f"Simulation timed out after {timeout} seconds"}
        except Exception as e:
            logger.error(f"Simulation error: {str(e)}")
            return {"error": str(e)}
    
    def _parse_simulation_output(self, output: str) -> Dict[str, Any]:
        """Parse simulation output to extract results, array outputs, dict outputs, and cycle counts."""
        results = []
        
        # Look for result lines in the output
        # Format: RESULT: inputs={a=1,b=2},output=3,cycles=8
        # Format: RESULT: inputs={a=1},output=[1,2,3],cycles=12
        # Format: RESULT: inputs={a=1},output={"out1": 2, "out2": 3},cycles=15
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith("RESULT:"):
                try:
                    result_part = line[7:].strip()  # Remove "RESULT:" prefix
                    
                    # Extract cycles if present
                    cycles_to_done = None
                    if ',cycles=' in result_part:
                        result_part, cycles_str = result_part.rsplit(',cycles=', 1)
                        try:
                            cycles_to_done = int(cycles_str.strip())
                        except ValueError:
                            pass
                    
                    # Extract inputs and output
                    if ',output=' in result_part:
                        inputs_part, output_part = result_part.split(',output=', 1)
                        output_part = output_part.strip()
                        
                        # Parse inputs: inputs={a=1,b=2}
                        test_inputs = {}
                        if inputs_part.startswith('inputs={') and inputs_part.endswith('}'):
                            inputs_str = inputs_part[8:-1]  # Remove 'inputs={' and '}'
                            for pair in inputs_str.split(','):
                                if '=' in pair:
                                    key, value = pair.split('=', 1)
                                    try:
                                        test_inputs[key] = int(value)
                                    except ValueError:
                                        try:
                                            test_inputs[key] = float(value)
                                        except ValueError:
                                            test_inputs[key] = value
                        
                        # Parse output: scalar, array [...], or dict {...}
                        if output_part.startswith('[') and output_part.endswith(']'):
                            inner = output_part[1:-1].strip()
                            if not inner:
                                output_value = []
                            else:
                                output_value = []
                                for item in inner.split(','):
                                    item = item.strip()
                                    try:
                                        output_value.append(int(item))
                                    except ValueError:
                                        try:
                                            output_value.append(float(item))
                                        except ValueError:
                                            output_value.append(item)
                        elif output_part.startswith('{') and output_part.endswith('}'):
                            try:
                                output_value = json.loads(output_part)
                            except Exception:
                                try:
                                    output_value = ast.literal_eval(output_part)
                                except Exception:
                                    output_value = output_part
                        else:
                            try:
                                output_value = int(output_part)
                            except ValueError:
                                try:
                                    output_value = float(output_part)
                                except ValueError:
                                    output_value = output_part
                        
                        result = {
                            "test_inputs": test_inputs,
                            "outputs": {"return_val": output_value} if not isinstance(output_value, dict) else output_value,
                        }
                        if cycles_to_done is not None:
                            result["cycles_to_done"] = cycles_to_done
                            result["timed_out"] = (cycles_to_done == -1)
                        results.append(result)
                        
                except Exception as e:
                    logger.warning(f"Could not parse result line: {line} - {str(e)}")
        
        return {"results": results, "raw_output": output}
    
    def _compare_results(self, python_results: Dict[str, Any], 
                        rtl_results: Dict[str, Any], 
                        test_vectors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare Python and RTL simulation results with structured diffs."""
        comparison = {
            "total_tests": len(test_vectors),
            "passed": 0,
            "failed": 0,
            "errors": [],
            "mismatches": [],
            "timeouts": 0
        }
        
        if "error" in python_results:
            comparison["errors"].append(f"Python execution error: {python_results['error']}")
        
        if "error" in rtl_results:
            comparison["errors"].append(f"RTL simulation error: {rtl_results['error']}")
        
        if comparison["errors"]:
            return comparison
        
        py_results = python_results.get("results", [])
        rtl_result_list = rtl_results.get("results", [])
        
        # Compare each test case
        for i, test_vector in enumerate(test_vectors):
            if i >= len(py_results) or i >= len(rtl_result_list):
                comparison["errors"].append(f"Mismatch in number of results for test {i}")
                continue
            
            py_result = py_results[i]
            rtl_result = rtl_result_list[i]
            
            # Check timeout
            if isinstance(rtl_result, dict) and (rtl_result.get("timed_out") or rtl_result.get("cycles_to_done") == -1):
                comparison["failed"] += 1
                comparison["timeouts"] += 1
                comparison["mismatches"].append({
                    "test_index": i,
                    "test_vector": test_vector,
                    "python_result": py_result,
                    "rtl_result": "TIMEOUT",
                    "error": "DUT did not assert done within max_cycles limit"
                })
                continue
            
            # Extract output value from RTL result
            if isinstance(rtl_result, dict) and "outputs" in rtl_result:
                outputs_dict = rtl_result["outputs"]
                if "return_val" in outputs_dict and len(outputs_dict) == 1:
                    rtl_output = outputs_dict["return_val"]
                else:
                    rtl_output = outputs_dict
            else:
                rtl_output = rtl_result
            
            if self._results_match(py_result, rtl_output):
                comparison["passed"] += 1
            else:
                comparison["failed"] += 1
                comparison["mismatches"].append({
                    "test_index": i,
                    "test_vector": test_vector,
                    "python_result": py_result,
                    "rtl_result": rtl_output
                })
        
        return comparison
    
    def _results_match(self, py_result: Any, rtl_result: Any, tolerance: float = 1e-5) -> bool:
        """Check if Python and RTL results match across scalars, arrays, and dictionaries."""
        if isinstance(py_result, (int, float)) and isinstance(rtl_result, (int, float)):
            if isinstance(py_result, float) or isinstance(rtl_result, float):
                return abs(py_result - rtl_result) <= tolerance
            else:
                return py_result == rtl_result
        if isinstance(py_result, (list, tuple)) and isinstance(rtl_result, (list, tuple)):
            if len(py_result) != len(rtl_result):
                return False
            return all(self._results_match(p, r, tolerance) for p, r in zip(py_result, rtl_result))
        if isinstance(py_result, dict) and isinstance(rtl_result, dict):
            if set(py_result.keys()) != set(rtl_result.keys()):
                return False
            return all(self._results_match(py_result[k], rtl_result[k], tolerance) for k in py_result)
        return py_result == rtl_result
    
    def _generate_verification_report(self, verification_results: Dict[str, Any]) -> str:
        """Generate a structured, actionable verification report."""
        report = []
        report.append("=" * 60)
        report.append("           PYTHON-HLS RTL VERIFICATION REPORT")
        report.append("=" * 60)
        report.append("")
        
        total_modules = len(verification_results)
        successful_modules = 0
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_timeouts = 0
        
        for module_name, result in verification_results.items():
            report.append(f"Module: {module_name}")
            report.append("-" * 40)
            
            if "error" in result:
                report.append(f"  [ERROR] {result['error']}")
            else:
                comparison = result.get("comparison", {})
                tests = comparison.get("total_tests", 0)
                passed = comparison.get("passed", 0)
                failed = comparison.get("failed", 0)
                timeouts = comparison.get("timeouts", 0)
                
                total_tests += tests
                total_passed += passed
                total_failed += failed
                total_timeouts += timeouts
                
                if failed == 0 and not comparison.get("errors"):
                    successful_modules += 1
                    report.append(f"  [PASS] {passed}/{tests} tests passed (100% RTL-Python equivalence)")
                else:
                    report.append(f"  [FAIL] {failed}/{tests} tests failed (Timeouts: {timeouts})")
                    
                    mismatches = comparison.get("mismatches", [])
                    if mismatches:
                        report.append("\n  Mismatches (up to 5 shown):")
                        for idx, mm in enumerate(mismatches[:5]):
                            t_idx = mm.get("test_index", idx)
                            inputs = mm.get("test_vector", {})
                            py_val = mm.get("python_result")
                            rtl_val = mm.get("rtl_result")
                            report.append(f"    - Test #{t_idx}: inputs={inputs}")
                            report.append(f"        Expected (Python): {py_val}")
                            report.append(f"        Received (RTL):    {rtl_val}")
                        if len(mismatches) > 5:
                            report.append(f"    ... and {len(mismatches) - 5} additional mismatches")
                
                if comparison.get("errors"):
                    report.append("  Diagnostics:")
                    for err in comparison["errors"]:
                        report.append(f"    - {err}")
            
            report.append("")
        
        # Overall Summary
        report.append("=" * 60)
        report.append(f"Summary: {successful_modules}/{total_modules} modules qualified")
        report.append(f"Total Test Vectors: {total_tests} | Passed: {total_passed} | Failed: {total_failed} | Timeouts: {total_timeouts}")
        if total_failed == 0 and successful_modules == total_modules and total_modules > 0:
            report.append("Result: ALL RTL VERIFICATION CHECKS PASSED")
        else:
            report.append("Result: VERIFICATION FAILURES DETECTED")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def _generate_test_vectors_from_ports(self, port_info: Dict[str, Any], num_tests: int, seed: Optional[int] = 42) -> List[Dict[str, Any]]:
        """Generate deterministic test vectors based on actual module port information."""
        import random
        rng = random.Random(seed) if seed is not None else random.Random()
        
        test_vectors = []
        
        # Add structured edge cases first
        edge_cases = self._generate_edge_cases_from_ports(port_info)
        test_vectors.extend(edge_cases)
        
        # Calculate remaining random tests
        remaining = max(0, num_tests - len(edge_cases))
        
        # Extract array interfaces
        array_interfaces = port_info.get("array_interfaces", {})
        
        # Generate test vectors for Python function execution
        for _ in range(remaining):
            test_vector = {}
            
            # Generate values for array interfaces using original parameter names
            for array_name, array_info in array_interfaces.items():
                if array_info["type"] == "input":
                    array_size = rng.randint(4, 16)
                    array_data = [rng.randint(0, 500) for _ in range(array_size)]
                    test_vector[array_name] = array_data
            
            # Generate values for scalar input ports (skip array interface signals)
            for port in port_info["input_ports"]:
                port_name = port["name"]
                bit_width = port["bit_width"]
                is_signed = port["is_signed"]
                
                if self._is_array_interface_signal(port_name):
                    continue
                
                # Generate values within safe ranges for test arithmetic
                if is_signed:
                    if bit_width <= 8:
                        max_val = (1 << (bit_width - 1)) - 1
                        min_val = -(1 << (bit_width - 1))
                        test_vector[port_name] = rng.randint(min_val, max_val)
                    elif bit_width <= 32:
                        test_vector[port_name] = rng.randint(1, 1000)
                    else:
                        test_vector[port_name] = rng.randint(1, 100000)
                else:
                    if bit_width <= 8:
                        max_val = (1 << bit_width) - 1
                        test_vector[port_name] = rng.randint(0, max_val)
                    elif bit_width <= 32:
                        test_vector[port_name] = rng.randint(0, 1000)
                    else:
                        test_vector[port_name] = rng.randint(0, 100000)
            
            test_vectors.append(test_vector)
        
        return test_vectors
    
    def _generate_edge_cases_from_ports(self, port_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate edge case test vectors based on port information."""
        edge_cases = []
        
        array_interfaces = port_info.get("array_interfaces", {})
        scalar_ports = [p for p in port_info.get("input_ports", []) if not self._is_array_interface_signal(p["name"])]
        
        # 1. Zero case
        zero_case = {}
        for array_name, array_info in array_interfaces.items():
            if array_info["type"] == "input":
                zero_case[array_name] = [0, 0, 0, 0]
        for port in scalar_ports:
            zero_case[port["name"]] = 0
        edge_cases.append(zero_case)
        
        # 2. One case
        one_case = {}
        for array_name, array_info in array_interfaces.items():
            if array_info["type"] == "input":
                one_case[array_name] = [1, 1, 1, 1]
        for port in scalar_ports:
            one_case[port["name"]] = 1
        edge_cases.append(one_case)
        
        # 3. Small positive case (useful for loops like GCD)
        small_case = {}
        for array_name, array_info in array_interfaces.items():
            if array_info["type"] == "input":
                small_case[array_name] = [2, 4, 6, 8]
        for idx, port in enumerate(scalar_ports):
            small_case[port["name"]] = 2 + idx * 2
        edge_cases.append(small_case)
        
        # 4. Max boundary case
        max_case = {}
        for array_name, array_info in array_interfaces.items():
            if array_info["type"] == "input":
                max_case[array_name] = [255, 255]
        for port in scalar_ports:
            bit_width = port["bit_width"]
            if port["is_signed"]:
                max_case[port["name"]] = min(1000, (1 << (bit_width - 1)) - 1)
            else:
                max_case[port["name"]] = min(1000, (1 << bit_width) - 1)
        edge_cases.append(max_case)
        
        return edge_cases