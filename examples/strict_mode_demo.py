"""
Demo: Strict Mode Compilation with Python-HLS

This example demonstrates the new "stricter contract" features:
1. Explicit latency annotations
2. Semantic validation
3. Refactor equivalence checking

Run with: python examples/strict_mode_demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python_hls import HLS, latency
from python_hls.constraints import (
    validate_semantics,
    check_refactor_equivalence,
    EquivalenceMode,
    SemanticViolationError,
    LatencyViolationError,
)


# =============================================================================
# Example 1: Clean code with latency constraint
# =============================================================================

# pragma hls latency 20
def gcd(a, b):
    """
    Calculate GCD using Euclidean algorithm.
    
    This function is annotated with a latency constraint.
    The compiler will verify the hardware meets this constraint.
    """
    while b:
        a, b = b, a % b
    return a


# =============================================================================
# Example 2: Code that violates semantic rules
# =============================================================================

BAD_CODE = '''
counter = 0  # Global mutable state - FORBIDDEN

def increment():
    global counter  # Using global keyword - FORBIDDEN
    counter += 1
    print(counter)  # Side effects - FORBIDDEN
    return counter
'''


# =============================================================================
# Example 3: Two functionally equivalent implementations
# =============================================================================

ORIGINAL_FIR = '''
def fir_filter(x, h0, h1, h2, h3):
    """Original FIR filter implementation."""
    return x * h0 + x * h1 + x * h2 + x * h3
'''

REFACTORED_FIR = '''
def fir_filter(x, h0, h1, h2, h3):
    """Refactored FIR filter - grouped multiplications."""
    sum_h = h0 + h1 + h2 + h3
    return x * sum_h
'''


def demo_semantic_validation():
    """Demonstrate semantic validation catching violations."""
    print("=" * 60)
    print("Demo: Semantic Validation")
    print("=" * 60)
    
    # Valid code should pass
    valid_code = '''
def add(a, b):
    return a + b
'''
    violations = validate_semantics(valid_code)
    print(f"\nValid code violations: {len(violations)}")
    
    # Invalid code should be caught
    violations = validate_semantics(BAD_CODE)
    print(f"Invalid code violations: {len(violations)}")
    for v in violations:
        print(f"  - {v}")
    
    print()


def demo_refactor_equivalence():
    """Demonstrate refactor equivalence checking."""
    print("=" * 60)
    print("Demo: Refactor Equivalence")
    print("=" * 60)
    
    # Check that the two FIR implementations are functionally equivalent
    print("\nChecking FIR filter refactor...")
    result = check_refactor_equivalence(
        ORIGINAL_FIR, 
        REFACTORED_FIR,
        mode=EquivalenceMode.FUNCTIONAL
    )
    
    print(f"Result: {result.summary()}")
    if result.equivalent:
        print("  Refactor is safe - behavior preserved!")
    else:
        print("  WARNING: Refactor changed behavior!")
        for m in result.mismatches[:3]:  # Show first 3 mismatches
            print(f"    {m}")
    
    print()


def demo_latency_constraints():
    """Demonstrate latency constraint enforcement."""
    print("=" * 60)
    print("Demo: Latency Constraints")
    print("=" * 60)
    
    code_with_constraint = '''
# pragma hls latency 50
def simple_math(a, b, c):
    x = a + b
    y = x * c
    return y
'''
    
    print("\nCompiling with latency constraint (50 cycles max)...")
    
    # Create HLS in strict mode
    hls = HLS(optimization_level=1, tech_node=45, strict_mode=True)
    
    # Write temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code_with_constraint)
        temp_path = f.name
    
    try:
        netlist, logs = hls.compile(temp_path)
        
        # Check the actual latency
        for func_name, func in hls.scheduled_ir.functions.items():
            actual = getattr(func, 'total_latency', 0)
            print(f"  Function '{func_name}': {actual} cycles")
            if func_name in hls.latency_constraints:
                constraint = hls.latency_constraints[func_name]
                status = "PASS" if constraint.validate(actual) else "FAIL"
                print(f"    Constraint: <= {constraint.max_cycles} cycles -> {status}")
    except LatencyViolationError as e:
        print(f"  Latency constraint violated: {e}")
    finally:
        os.unlink(temp_path)
    
    print()


def demo_strict_mode_compilation():
    """Demonstrate full strict mode compilation."""
    print("=" * 60)
    print("Demo: Strict Mode Compilation")
    print("=" * 60)
    
    clean_code = '''
# pragma hls latency 100
def matrix_element(a, b, c, d):
    """Clean, HLS-friendly code."""
    x = a * b
    y = c * d
    result = x + y
    return result
'''
    
    print("\nCompiling clean code in strict mode...")
    
    # First validate semantics
    violations = validate_semantics(clean_code)
    if violations:
        print("  Semantic violations found:")
        for v in violations:
            print(f"    - {v}")
        return
    
    print("  Semantic validation: PASS")
    
    # Compile with HLS
    hls = HLS(optimization_level=1, tech_node=45, strict_mode=True)
    
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(clean_code)
        temp_path = f.name
    
    try:
        netlist, logs = hls.compile(temp_path)
        print("  Compilation: PASS")
        
        # Get metrics
        metrics = hls.get_performance_metrics()
        print(f"  Latency: {metrics['latency_cycles']} cycles")
        print(f"  Area: {metrics['total_area']:.2f} μm²")
        
    except (LatencyViolationError, SemanticViolationError) as e:
        print(f"  Compilation FAILED: {e}")
    finally:
        os.unlink(temp_path)
    
    print()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Python-HLS Strict Mode Demo")
    print("Where the source code IS the hardware")
    print("=" * 60 + "\n")
    
    demo_semantic_validation()
    demo_refactor_equivalence()
    demo_latency_constraints()
    demo_strict_mode_compilation()
    
    print("=" * 60)
    print("Demo complete!")
    print("=" * 60)
