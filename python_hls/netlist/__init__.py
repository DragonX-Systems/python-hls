"""
Netlist module for representing hardware structures.
"""

from .netlist import Netlist, NetlistModule, NetlistPort, NetlistSignal, NetlistResource, NetlistOperation
from .streaming_components import (
    FIFOResource, 
    CrossbarResource, 
    StreamingChannel, 
    StreamingArchitecture,
    create_fifo_read_operation,
    create_fifo_write_operation,
    create_crossbar_route_operation
) 