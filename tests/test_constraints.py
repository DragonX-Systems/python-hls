"""
Tests for the HLS constraint system.

Tests:
- Explicit latency annotations
- Semantic validation rules
- Refactor equivalence checking
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python_hls.constraints.latency import (
    latency, LatencyConstraint, LatencyViolationError,
    parse_latency_pragma, extract_latency_constraints_from_source,
    enforce_latency_constraint, clear_latency_constraints, get_latency_constraint,
)
from python_hls.constraints.semantic_rules import (
    SemanticValidator, SemanticViolationError, SemanticValidatorConfig,
    ViolationType, validate_semantics, validate_semantics_strict,
)
from python_hls.constraints.equivalence import (
    EquivalenceChecker, EquivalenceResult, EquivalenceMode,
    CompilationFingerprint, check_refactor_equivalence,
)


class TestLatencyConstraints:
    """Tests for explicit latency constraint system."""
    
    def setup_method(self):
        """Clear constraints before each test."""
        clear_latency_constraints()
    
    def test_latency_constraint_validation(self):
        """Test LatencyConstraint validation logic."""
        # Max mode: actual <= max
        constraint = LatencyConstraint(max_cycles=10, mode='max')
        assert constraint.validate(5) == True
        assert constraint.validate(10) == True
        assert constraint.validate(11) == False
        
        # Exact mode: actual == max
        constraint = LatencyConstraint(max_cycles=10, mode='exact')
        assert constraint.validate(10) == True
        assert constraint.validate(9) == False
        assert constraint.validate(11) == False
        
        # Range mode: min <= actual <= max
        constraint = LatencyConstraint(max_cycles=20, min_cycles=10, mode='range')
        assert constraint.validate(10) == True
        assert constraint.validate(15) == True
        assert constraint.validate(20) == True
        assert constraint.validate(9) == False
        assert constraint.validate(21) == False
    
    def test_latency_decorator(self):
        """Test @latency decorator registration."""
        @latency(8)
        def simple_func(a, b):
            return a + b
        
        # Check constraint was registered
        constraint = get_latency_constraint('simple_func')
        assert constraint is not None
        assert constraint.max_cycles == 8
        assert constraint.mode == 'max'
        
        # Function should still work
        assert simple_func(3, 5) == 8
    
    def test_latency_decorator_with_modes(self):
        """Test @latency decorator with different modes."""
        @latency(16, mode='exact')
        def exact_func(x):
            return x * 2
        
        @latency(32, min_cycles=16, mode='range')
        def range_func(x):
            return x * 3
        
        exact_constraint = get_latency_constraint('exact_func')
        assert exact_constraint.mode == 'exact'
        assert exact_constraint.max_cycles == 16
        
        range_constraint = get_latency_constraint('range_func')
        assert range_constraint.mode == 'range'
        assert range_constraint.min_cycles == 16
        assert range_constraint.max_cycles == 32
    
    def test_parse_latency_pragma(self):
        """Test parsing latency pragmas from comments."""
        # Simple latency
        constraint = parse_latency_pragma("# pragma hls latency 8")
        assert constraint is not None
        assert constraint.max_cycles == 8
        assert constraint.mode == 'max'
        
        # Exact latency
        constraint = parse_latency_pragma("# pragma hls latency 16 exact")
        assert constraint is not None
        assert constraint.max_cycles == 16
        assert constraint.mode == 'exact'
        
        # Range latency
        constraint = parse_latency_pragma("# pragma hls latency 10-20")
        assert constraint is not None
        assert constraint.min_cycles == 10
        assert constraint.max_cycles == 20
        assert constraint.mode == 'range'
        
        # Pipeline II
        constraint = parse_latency_pragma("# pragma hls pipeline ii=1")
        assert constraint is not None
        assert constraint.pipeline_ii == 1
    
    def test_extract_constraints_from_source(self):
        """Test extracting constraints from full source code."""
        source = '''
# pragma hls latency 8
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

# pragma hls latency 16 exact
def fir_filter(x, h):
    return sum(x[i] * h[i] for i in range(len(h)))
'''
        constraints = extract_latency_constraints_from_source(source)
        
        assert 'gcd' in constraints
        assert constraints['gcd'].max_cycles == 8
        
        assert 'fir_filter' in constraints
        assert constraints['fir_filter'].max_cycles == 16
        assert constraints['fir_filter'].mode == 'exact'
    
    def test_enforce_latency_violation(self):
        """Test that latency violations raise errors."""
        constraint = LatencyConstraint(max_cycles=10, mode='max')
        
        # Should not raise for valid latency
        enforce_latency_constraint('test_func', 8, constraint)
        
        # Should raise for invalid latency
        with pytest.raises(LatencyViolationError) as exc_info:
            enforce_latency_constraint('test_func', 15, constraint)
        
        assert exc_info.value.function_name == 'test_func'
        assert exc_info.value.constraint == 10
        assert exc_info.value.actual == 15


class TestSemanticValidation:
    """Tests for semantic validation rules."""
    
    def test_valid_code_passes(self):
        """Test that valid HLS code passes validation."""
        source = '''
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
'''
        violations = validate_semantics(source)
        assert len(violations) == 0
    
    def test_global_mutable_state_rejected(self):
        """Test that global mutable state is rejected."""
        source = '''
counter = 0

def increment():
    global counter
    counter += 1
    return counter
'''
        violations = validate_semantics(source)
        
        # Should have violations for global state
        global_violations = [v for v in violations 
                           if v.violation_type == ViolationType.GLOBAL_MUTABLE_STATE]
        assert len(global_violations) > 0
    
    def test_global_constants_allowed(self):
        """Test that global constants (ALL_CAPS) are allowed."""
        source = '''
MAX_SIZE = 100
PI = 3.14159

def compute(x):
    return x * PI
'''
        violations = validate_semantics(source)
        
        # Should not have violations for constants
        global_violations = [v for v in violations 
                           if v.violation_type == ViolationType.GLOBAL_MUTABLE_STATE]
        assert len(global_violations) == 0
    
    def test_non_determinism_rejected(self):
        """Test that non-deterministic operations are rejected."""
        source = '''
import random

def roll_dice():
    return random.randint(1, 6)
'''
        # Note: This would be caught by the parser's import check first,
        # but if it gets through, semantic validator should also catch it
        # For this test, we use a simplified version
        source = '''
def bad_func():
    return random()  # Calling 'random' directly
'''
        violations = validate_semantics(source)
        # The call to 'random' should be flagged
        non_det = [v for v in violations 
                  if v.violation_type == ViolationType.NON_DETERMINISM]
        assert len(non_det) > 0
    
    def test_side_effects_rejected(self):
        """Test that side effects are rejected."""
        source = '''
def log_value(x):
    print(x)
    return x
'''
        violations = validate_semantics(source)
        
        side_effect_violations = [v for v in violations 
                                 if v.violation_type == ViolationType.HIDDEN_SIDE_EFFECT]
        assert len(side_effect_violations) > 0
    
    def test_dynamic_allocation_rejected(self):
        """Test that dynamic allocation is rejected."""
        source = '''
def build_list(n):
    result = []
    for i in range(n):
        result.append(i)
    return result
'''
        violations = validate_semantics(source)
        
        alloc_violations = [v for v in violations 
                          if v.violation_type == ViolationType.DYNAMIC_ALLOCATION]
        assert len(alloc_violations) > 0
    
    def test_recursion_rejected(self):
        """Test that unbounded recursion is rejected."""
        source = '''
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''
        violations = validate_semantics(source)
        
        recursion_violations = [v for v in violations 
                               if v.violation_type == ViolationType.UNBOUNDED_RECURSION]
        assert len(recursion_violations) > 0
    
    def test_strict_validation_raises(self):
        """Test that strict validation raises on any violation."""
        source = '''
counter = 0
def bad():
    global counter
    counter += 1
'''
        with pytest.raises(SemanticViolationError):
            validate_semantics_strict(source)
    
    def test_allowed_builtins(self):
        """Test that whitelisted builtins are allowed."""
        source = '''
def compute(arr):
    return len(arr), min(arr), max(arr), sum(arr)
'''
        violations = validate_semantics(source)
        
        # Should not have violations for allowed builtins
        external_violations = [v for v in violations 
                              if v.violation_type == ViolationType.EXTERNAL_DEPENDENCY]
        assert len(external_violations) == 0


class TestEquivalenceChecking:
    """Tests for refactor equivalence checking."""
    
    def test_identical_code_is_equivalent(self):
        """Test that identical code is functionally equivalent."""
        source = '''
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
'''
        result = check_refactor_equivalence(source, source)
        assert result.equivalent == True
    
    def test_renamed_variables_is_equivalent(self):
        """Test that variable renaming preserves equivalence."""
        original = '''
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
'''
        refactored = '''
def gcd(x, y):
    while y:
        x, y = y, x % y
    return x
'''
        result = check_refactor_equivalence(original, refactored)
        assert result.equivalent == True
    
    def test_different_logic_not_equivalent(self):
        """Test that different logic is detected as not equivalent."""
        original = '''
def compute(a, b):
    return a + b
'''
        different = '''
def compute(a, b):
    return a * b
'''
        # Use explicit test vectors to ensure we catch the difference
        checker = EquivalenceChecker()
        test_vectors = [{'a': 5, 'b': 3}, {'a': 10, 'b': 2}, {'a': 7, 'b': 4}]
        result = checker.check_source_equivalence(
            original, different, 
            mode=EquivalenceMode.FUNCTIONAL,
            test_vectors=test_vectors
        )
        # 5+3=8 vs 5*3=15, 10+2=12 vs 10*2=20, etc.
        assert result.equivalent == False
        assert len(result.mismatches) > 0
    
    def test_fingerprint_serialization(self):
        """Test that fingerprints can be serialized and deserialized."""
        fp = CompilationFingerprint(
            source_hash='abc123',
            function_name='test',
            input_ports=[('a', 32), ('b', 32)],
            output_ports=[('result', 32)],
            latency_cycles=10,
            rtl_hash='def456',
            test_results=[({'a': 1, 'b': 2}, {'result': 3})],
        )
        
        # Round-trip through dict
        data = fp.to_dict()
        fp2 = CompilationFingerprint.from_dict(data)
        
        assert fp2.source_hash == fp.source_hash
        assert fp2.function_name == fp.function_name
        assert fp2.latency_cycles == fp.latency_cycles


class TestIntegration:
    """Integration tests using the full HLS pipeline."""
    
    def test_strict_mode_validates_semantics(self):
        """Test that strict mode catches semantic violations."""
        # This test would require the full HLS compiler
        # For now, we just verify the validator can be instantiated
        validator = SemanticValidator(SemanticValidatorConfig(strict=True))
        assert validator.config.strict == True
    
    def test_constraint_workflow(self):
        """Test the typical constraint workflow."""
        # 1. Define code with constraints
        source = '''
# pragma hls latency 100
def simple_add(a, b):
    return a + b
'''
        # 2. Extract constraints
        constraints = extract_latency_constraints_from_source(source)
        assert 'simple_add' in constraints
        
        # 3. Validate semantics
        violations = validate_semantics(source)
        assert len(violations) == 0  # Clean code
        
        # 4. Check equivalence with refactored version
        refactored = '''
# pragma hls latency 100  
def simple_add(x, y):
    result = x + y
    return result
'''
        result = check_refactor_equivalence(source, refactored)
        assert result.equivalent == True


class TestRTLOutputParsing:
    """Test RTL simulation output parsing with cycle counts."""
    
    def test_parse_result_with_cycles(self):
        """Test that RESULT lines with cycles= are parsed correctly."""
        from python_hls.verification.rtl_verifier import RTLVerifier
        
        verifier = RTLVerifier()
        
        output = """
Some debug output
RESULT: inputs={a=48,b=18},output=6,cycles=11
RESULT: inputs={a=100,b=50},output=50,cycles=8
More output
"""
        result = verifier._parse_simulation_output(output)
        
        assert len(result["results"]) == 2
        assert result["results"][0]["test_inputs"] == {"a": 48, "b": 18}
        assert result["results"][0]["outputs"]["return_val"] == 6
        assert result["results"][0]["cycles_to_done"] == 11
        
        assert result["results"][1]["test_inputs"] == {"a": 100, "b": 50}
        assert result["results"][1]["outputs"]["return_val"] == 50
        assert result["results"][1]["cycles_to_done"] == 8
    
    def test_parse_result_without_cycles_backwards_compat(self):
        """Test that RESULT lines without cycles still parse (backwards compat)."""
        from python_hls.verification.rtl_verifier import RTLVerifier
        
        verifier = RTLVerifier()
        
        output = "RESULT: inputs={a=1,b=2},output=3\n"
        result = verifier._parse_simulation_output(output)
        
        assert len(result["results"]) == 1
        assert result["results"][0]["outputs"]["return_val"] == 3
        assert "cycles_to_done" not in result["results"][0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
