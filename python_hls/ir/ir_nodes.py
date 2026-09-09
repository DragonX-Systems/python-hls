"""
IR nodes for representing Python constructs in a hardware-friendly way.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union, Any, Tuple


class OperationType(Enum):
    """Types of operations supported in the IR."""
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    POW = auto()
    LSHIFT = auto()
    RSHIFT = auto()
    BIT_OR = auto()
    BIT_AND = auto()
    BIT_XOR = auto()
    LOGIC_OR = auto()
    LOGIC_AND = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    LTE = auto()
    GT = auto()
    GTE = auto()
    NEG = auto()
    NOT = auto()
    BIT_NOT = auto()
    ASSIGN = auto()  # Assignment operation
    RETURN = auto()  # Return operation
    STORE = auto()   # Memory store operation
    LOAD = auto()    # Memory load operation
    CALL = auto()    # Function call operation
    FIFO_WRITE = auto()  # FIFO write operation
    FIFO_READ = auto()   # FIFO read operation
    CROSSBAR_ROUTE = auto()  # Crossbar routing operation
    
    # AXI-Stream interface operations
    AXIS_FIFO_WRITE = auto()  # AXI-Stream FIFO write operation
    AXIS_FIFO_READ = auto()   # AXI-Stream FIFO read operation
    
    # AXI-Lite interface operations
    AXILITE_FIFO_WRITE = auto()  # AXI-Lite FIFO write operation
    AXILITE_FIFO_READ = auto()   # AXI-Lite FIFO read operation


class DataType(Enum):
    """Data types supported in the IR."""
    BOOL = auto()
    INT = auto()
    FLOAT = auto()
    ARRAY = auto()
    STRUCT = auto()
    STREAM = auto()  # Streaming interface type


@dataclass
class IRNode:
    """Base class for all IR nodes."""
    name: str
    node_id: int


@dataclass
class IRVariable(IRNode):
    """Variable in the IR."""
    data_type: DataType
    bit_width: int
    is_input: bool = False
    is_output: bool = False
    is_register: bool = False
    is_scratchpad: bool = False  # Flag for variables requiring scratchpad memory
    is_stream: bool = False  # Flag for streaming interfaces
    memory_size: int = 1  # Size in elements (e.g., array length)
    initial_value: Optional[Any] = None
    
    # Streaming interface properties
    stream_direction: Optional[str] = None  # 'in', 'out', or 'inout'
    stream_protocol: Optional[str] = None  # 'simple', 'axis', 'axilite', 'avalon'
    stream_width: Optional[int] = None  # Width of the stream in bits
    
    # FIFO properties (if this variable is implemented as a FIFO)
    fifo_depth: Optional[int] = None
    fifo_threshold_full: Optional[int] = None
    fifo_threshold_empty: Optional[int] = None
    
    # Crossbar properties (if this variable connects through a crossbar)
    crossbar_input_port: Optional[int] = None
    crossbar_output_port: Optional[int] = None
    
    # AXI-Stream specific properties
    axis_has_tuser: bool = False
    axis_tuser_width: Optional[int] = None
    axis_has_tid: bool = False
    axis_tid_width: Optional[int] = None
    axis_has_tdest: bool = False
    axis_tdest_width: Optional[int] = None
    axis_has_tkeep: bool = False
    axis_has_tlast: bool = False
    
    # AXI-Lite specific properties
    axilite_addr_width: Optional[int] = None
    axilite_has_strb: bool = False
    axilite_has_resp: bool = False


@dataclass
class IRConstant(IRNode):
    """Constant value in the IR."""
    data_type: DataType
    value: Any
    bit_width: int
    
    def __hash__(self):
        """Make the constant hashable using its ID."""
        return hash(self.node_id)
    
    def __eq__(self, other):
        """Compare constants by ID."""
        if not isinstance(other, IRConstant):
            return False
        return self.node_id == other.node_id


@dataclass
class IROperation(IRNode):
    """Operation in the IR."""
    op_type: OperationType
    operands: List[Union['IRVariable', 'IRConstant', 'IROperation']]
    result: Optional['IRVariable'] = None
    control_step: int = 0
    
    # Streaming-specific attributes for FIFO and crossbar operations
    fifo_name: Optional[str] = None  # For FIFO_READ/WRITE operations
    crossbar_name: Optional[str] = None  # For XBAR_ROUTE operations
    input_port: Optional[int] = None  # For crossbar routing
    output_port: Optional[int] = None  # For crossbar routing
    
    def __hash__(self):
        """Make the operation hashable using its ID."""
        return hash(self.node_id)
    
    def __eq__(self, other):
        """Compare operations by ID."""
        if not isinstance(other, IROperation):
            return False
        return self.node_id == other.node_id


@dataclass
class IRInstruction(IRNode):
    """Instruction in the IR."""
    operations: List[IROperation] = field(default_factory=list)
    predecessors: List['IRInstruction'] = field(default_factory=list)
    successors: List['IRInstruction'] = field(default_factory=list)


@dataclass
class IRBlock(IRNode):
    """Block of instructions in the IR."""
    instructions: List[IRInstruction] = field(default_factory=list)
    predecessors: List['IRBlock'] = field(default_factory=list)
    successors: List['IRBlock'] = field(default_factory=list)
    loop_header: Optional['IRBlock'] = None
    loop_exit: Optional['IRBlock'] = None
    condition: Optional[IROperation] = None
    
    # Store pragmas associated with this block
    pragmas: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        """Make the block hashable using its ID."""
        return hash(self.node_id)
    
    def __eq__(self, other):
        """Compare blocks by ID."""
        if not isinstance(other, IRBlock):
            return False
        return self.node_id == other.node_id


@dataclass
class StreamingComponent:
    """
    Represents a streaming component in the IR.
    Used to track FIFOs, crossbars, and channels within a function.
    """
    name: str
    component_type: str  # 'fifo', 'crossbar', 'channel'
    params: Dict[str, Any] = field(default_factory=dict)
    source_var: Optional[str] = None  # Variable that feeds this component
    dest_var: Optional[str] = None  # Variable that receives from this component


@dataclass
class IRFunction(IRNode):
    """Function in the IR."""
    parameters: List[IRVariable] = field(default_factory=list)
    return_var: Optional[IRVariable] = None
    blocks: List[IRBlock] = field(default_factory=list)
    entry_block: Optional[IRBlock] = None
    exit_block: Optional[IRBlock] = None
    local_vars: Dict[str, IRVariable] = field(default_factory=dict)
    
    # Performance metrics
    max_control_step: int = 0
    single_iter_latency: int = 0  # Latency of a single iteration without loop multipliers
    total_latency: int = 0  # Total latency including loop iterations
    clock_frequency_mhz: float = 100.0  # Default to 100 MHz
    
    # Loop statistics
    loop_count: int = 0
    loop_iterations: int = 0
    
    # Pipeline configuration
    enable_pipeline: bool = False
    pipeline_depth: int = 1
    
    # Streaming components
    streaming_components: Dict[str, StreamingComponent] = field(default_factory=dict)
    
    # Streaming architecture configuration
    is_streaming_architecture: bool = False
    dataflow_stages: List[str] = field(default_factory=list)  # Names of stages in dataflow pipeline
    
    @property
    def latency_ns(self) -> float:
        """Get the latency in nanoseconds."""
        if self.clock_frequency_mhz <= 0:
            return 0.0
        return (self.total_latency * 1000.0) / self.clock_frequency_mhz
    
    def add_streaming_component(self, component: StreamingComponent):
        """Add a streaming component to the function."""
        self.streaming_components[component.name] = component
        
        # Flag this function as using a streaming architecture
        self.is_streaming_architecture = True


@dataclass
class IR:
    """Top-level IR containing all functions and global variables."""
    functions: Dict[str, IRFunction] = field(default_factory=dict)
    global_vars: Dict[str, IRVariable] = field(default_factory=dict)
    constants: Dict[str, IRConstant] = field(default_factory=dict)
    
    # Hardware-specific information
    target_frequency_mhz: float = 100.0
    resource_constraints: Dict[str, int] = field(default_factory=dict)
    
    # Streaming architecture top-level configuration
    is_streaming_design: bool = False
    top_level_streams: List[str] = field(default_factory=list)  # Top-level streaming interfaces
    
    def get_main_function(self) -> Optional[IRFunction]:
        """Get the main function of the IR."""
        return self.functions.get('main')
    
    def get_function(self, name: str) -> Optional[IRFunction]:
        """Get a function by name."""
        return self.functions.get(name)
    
    def add_function(self, func: IRFunction) -> None:
        """Add a function to the IR."""
        self.functions[func.name] = func
        
        # Check if this function uses streaming architecture
        if func.is_streaming_architecture:
            self.is_streaming_design = True
    
    def add_global_var(self, var: IRVariable) -> None:
        """Add a global variable to the IR."""
        self.global_vars[var.name] = var
        
        # Check if this is a streaming variable
        if var.is_stream:
            self.top_level_streams.append(var.name)
            self.is_streaming_design = True
    
    def add_constant(self, const: IRConstant) -> None:
        """Add a constant to the IR."""
        self.constants[const.name] = const 