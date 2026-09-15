"""
Workload catalog registry for ML, Data-Science, and Finance benchmarks.
"""

from typing import Dict, List, Optional
from benchmarks.models import WorkloadConfig
from .catalog import get_workload_catalog


def load_all_workloads() -> Dict[str, WorkloadConfig]:
    """Load and return all registered workload configurations."""
    return get_workload_catalog()


def get_workload(name: str) -> Optional[WorkloadConfig]:
    """Get a specific workload configuration by name."""
    catalog = load_all_workloads()
    return catalog.get(name)


def get_workloads_by_domain(domain: str) -> List[WorkloadConfig]:
    """Get all workloads for a given domain ('ml', 'data_science', 'finance', 'all')."""
    catalog = load_all_workloads()
    if domain == "all":
        return list(catalog.values())
    return [w for w in catalog.values() if w.domain == domain]
