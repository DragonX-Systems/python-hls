"""
Parser for converting Python source code to AST.
"""

import ast
import inspect
from typing import Any, Dict, List, Optional, Union, Callable, Set


class PythonParser:
    """Parser for converting Python source code to AST."""
    
    def __init__(self):
        """Initialize the Python parser."""
        self.supported_constructs = {
            ast.FunctionDef, ast.AsyncFunctionDef, ast.If, ast.For, ast.While,
            ast.Assign, ast.AugAssign, ast.BinOp, ast.UnaryOp, ast.Compare,
            ast.Call, ast.Return, ast.Expr, ast.Constant, ast.Name, ast.Tuple,
            ast.List, ast.Dict, ast.Subscript, ast.Attribute, ast.BoolOp,
            ast.IfExp
        }
        
        # Note: using strings for ast nodes that are keywords in Python
        self.unsupported_constructs = {
            ast.ClassDef, ast.Import, ast.ImportFrom, ast.Try, ast.With,
            ast.AsyncFor, ast.AsyncWith, ast.Raise, ast.Lambda, ast.GeneratorExp
        }
        
        # Store source code for pragma extraction
        self.source_lines = []
        # Store all functions found during parsing
        self.discovered_functions = {}
        # Store function dependencies
        self.function_dependencies = {}
    
    def parse_file(self, filename: str, entry_function: Optional[str] = None) -> ast.Module:
        """
        Parse a Python file into an AST, focusing on the entry function and its dependencies.
        
        Args:
            filename: Path to the Python file
            entry_function: Name of the function to use as entry point.
                           If None, will try to auto-detect from __main__ or look for 'main'
            
        Returns:
            AST of the Python file, filtered to include only relevant functions
        """
        with open(filename, 'r') as f:
            source = f.read()
        
        return self.parse_source(source, entry_function)
    
    def parse_source(self, source: str, entry_function: Optional[str] = None) -> ast.Module:
        """
        Parse Python source code into an AST, focusing on the entry function and its dependencies.
        
        Args:
            source: Python source code
            entry_function: Name of the function to use as entry point.
                           If None, will try to auto-detect from __main__ or look for 'main'
            
        Returns:
            AST of the Python source, filtered to include only relevant functions
        """
        # Check if source contains NumPy constructs; if so, lower them first
        from .numpy import NumPyFrontend
        if NumPyFrontend.is_numpy_source(source):
            frontend = NumPyFrontend()
            source = frontend.parse_and_lower_source(source, entry_function=entry_function)

        # Store source lines for pragma extraction
        self.source_lines = source.splitlines()
        
        # Parse the full AST first
        full_tree = ast.parse(source)
        self._validate_ast(full_tree)
        
        # Discover all functions and their dependencies
        self._discover_functions(full_tree)
        self._analyze_dependencies(full_tree)
        
        # Determine the entry function
        if entry_function is None:
            entry_function = self._detect_entry_function(full_tree)
        
        if entry_function is None:
            # If no entry function specified or detected, return the full tree
            print("Warning: No entry function specified or detected. Parsing all functions.")
            return full_tree
        
        # Create a filtered AST with only the entry function and its dependencies
        filtered_tree = self._create_filtered_ast(full_tree, entry_function)
        
        print(f"Entry function: {entry_function}")
        if entry_function in self.function_dependencies:
            deps = self.function_dependencies[entry_function]
            if deps:
                print(f"Dependencies: {', '.join(deps)}")
            else:
                print("No dependencies detected")
        
        return filtered_tree
    
    def parse_function(self, func: Callable) -> ast.FunctionDef:
        """
        Parse a Python function into an AST.
        
        Args:
            func: Python function object
            
        Returns:
            Function definition AST node
        """
        from .numpy import NumPyFrontend
        if NumPyFrontend.is_numpy_function(func):
            frontend = NumPyFrontend()
            function_def = frontend.lower_callable(func)
            self._validate_ast(function_def)
            return function_def

        source = inspect.getsource(func)
        module = ast.parse(source)
        
        # Expect a single function definition
        if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
            raise ValueError("Expected a single function definition")
        
        function_def = module.body[0]
        self._validate_ast(function_def)
        return function_def
    
    def _discover_functions(self, tree: ast.Module) -> None:
        """Discover all function definitions in the AST."""
        self.discovered_functions = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.discovered_functions[node.name] = node
    
    def _analyze_dependencies(self, tree: ast.Module) -> None:
        """Analyze function call dependencies."""
        self.function_dependencies = {}
        
        for func_name, func_node in self.discovered_functions.items():
            dependencies = set()
            
            # Look for function calls within this function
            for node in ast.walk(func_node):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        called_func = node.func.id
                        if called_func in self.discovered_functions and called_func != func_name:
                            dependencies.add(called_func)
            
            self.function_dependencies[func_name] = dependencies
    
    def _detect_entry_function(self, tree: ast.Module) -> Optional[str]:
        """Detect the entry function from the AST."""
        # Strategy 1: Look for functions called in __main__ block
        main_calls = self._find_main_block_calls(tree)
        if main_calls:
            # Return the first function call found in __main__
            return main_calls[0]
        
        # Strategy 2: Look for a function named 'main'
        if 'main' in self.discovered_functions:
            return 'main'
        
        # Strategy 3: Look for common entry point names
        common_names = ['run', 'execute', 'start', 'algorithm']
        for name in common_names:
            if name in self.discovered_functions:
                return name
        
        # Strategy 4: If only one function, use it
        if len(self.discovered_functions) == 1:
            return list(self.discovered_functions.keys())[0]
        
        return None
    
    def _find_main_block_calls(self, tree: ast.Module) -> List[str]:
        """Find function calls in the __main__ block."""
        main_calls = []
        
        for node in tree.body:
            if isinstance(node, ast.If):
                # Check if this is a "if __name__ == '__main__':" block
                if (isinstance(node.test, ast.Compare) and
                    isinstance(node.test.left, ast.Name) and
                    node.test.left.id == '__name__' and
                    len(node.test.comparators) == 1 and
                    isinstance(node.test.comparators[0], ast.Constant) and
                    node.test.comparators[0].value == '__main__'):
                    
                    # Extract function calls from the main block
                    for stmt in node.body:
                        main_calls.extend(self._extract_function_calls(stmt))
        
        return main_calls
    
    def _extract_function_calls(self, node: ast.AST) -> List[str]:
        """Extract function calls from an AST node."""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                func_name = child.func.id
                if func_name in self.discovered_functions:
                    calls.append(func_name)
        return calls
    
    def _create_filtered_ast(self, tree: ast.Module, entry_function: str) -> ast.Module:
        """Create a filtered AST containing only the entry function and its dependencies."""
        if entry_function not in self.discovered_functions:
            raise ValueError(f"Entry function '{entry_function}' not found")
        
        # Get all functions we need (entry + dependencies)
        needed_functions = self._get_all_dependencies(entry_function)
        needed_functions.add(entry_function)
        
        # Create new module with only needed functions
        new_body = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in needed_functions:
                    new_body.append(node)
            else:
                # Keep non-function nodes (imports, constants, etc.)
                new_body.append(node)
        
        # Create new module
        filtered_tree = ast.Module(body=new_body, type_ignores=[])
        return filtered_tree
    
    def _get_all_dependencies(self, func_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """Recursively get all dependencies of a function."""
        if visited is None:
            visited = set()
        
        if func_name in visited:
            return set()  # Avoid cycles
        
        visited.add(func_name)
        all_deps = set()
        
        if func_name in self.function_dependencies:
            direct_deps = self.function_dependencies[func_name]
            all_deps.update(direct_deps)
            
            # Recursively get dependencies of dependencies
            for dep in direct_deps:
                all_deps.update(self._get_all_dependencies(dep, visited.copy()))
        
        return all_deps

    def _validate_ast(self, node: ast.AST) -> None:
        """
        Validate that the AST only contains supported constructs.
        
        Args:
            node: AST node to validate
            
        Raises:
            ValueError: If the AST contains unsupported constructs
        """
        for child_node in ast.walk(node):
            node_type = type(child_node)
            
            if node_type in self.unsupported_constructs:
                raise ValueError(f"Unsupported Python construct: {node_type.__name__}")
                
        # Perform additional validation for specific node types
        visitor = _ValidationVisitor()
        visitor.visit(node)


class _ValidationVisitor(ast.NodeVisitor):
    """AST visitor for validating nodes for HLS compatibility."""
    
    def visit_Call(self, node: ast.Call) -> None:
        """
        Validate function calls.
        
        Only allow built-in functions or user-defined functions.
        Disallow calls to external libraries except for a whitelist.
        """
        if isinstance(node.func, ast.Attribute):
            module_name = self._get_module_name(node.func)
            if module_name and module_name not in ['math']:
                raise ValueError(
                    f"Calls to external module '{module_name}' are not supported. "
                    "Only built-in functions, user-defined functions, and "
                    "the 'math' module are supported."
                )
        
        # Continue visiting children
        self.generic_visit(node)
    
    def _get_module_name(self, node: ast.Attribute) -> Optional[str]:
        """Extract the module name from an attribute node."""
        if isinstance(node.value, ast.Name):
            return node.value.id
        elif isinstance(node.value, ast.Attribute):
            parent = self._get_module_name(node.value)
            return f"{parent}.{node.attr}" if parent else None
        return None 