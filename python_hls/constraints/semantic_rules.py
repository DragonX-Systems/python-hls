"""
Semantic validation rules for Python-HLS.

Enforces stricter rules than just syntax checking:
- No global mutable state
- No non-deterministic operations
- No hidden side effects
- Explicit data flow

The goal: If it compiles, the source IS the hardware spec.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from enum import Enum, auto


class ViolationType(Enum):
    """Categories of semantic violations."""
    GLOBAL_MUTABLE_STATE = auto()
    NON_DETERMINISM = auto()
    HIDDEN_SIDE_EFFECT = auto()
    IMPLICIT_STATE = auto()
    UNBOUNDED_RECURSION = auto()
    DYNAMIC_ALLOCATION = auto()
    EXTERNAL_DEPENDENCY = auto()


@dataclass
class SemanticViolation:
    """Represents a single semantic rule violation."""
    violation_type: ViolationType
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    node_name: Optional[str] = None
    
    def __str__(self) -> str:
        loc = f" at line {self.line}" if self.line else ""
        return f"[{self.violation_type.name}]{loc}: {self.message}"


class SemanticViolationError(Exception):
    """Raised when semantic validation fails."""
    
    def __init__(self, violations: List[SemanticViolation]):
        self.violations = violations
        messages = [str(v) for v in violations]
        super().__init__(
            f"Semantic validation failed with {len(violations)} violation(s):\n" +
            "\n".join(f"  - {m}" for m in messages)
        )


@dataclass
class SemanticValidatorConfig:
    """Configuration for semantic validation strictness."""
    # Strict mode: fail on any violation
    strict: bool = True
    
    # Individual rule toggles (all on by default in strict mode)
    forbid_global_mutable: bool = True
    forbid_non_determinism: bool = True
    forbid_recursion: bool = True  # Unbounded recursion
    forbid_dynamic_allocation: bool = True
    forbid_external_calls: bool = True
    
    # Whitelist for allowed external modules (empty = none allowed in strict)
    allowed_modules: Set[str] = field(default_factory=lambda: {'math'})
    
    # Whitelist for allowed builtins
    allowed_builtins: Set[str] = field(default_factory=lambda: {
        'range', 'len', 'int', 'bool', 'abs', 'min', 'max', 'sum',
        'True', 'False', 'None',
    })


class SemanticValidator(ast.NodeVisitor):
    """
    AST visitor that enforces strict semantic rules.
    
    Rules enforced:
    1. No global mutable state (module-level variables that are written)
    2. No non-deterministic operations (random, time, etc.)
    3. No hidden side effects (print, file I/O, network)
    4. No unbounded recursion without explicit depth limits
    5. No dynamic memory allocation (no append, extend, etc.)
    6. No external dependencies except whitelisted
    
    The philosophy: If the compiler accepts it, the Python source
    IS the hardware specification. No surprises.
    """
    
    # Known non-deterministic functions
    NON_DETERMINISTIC = {
        'random', 'randint', 'choice', 'shuffle', 'sample',
        'time', 'now', 'datetime', 'timestamp',
        'uuid', 'uuid4',
        'input',
    }
    
    # Functions with side effects
    SIDE_EFFECTS = {
        'print', 'open', 'write', 'read', 'close',
        'send', 'recv', 'connect', 'socket',
        'exec', 'eval', 'compile',
        '__import__',
    }
    
    # Dynamic allocation methods
    DYNAMIC_ALLOC = {
        'append', 'extend', 'insert', 'pop', 'remove', 'clear',
        'add', 'discard', 'update',  # set methods
    }
    
    def __init__(self, config: Optional[SemanticValidatorConfig] = None):
        self.config = config or SemanticValidatorConfig()
        self.violations: List[SemanticViolation] = []
        
        # Track state during validation
        self._current_function: Optional[str] = None
        self._function_calls: Dict[str, Set[str]] = {}  # func -> set of called funcs
        self._defined_functions: Set[str] = set()
        self._global_writes: Set[str] = set()
        self._local_vars: Set[str] = set()
    
    def validate(self, tree: ast.AST) -> List[SemanticViolation]:
        """
        Validate an AST against semantic rules.
        
        Args:
            tree: AST to validate
            
        Returns:
            List of violations found (empty if valid)
        """
        self.violations = []
        self._function_calls = {}
        self._defined_functions = set()
        self._global_writes = set()
        
        # First pass: collect function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self._defined_functions.add(node.name)
        
        # Second pass: full validation
        self.visit(tree)
        
        # Post-validation: check for recursion
        if self.config.forbid_recursion:
            self._check_recursion()
        
        return self.violations
    
    def validate_strict(self, tree: ast.AST) -> None:
        """
        Validate and raise an error if any violations found.
        
        Args:
            tree: AST to validate
            
        Raises:
            SemanticViolationError: If any violations found
        """
        violations = self.validate(tree)
        if violations and self.config.strict:
            raise SemanticViolationError(violations)
    
    def _add_violation(self, violation_type: ViolationType, message: str,
                       node: Optional[ast.AST] = None):
        """Add a violation to the list."""
        line = getattr(node, 'lineno', None) if node else None
        col = getattr(node, 'col_offset', None) if node else None
        self.violations.append(SemanticViolation(
            violation_type=violation_type,
            message=message,
            line=line,
            column=col,
        ))
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function context."""
        old_function = self._current_function
        old_locals = self._local_vars.copy()
        
        self._current_function = node.name
        self._local_vars = set()
        self._function_calls[node.name] = set()
        
        # Add parameters to local vars
        for arg in node.args.args:
            self._local_vars.add(arg.arg)
        
        self.generic_visit(node)
        
        self._current_function = old_function
        self._local_vars = old_locals
    
    def visit_Assign(self, node: ast.Assign):
        """Check for global mutable state."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                
                # If we're in a function, it's a local
                if self._current_function:
                    self._local_vars.add(name)
                else:
                    # Module-level assignment = global mutable state
                    if self.config.forbid_global_mutable:
                        # Allow constants (all caps by convention)
                        if not name.isupper():
                            self._global_writes.add(name)
                            self._add_violation(
                                ViolationType.GLOBAL_MUTABLE_STATE,
                                f"Global mutable variable '{name}' is forbidden. "
                                f"Use function parameters instead, or make it a constant (ALL_CAPS).",
                                node
                            )
        
        self.generic_visit(node)
    
    def visit_Global(self, node: ast.Global):
        """Forbid 'global' keyword."""
        if self.config.forbid_global_mutable:
            for name in node.names:
                self._add_violation(
                    ViolationType.GLOBAL_MUTABLE_STATE,
                    f"'global {name}' is forbidden. Hardware has no global state. "
                    f"Pass data explicitly through function parameters.",
                    node
                )
    
    def visit_Nonlocal(self, node: ast.Nonlocal):
        """Forbid 'nonlocal' keyword."""
        if self.config.forbid_global_mutable:
            for name in node.names:
                self._add_violation(
                    ViolationType.IMPLICIT_STATE,
                    f"'nonlocal {name}' is forbidden. Implicit state is not supported. "
                    f"Use explicit return values instead.",
                    node
                )
    
    def visit_Call(self, node: ast.Call):
        """Check function calls for violations."""
        func_name = self._get_call_name(node)
        
        if func_name:
            # Track function calls for recursion detection
            if self._current_function:
                self._function_calls[self._current_function].add(func_name)
            
            # Check for non-deterministic functions
            if self.config.forbid_non_determinism and func_name in self.NON_DETERMINISTIC:
                self._add_violation(
                    ViolationType.NON_DETERMINISM,
                    f"Non-deterministic function '{func_name}' is forbidden. "
                    f"Hardware must be deterministic.",
                    node
                )
            
            # Check for side effects
            if func_name in self.SIDE_EFFECTS:
                self._add_violation(
                    ViolationType.HIDDEN_SIDE_EFFECT,
                    f"Function '{func_name}' has side effects and is forbidden. "
                    f"Hardware functions must be pure.",
                    node
                )
            
            # Check for forbidden external calls
            if self.config.forbid_external_calls:
                if '.' in func_name:
                    module = func_name.split('.')[0]
                    if module not in self.config.allowed_modules:
                        self._add_violation(
                            ViolationType.EXTERNAL_DEPENDENCY,
                            f"External module '{module}' is not allowed. "
                            f"Allowed: {self.config.allowed_modules}",
                            node
                        )
                elif func_name not in self._defined_functions:
                    if func_name not in self.config.allowed_builtins:
                        self._add_violation(
                            ViolationType.EXTERNAL_DEPENDENCY,
                            f"Unknown function '{func_name}' is not allowed. "
                            f"Only user-defined functions and whitelisted builtins are permitted.",
                            node
                        )
        
        # Check for dynamic allocation methods
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if self.config.forbid_dynamic_allocation and method_name in self.DYNAMIC_ALLOC:
                self._add_violation(
                    ViolationType.DYNAMIC_ALLOCATION,
                    f"Dynamic allocation method '{method_name}' is forbidden. "
                    f"Use fixed-size arrays instead.",
                    node
                )
        
        self.generic_visit(node)
    
    def visit_ListComp(self, node: ast.ListComp):
        """List comprehensions are allowed if size is determinable."""
        # For now, allow simple list comprehensions
        # More sophisticated analysis could check if size is compile-time constant
        self.generic_visit(node)
    
    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        """Generator expressions are not supported (lazy evaluation)."""
        self._add_violation(
            ViolationType.DYNAMIC_ALLOCATION,
            "Generator expressions are not supported. Use list comprehensions instead.",
            node
        )
    
    def visit_Yield(self, node: ast.Yield):
        """Yield is not supported."""
        self._add_violation(
            ViolationType.IMPLICIT_STATE,
            "'yield' is not supported. Generators require implicit state.",
            node
        )
    
    def visit_YieldFrom(self, node: ast.YieldFrom):
        """Yield from is not supported."""
        self._add_violation(
            ViolationType.IMPLICIT_STATE,
            "'yield from' is not supported. Generators require implicit state.",
            node
        )
    
    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Extract the function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                return '.'.join(reversed(parts))
        return None
    
    def _check_recursion(self):
        """Check for recursive function calls."""
        # Build call graph and detect cycles
        for func, calls in self._function_calls.items():
            if func in calls:
                # Direct recursion
                self._add_violation(
                    ViolationType.UNBOUNDED_RECURSION,
                    f"Direct recursion in '{func}' is not supported. "
                    f"Use explicit loops or pragma-annotated bounded recursion.",
                    None
                )
            else:
                # Check for indirect recursion
                visited = set()
                if self._has_cycle(func, visited):
                    self._add_violation(
                        ViolationType.UNBOUNDED_RECURSION,
                        f"Indirect recursion detected involving '{func}'. "
                        f"Recursive call chains are not supported.",
                        None
                    )
    
    def _has_cycle(self, start: str, visited: Set[str], 
                   path: Optional[Set[str]] = None) -> bool:
        """Check if there's a cycle in the call graph starting from 'start'."""
        if path is None:
            path = set()
        
        if start in path:
            return True
        if start in visited:
            return False
        
        visited.add(start)
        path.add(start)
        
        for called in self._function_calls.get(start, set()):
            if called in self._defined_functions:
                if self._has_cycle(called, visited, path):
                    return True
        
        path.remove(start)
        return False


def validate_semantics(source: str, strict: bool = True) -> List[SemanticViolation]:
    """
    Convenience function to validate Python source code semantics.
    
    Args:
        source: Python source code
        strict: If True, use strict validation rules
        
    Returns:
        List of violations (empty if valid)
    """
    tree = ast.parse(source)
    config = SemanticValidatorConfig(strict=strict)
    validator = SemanticValidator(config)
    return validator.validate(tree)


def validate_semantics_strict(source: str) -> None:
    """
    Validate Python source code and raise on any violation.
    
    Args:
        source: Python source code
        
    Raises:
        SemanticViolationError: If any violations found
    """
    tree = ast.parse(source)
    validator = SemanticValidator()
    validator.validate_strict(tree)
