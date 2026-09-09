"""
Python executor for running original Python code to get reference results.
"""

import os
import sys
import ast
import importlib.util
import tempfile
import traceback
from typing import Dict, List, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class PythonExecutor:
    """
    Executes Python functions to get reference results for verification.
    """
    
    def __init__(self):
        """Initialize the Python executor."""
        pass
    
    def execute_function(self, 
                        source_file: str, 
                        function_name: str, 
                        test_vectors: List[Dict[str, Any]],
                        simulate_rtl_bitwidth: bool = True,
                        output_bitwidth: int = 32) -> Dict[str, Any]:
        """
        Execute a Python function with test vectors.
        
        Args:
            source_file: Path to Python source file
            function_name: Name of function to execute
            test_vectors: List of test vectors (input parameter dictionaries)
            simulate_rtl_bitwidth: Whether to simulate RTL bit-width behavior
            output_bitwidth: Bit width for output simulation (default 32)
            
        Returns:
            Dictionary containing execution results
        """
        logger.info(f"Executing Python function {function_name} from {source_file}")
        
        try:
            # Load the Python module
            func = self._load_function(source_file, function_name)
            if not func:
                return {"error": f"Could not load function {function_name} from {source_file}"}
            
            # Execute function with each test vector
            results = []
            for i, test_vector in enumerate(test_vectors):
                try:
                    # Call the function with the test vector parameters
                    result = func(**test_vector)
                    
                    # Simulate RTL bit-width behavior if requested
                    if simulate_rtl_bitwidth:
                        result = self._simulate_rtl_bitwidth(result, output_bitwidth)
                    
                    results.append(result)
                    logger.debug(f"Test {i+1}: {test_vector} -> {result}")
                except Exception as e:
                    logger.error(f"Error executing test {i+1}: {str(e)}")
                    results.append({"error": str(e)})
            
            return {"results": results}
            
        except Exception as e:
            logger.error(f"Error executing Python function: {str(e)}")
            return {"error": str(e)}
    
    def _load_function(self, source_file: str, function_name: str) -> Optional[Callable]:
        """Load a specific function from a Python source file."""
        try:
            # Create a module spec from the source file
            spec = importlib.util.spec_from_file_location("test_module", source_file)
            if not spec or not spec.loader:
                logger.error(f"Could not create module spec for {source_file}")
                return None
            
            # Load the module
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the function
            if hasattr(module, function_name):
                return getattr(module, function_name)
            else:
                logger.error(f"Function {function_name} not found in {source_file}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading function {function_name}: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def extract_functions(self, source_file: str) -> List[str]:
        """
        Extract all function names from a Python source file.
        
        Args:
            source_file: Path to Python source file
            
        Returns:
            List of function names
        """
        try:
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            # Parse the AST
            tree = ast.parse(source_code)
            
            # Extract function names
            functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
            
            return functions
            
        except Exception as e:
            logger.error(f"Error extracting functions from {source_file}: {str(e)}")
            return []
    
    def get_function_signature(self, source_file: str, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the signature of a function from a Python source file.
        
        Args:
            source_file: Path to Python source file
            function_name: Name of the function
            
        Returns:
            Dictionary containing function signature information
        """
        try:
            with open(source_file, 'r') as f:
                source_code = f.read()
            
            # Parse the AST
            tree = ast.parse(source_code)
            
            # Find the function
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    # Extract parameter information
                    params = []
                    for arg in node.args.args:
                        param_info = {
                            "name": arg.arg,
                            "annotation": None
                        }
                        
                        # Get type annotation if available
                        if arg.annotation:
                            param_info["annotation"] = ast.unparse(arg.annotation)
                        
                        params.append(param_info)
                    
                    # Extract return type annotation
                    return_annotation = None
                    if node.returns:
                        return_annotation = ast.unparse(node.returns)
                    
                    return {
                        "name": function_name,
                        "parameters": params,
                        "return_annotation": return_annotation,
                        "docstring": ast.get_docstring(node)
                    }
            
            logger.error(f"Function {function_name} not found in {source_file}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting function signature: {str(e)}")
            return None
    
    def validate_test_vectors(self, 
                            source_file: str, 
                            function_name: str, 
                            test_vectors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate that test vectors are compatible with the function signature.
        
        Args:
            source_file: Path to Python source file
            function_name: Name of the function
            test_vectors: List of test vectors to validate
            
        Returns:
            Validation results
        """
        signature = self.get_function_signature(source_file, function_name)
        if not signature:
            return {"valid": False, "error": "Could not get function signature"}
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        expected_params = set(param["name"] for param in signature["parameters"])
        
        for i, test_vector in enumerate(test_vectors):
            test_params = set(test_vector.keys())
            
            # Check for missing parameters
            missing_params = expected_params - test_params
            if missing_params:
                validation_results["valid"] = False
                validation_results["errors"].append(
                    f"Test vector {i+1} missing parameters: {missing_params}"
                )
            
            # Check for extra parameters
            extra_params = test_params - expected_params
            if extra_params:
                validation_results["warnings"].append(
                    f"Test vector {i+1} has extra parameters: {extra_params}"
                )
        
        return validation_results
    
    def create_test_file(self, 
                        original_file: str, 
                        function_name: str, 
                        test_vectors: List[Dict[str, Any]]) -> str:
        """
        Create a standalone test file for a specific function.
        
        Args:
            original_file: Path to original Python source file
            function_name: Name of function to test
            test_vectors: Test vectors to include
            
        Returns:
            Path to created test file
        """
        try:
            # Read the original file
            with open(original_file, 'r') as f:
                original_code = f.read()
            
            # Create test code
            test_code = []
            test_code.append("#!/usr/bin/env python3")
            test_code.append('"""')
            test_code.append(f"Test file for function {function_name}")
            test_code.append("Generated automatically for RTL verification")
            test_code.append('"""')
            test_code.append("")
            test_code.append("import json")
            test_code.append("")
            
            # Include the original code
            test_code.append("# Original function code")
            test_code.append(original_code)
            test_code.append("")
            
            # Add test execution code
            test_code.append("# Test execution")
            test_code.append("def run_tests():")
            test_code.append("    test_vectors = [")
            for test_vector in test_vectors:
                test_code.append(f"        {test_vector},")
            test_code.append("    ]")
            test_code.append("")
            test_code.append("    results = []")
            test_code.append("    for i, test_vector in enumerate(test_vectors):")
            test_code.append("        try:")
            test_code.append(f"            result = {function_name}(**test_vector)")
            test_code.append("            results.append(result)")
            test_code.append(f'            print(f"Test {{i+1}}: {{test_vector}} -> {{result}}")')
            test_code.append("        except Exception as e:")
            test_code.append(f'            print(f"Error in test {{i+1}}: {{e}}")')
            test_code.append("            results.append({'error': str(e)})")
            test_code.append("")
            test_code.append("    return results")
            test_code.append("")
            test_code.append('if __name__ == "__main__":')
            test_code.append("    results = run_tests()")
            test_code.append("    print(f'Results: {results}')")
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write("\n".join(test_code))
                return f.name
                
        except Exception as e:
            logger.error(f"Error creating test file: {str(e)}")
            raise 

    def _simulate_rtl_bitwidth(self, value: Any, bitwidth: int) -> Any:
        """
        Simulate RTL bit-width behavior for integer values.
        
        Args:
            value: The value to simulate
            bitwidth: Target bit width (e.g., 32 for 32-bit signed)
            
        Returns:
            Value with simulated RTL bit-width behavior (unsigned representation)
        """
        if not isinstance(value, int):
            return value  # Only simulate for integers
        
        # Simulate overflow/underflow by masking to bit width
        # Return unsigned representation to match Verilator C++ interface
        mask = (1 << bitwidth) - 1  # e.g., 0xFFFFFFFF for 32-bit
        return value & mask 