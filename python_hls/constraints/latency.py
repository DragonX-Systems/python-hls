"""
Explicit latency constraints for Python-HLS.

Provides a decorator and pragma system for specifying latency requirements
that the compiler MUST meet or fail compilation.
"""

import ast
import re
import functools
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, List, Union


class LatencyViolationError(Exception):
    """Raised when a latency constraint cannot be satisfied."""
    
    def __init__(self, function_name: str, constraint: int, actual: int, 
                 message: Optional[str] = None):
        self.function_name = function_name
        self.constraint = constraint
        self.actual = actual
        if message is None:
            message = (
                f"Latency constraint violated for '{function_name}': "
                f"required {constraint} cycles, compiler produced {actual} cycles. "
                f"Either relax the constraint or restructure the code."
            )
        super().__init__(message)


@dataclass
class LatencyConstraint:
    """
    Represents a latency constraint for a function.
    
    Attributes:
        max_cycles: Maximum latency in clock cycles (hard constraint)
        target_cycles: Target latency (soft constraint, for optimization guidance)
        mode: 'exact' = must match exactly, 'max' = upper bound, 'range' = within range
        min_cycles: Minimum latency (for 'range' mode)
        pipeline_ii: Initiation interval for pipelined functions
    """
    max_cycles: int
    target_cycles: Optional[int] = None
    mode: str = 'max'  # 'exact', 'max', 'range'
    min_cycles: Optional[int] = None
    pipeline_ii: Optional[int] = None
    
    def __post_init__(self):
        if self.mode == 'range' and self.min_cycles is None:
            raise ValueError("min_cycles required for 'range' mode")
        if self.mode == 'exact':
            self.min_cycles = self.max_cycles
        if self.target_cycles is None:
            self.target_cycles = self.max_cycles
    
    def validate(self, actual_cycles: int) -> bool:
        """Check if actual latency satisfies the constraint."""
        if self.mode == 'exact':
            return actual_cycles == self.max_cycles
        elif self.mode == 'max':
            return actual_cycles <= self.max_cycles
        elif self.mode == 'range':
            return self.min_cycles <= actual_cycles <= self.max_cycles
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize constraint to dictionary."""
        return {
            'max_cycles': self.max_cycles,
            'target_cycles': self.target_cycles,
            'mode': self.mode,
            'min_cycles': self.min_cycles,
            'pipeline_ii': self.pipeline_ii,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LatencyConstraint':
        """Deserialize constraint from dictionary."""
        return cls(**data)


# Global registry for latency constraints
_latency_constraints: Dict[str, LatencyConstraint] = {}


def latency(cycles: int, *, mode: str = 'max', min_cycles: Optional[int] = None,
            target: Optional[int] = None, pipeline_ii: Optional[int] = None) -> Callable:
    """
    Decorator to specify latency constraints for a function.
    
    The compiler MUST produce hardware that meets this constraint or fail.
    
    Args:
        cycles: Maximum (or exact) latency in clock cycles
        mode: 'exact' = must match exactly, 'max' = upper bound (default), 
              'range' = between min_cycles and cycles
        min_cycles: Minimum latency for 'range' mode
        target: Target latency for optimization (soft constraint)
        pipeline_ii: Required initiation interval for pipelined execution
    
    Examples:
        @latency(8)
        def gcd(a, b):
            ...  # Must complete in <= 8 cycles
        
        @latency(16, mode='exact')
        def fir_filter(x, coeffs):
            ...  # Must complete in exactly 16 cycles
        
        @latency(32, min_cycles=16, mode='range')
        def matrix_mult(A, B):
            ...  # Must complete between 16-32 cycles
        
        @latency(100, pipeline_ii=1)
        def streaming_kernel(data):
            ...  # New input every cycle (II=1)
    """
    constraint = LatencyConstraint(
        max_cycles=cycles,
        target_cycles=target,
        mode=mode,
        min_cycles=min_cycles,
        pipeline_ii=pipeline_ii,
    )
    
    def decorator(func: Callable) -> Callable:
        # Register the constraint
        func_name = func.__name__
        _latency_constraints[func_name] = constraint
        
        # Attach constraint to function for introspection
        func._hls_latency_constraint = constraint
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._hls_latency_constraint = constraint
        return wrapper
    
    return decorator


def get_latency_constraint(func_name: str) -> Optional[LatencyConstraint]:
    """Get the latency constraint for a function by name."""
    return _latency_constraints.get(func_name)


def clear_latency_constraints():
    """Clear all registered latency constraints (for testing)."""
    _latency_constraints.clear()


# Pragma patterns for latency constraints in comments
LATENCY_PRAGMA_PATTERNS = {
    'latency': r'#\s*pragma\s+hls\s+latency\s+(\d+)(?:\s+(\w+))?',
    'latency_range': r'#\s*pragma\s+hls\s+latency\s+(\d+)\s*-\s*(\d+)',
    'pipeline_ii': r'#\s*pragma\s+hls\s+pipeline\s+ii\s*=\s*(\d+)',
}


def parse_latency_pragma(comment: str) -> Optional[LatencyConstraint]:
    """
    Parse a latency pragma from a comment string.
    
    Supported formats:
        # pragma hls latency 8
        # pragma hls latency 8 exact
        # pragma hls latency 16-32
        # pragma hls pipeline ii=1
    
    Args:
        comment: Comment string to parse
        
    Returns:
        LatencyConstraint if valid pragma found, None otherwise
    """
    # Check for range format: latency 16-32
    match = re.search(LATENCY_PRAGMA_PATTERNS['latency_range'], comment, re.IGNORECASE)
    if match:
        min_cycles = int(match.group(1))
        max_cycles = int(match.group(2))
        return LatencyConstraint(max_cycles=max_cycles, min_cycles=min_cycles, mode='range')
    
    # Check for simple latency: latency 8 [exact|max]
    match = re.search(LATENCY_PRAGMA_PATTERNS['latency'], comment, re.IGNORECASE)
    if match:
        cycles = int(match.group(1))
        mode = match.group(2).lower() if match.group(2) else 'max'
        if mode not in ('exact', 'max'):
            mode = 'max'
        return LatencyConstraint(max_cycles=cycles, mode=mode)
    
    # Check for pipeline II
    match = re.search(LATENCY_PRAGMA_PATTERNS['pipeline_ii'], comment, re.IGNORECASE)
    if match:
        ii = int(match.group(1))
        # Pipeline II implies a constraint on throughput, not total latency
        # We return a constraint that captures this
        return LatencyConstraint(max_cycles=ii * 1000, pipeline_ii=ii)  # Large max, real constraint is II
    
    return None


def extract_latency_constraints_from_source(source: str) -> Dict[str, LatencyConstraint]:
    """
    Extract latency constraints from Python source code pragmas and decorators.
    
    Scans for:
    - @latency(...) decorators
    - # pragma hls latency ... comments before function definitions
    
    Args:
        source: Python source code
        
    Returns:
        Dictionary mapping function names to their latency constraints
    """
    constraints: Dict[str, LatencyConstraint] = {}
    lines = source.splitlines()
    
    # Track pending pragma (pragma on line before function)
    pending_pragma: Optional[LatencyConstraint] = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Check for pragma comment
        if stripped.startswith('#'):
            pragma = parse_latency_pragma(stripped)
            if pragma:
                pending_pragma = pragma
                continue
        
        # Check for function definition
        if stripped.startswith('def '):
            # Extract function name
            match = re.match(r'def\s+(\w+)\s*\(', stripped)
            if match:
                func_name = match.group(1)
                if pending_pragma:
                    constraints[func_name] = pending_pragma
                    pending_pragma = None
        else:
            # If line is not a def and not empty/comment, clear pending pragma
            if stripped and not stripped.startswith('#') and not stripped.startswith('@'):
                pending_pragma = None
    
    # Also check for decorator-based constraints in the AST
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    constraint = _parse_latency_decorator(decorator)
                    if constraint:
                        constraints[node.name] = constraint
    except SyntaxError:
        pass  # If we can't parse, just use pragma-based constraints
    
    return constraints


def _parse_latency_decorator(decorator: ast.expr) -> Optional[LatencyConstraint]:
    """Parse a @latency(...) decorator AST node."""
    if not isinstance(decorator, ast.Call):
        return None
    
    # Check if it's a call to 'latency'
    if isinstance(decorator.func, ast.Name) and decorator.func.id == 'latency':
        # Extract arguments
        cycles = None
        mode = 'max'
        min_cycles = None
        target = None
        pipeline_ii = None
        
        # Positional argument: cycles
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            cycles = decorator.args[0].value
        
        # Keyword arguments
        for kw in decorator.keywords:
            if kw.arg == 'mode' and isinstance(kw.value, ast.Constant):
                mode = kw.value.value
            elif kw.arg == 'min_cycles' and isinstance(kw.value, ast.Constant):
                min_cycles = kw.value.value
            elif kw.arg == 'target' and isinstance(kw.value, ast.Constant):
                target = kw.value.value
            elif kw.arg == 'pipeline_ii' and isinstance(kw.value, ast.Constant):
                pipeline_ii = kw.value.value
        
        if cycles is not None:
            return LatencyConstraint(
                max_cycles=cycles,
                target_cycles=target,
                mode=mode,
                min_cycles=min_cycles,
                pipeline_ii=pipeline_ii,
            )
    
    return None


def enforce_latency_constraint(func_name: str, actual_cycles: int, 
                               constraint: Optional[LatencyConstraint] = None) -> None:
    """
    Enforce a latency constraint, raising an error if violated.
    
    Args:
        func_name: Name of the function being compiled
        actual_cycles: Actual latency produced by the compiler
        constraint: Optional explicit constraint; if None, looks up from registry
        
    Raises:
        LatencyViolationError: If the constraint is violated
    """
    if constraint is None:
        constraint = get_latency_constraint(func_name)
    
    if constraint is None:
        return  # No constraint to enforce
    
    if not constraint.validate(actual_cycles):
        raise LatencyViolationError(
            function_name=func_name,
            constraint=constraint.max_cycles,
            actual=actual_cycles,
        )
