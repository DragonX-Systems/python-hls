"""
Data models and configuration definitions for representative HLS benchmarks.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import json


@dataclass
class NodePPA:
    """Power, Performance, and Area metrics for a specific technology node."""
    node_nm: int
    area_um2: float
    power_mw: float
    latency_cycles: int
    latency_ns: float
    frequency_mhz: float
    critical_path_ns: float
    resource_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_nm": self.node_nm,
            "area_um2": round(self.area_um2, 2),
            "power_mw": round(self.power_mw, 3),
            "latency_cycles": self.latency_cycles,
            "latency_ns": round(self.latency_ns, 2),
            "frequency_mhz": round(self.frequency_mhz, 1),
            "critical_path_ns": round(self.critical_path_ns, 3),
            "resource_counts": self.resource_counts,
        }


@dataclass
class CompilationResult:
    """Status and metrics from the HLS compilation phase."""
    status: str  # "PASS" or "FAIL"
    error: Optional[str] = None
    operations_count: int = 0
    cycle_latency: int = 0
    modules: List[str] = field(default_factory=list)
    verilog_path: Optional[str] = None
    log_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "error": self.error,
            "operations_count": self.operations_count,
            "cycle_latency": self.cycle_latency,
            "modules": self.modules,
            "verilog_path": self.verilog_path,
        }


@dataclass
class EquivalenceResult:
    """Status and results from simulation/functional equivalence verification."""
    status: str  # "PASS", "FAIL", or "SKIPPED"
    total_vectors: int = 0
    passed_vectors: int = 0
    failed_vectors: int = 0
    sim_backend: str = "python_reference"  # "python_reference", "verilator", etc.
    mismatches: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "total_vectors": self.total_vectors,
            "passed_vectors": self.passed_vectors,
            "failed_vectors": self.failed_vectors,
            "sim_backend": self.sim_backend,
            "mismatches": self.mismatches[:5],
            "error": self.error,
        }


@dataclass
class WorkloadConfig:
    """Static metadata and execution specification for a pinned workload."""
    name: str
    domain: str  # "ml", "data_science", "finance"
    display_name: str
    description: str
    source_file: str
    entry_function: str
    shapes: Dict[str, Any]
    dtypes: Dict[str, str]
    quantization: str
    hardware_assumptions: List[str]
    unsupported_operations: List[str]
    reference_fn: Optional[Callable[..., Any]] = None
    test_vectors: List[Dict[str, Any]] = field(default_factory=list)
    target_frequency_mhz: float = 1000.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "display_name": self.display_name,
            "description": self.description,
            "source_file": self.source_file,
            "entry_function": self.entry_function,
            "shapes": self.shapes,
            "dtypes": self.dtypes,
            "quantization": self.quantization,
            "hardware_assumptions": self.hardware_assumptions,
            "unsupported_operations": self.unsupported_operations,
            "target_frequency_mhz": self.target_frequency_mhz,
            "num_test_vectors": len(self.test_vectors),
        }


@dataclass
class WorkloadResult:
    """Aggregate benchmark result for a workload, separating compilation, equivalence, and PPA."""
    workload: WorkloadConfig
    compilation: CompilationResult
    equivalence: EquivalenceResult
    ppa_by_node: Dict[int, NodePPA] = field(default_factory=dict)  # node_nm -> NodePPA

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workload": self.workload.to_dict(),
            "compilation": self.compilation.to_dict(),
            "equivalence": self.equivalence.to_dict(),
            "ppa": {str(k): v.to_dict() for k, v in self.ppa_by_node.items()},
        }
