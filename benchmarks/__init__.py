"""
Python-HLS Benchmarks Suite.
Representative ML, Data-Science, and Quantitative Finance workloads.
"""

from .models import (
    WorkloadConfig,
    CompilationResult,
    EquivalenceResult,
    NodePPA,
    WorkloadResult,
)
from .runner import BenchmarkRunner
from .workloads import load_all_workloads, get_workload, get_workloads_by_domain

__all__ = [
    "WorkloadConfig",
    "CompilationResult",
    "EquivalenceResult",
    "NodePPA",
    "WorkloadResult",
    "BenchmarkRunner",
    "load_all_workloads",
    "get_workload",
    "get_workloads_by_domain",
]
