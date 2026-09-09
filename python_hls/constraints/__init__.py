"""
Hardware constraints module for Python-HLS.

This module provides:
- Explicit latency annotations
- Semantic validation rules
- Refactor equivalence checking
"""

from .latency import (
    latency, 
    LatencyConstraint, 
    LatencyViolationError,
    parse_latency_pragma,
    extract_latency_constraints_from_source,
    enforce_latency_constraint,
    get_latency_constraint,
    clear_latency_constraints,
)
from .semantic_rules import (
    SemanticValidator, 
    SemanticViolationError,
    SemanticValidatorConfig,
    ViolationType,
    validate_semantics,
    validate_semantics_strict,
)
from .equivalence import (
    EquivalenceChecker, 
    EquivalenceResult,
    EquivalenceMode,
    CompilationFingerprint,
    check_refactor_equivalence,
)

__all__ = [
    # Latency
    'latency',
    'LatencyConstraint',
    'LatencyViolationError',
    'parse_latency_pragma',
    'extract_latency_constraints_from_source',
    'enforce_latency_constraint',
    'get_latency_constraint',
    'clear_latency_constraints',
    # Semantic rules
    'SemanticValidator',
    'SemanticViolationError',
    'SemanticValidatorConfig',
    'ViolationType',
    'validate_semantics',
    'validate_semantics_strict',
    # Equivalence
    'EquivalenceChecker',
    'EquivalenceResult',
    'EquivalenceMode',
    'CompilationFingerprint',
    'check_refactor_equivalence',
]
