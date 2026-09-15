"""
Deterministic diagnostic exceptions for the JAX frontend and Jaxpr lowering pass.
"""


class JAXFrontendError(Exception):
    """Base exception for all JAX frontend errors in Python-HLS."""
    pass


class JAXShapeError(JAXFrontendError):
    """Raised when tensor/array shapes violate static hardware bounds or dimension constraints."""
    pass


class JAXDTypeError(JAXFrontendError):
    """Raised when data types cannot be synthesized into fixed-width hardware registers."""
    pass


class JAXUnsupportedPrimitiveError(JAXFrontendError):
    """Raised when a JAX/Jaxpr primitive equation has no qualified hardware lowering."""
    pass
