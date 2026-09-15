"""
Python-HLS Constraint-Driven Hardware Pipelines and Standard Interfaces.

Exports:
- PipelineSpec: Pipeline configuration specification
- PipelineInterfaceType: Supported standard interface protocols (AXIS, READY_VALID, MEMORY)
- PipelineVerilogGenerator: Synthesizable Verilog code generator
- PipelineVerifier: Automated protocol verification and Verilator co-simulation
- PipelineVerificationResult: Simulation and protocol verification result dataclass
- PipelineCycleSimulator: Cycle-accurate reference model in Python
- pipeline: Function decorator for declaring pipelined accelerator lanes
- get_pipeline_spec, clear_pipeline_specs: Specification registry management
"""

from .spec import (
    PipelineSpec,
    PipelineInterfaceType,
    pipeline,
    get_pipeline_spec,
    clear_pipeline_specs,
)
from .generator import (
    PipelineVerilogGenerator,
)
from .verifier import (
    PipelineVerifier,
    PipelineVerificationResult,
    PipelineCycleSimulator,
)

__all__ = [
    "PipelineSpec",
    "PipelineInterfaceType",
    "PipelineVerilogGenerator",
    "PipelineVerifier",
    "PipelineVerificationResult",
    "PipelineCycleSimulator",
    "pipeline",
    "get_pipeline_spec",
    "clear_pipeline_specs",
]
