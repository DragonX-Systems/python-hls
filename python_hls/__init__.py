"""
Python-HLS: A High-Level Synthesis tool for Python

Where the source code IS the hardware.
"""

from .hls import HLS
from .netlist import Netlist, NetlistModule

# Constraint system for strict compilation
from .constraints import (
    # Latency constraints
    latency,
    LatencyConstraint,
    LatencyViolationError,
    # Semantic validation
    SemanticValidator,
    SemanticViolationError,
    # Equivalence checking
    EquivalenceChecker,
    EquivalenceResult,
)

# Apply patch to fix area calculation in NetlistModule
# Store the original add_resource method
original_add_resource = NetlistModule.add_resource

# Define a new add_resource method that updates the area
def patched_add_resource(self, resource):
    # Call the original method first
    original_add_resource(self, resource)
    
    # Update the module's area when a resource is added
    self.area = sum(r.area for r in self.resources)
    self.power = sum(r.power for r in self.resources)

# Replace the original method with our patched version
NetlistModule.add_resource = patched_add_resource

# NumPy frontend for bounded array kernels
from .frontend.numpy import (
    numpy_kernel,
    ArraySpec,
    KernelSpec,
    NumPyFrontend,
    NumPyFrontendError,
    NumPyShapeError,
    NumPyDTypeError,
    NumPyUnsupportedOperationError,
)

# JAX frontend for static lowerable kernels
from .frontend.jax import (
    jax_kernel,
    JAXArraySpec,
    JAXKernelSpec,
    JaxprGraph,
    JaxprNode,
    JaxprVariable,
    trace_jax_kernel,
    jaxpr_to_ir,
    JAXFrontendError,
    JAXShapeError,
    JAXDTypeError,
    JAXUnsupportedPrimitiveError,
)

from .handoff import (
    FlowManifest,
    DesignSpec,
    TechnologySpec,
    FlowConfig,
    DSEEstimateSpec,
    SDCGenerator,
    SDCConfig,
    OpenLaneRunner,
    HandoffResult,
    ReportIngestionEngine,
    ImplementationReport,
    DSECalibrator,
    CalibrationReport,
)

__version__ = "0.1.0"

__all__ = [
    'HLS',
    'Netlist',
    'NetlistModule',
    # Constraints
    'latency',
    'LatencyConstraint',
    'LatencyViolationError',
    'SemanticValidator',
    'SemanticViolationError',
    'EquivalenceChecker',
    'EquivalenceResult',
    # NumPy frontend
    'numpy_kernel',
    'ArraySpec',
    'KernelSpec',
    'NumPyFrontend',
    'NumPyFrontendError',
    'NumPyShapeError',
    'NumPyDTypeError',
    'NumPyUnsupportedOperationError',
    # JAX frontend
    'jax_kernel',
    'JAXArraySpec',
    'JAXKernelSpec',
    'JaxprGraph',
    'JaxprNode',
    'JaxprVariable',
    'trace_jax_kernel',
    'jaxpr_to_ir',
    'JAXFrontendError',
    'JAXShapeError',
    'JAXDTypeError',
    'JAXUnsupportedPrimitiveError',
    # GPU-OpenLane Handoff & DSE Calibration
    'FlowManifest',
    'DesignSpec',
    'TechnologySpec',
    'FlowConfig',
    'DSEEstimateSpec',
    'SDCGenerator',
    'SDCConfig',
    'OpenLaneRunner',
    'HandoffResult',
    'ReportIngestionEngine',
    'ImplementationReport',
    'DSECalibrator',
    'CalibrationReport',
]
