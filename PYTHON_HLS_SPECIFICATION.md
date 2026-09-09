# Python-HLS Framework Specification
## Enterprise-Grade Python to Hardware Synthesis

### Version 1.0
### Date: December 2024

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Python Language Features](#supported-python-language-features)
3. [Generated RTL Coding Style Guidelines](#generated-rtl-coding-style-guidelines)
4. [Traceability: Python ↔ RTL Mapping](#traceability-python--rtl-mapping)
5. [Pragma System](#pragma-system)
6. [Memory Architecture](#memory-architecture)
7. [Optimization Framework](#optimization-framework)
8. [Scheduling and Resource Allocation](#scheduling-and-resource-allocation)
9. [Technology Library](#technology-library)
10. [Verification Framework](#verification-framework)
11. [Streaming Architecture Support](#streaming-architecture-support)
12. [Performance Metrics](#performance-metrics)

---

## Overview

The Python-HLS framework is an enterprise-grade high-level synthesis compiler that transforms Python source code into optimized hardware descriptions (Verilog/VHDL). The framework provides comprehensive support for algorithmic Python constructs, advanced optimization techniques, and industry-standard RTL generation.

### Key Features
- **Full Python AST Support**: Comprehensive parsing and analysis of Python constructs
- **Multi-Stage Optimization**: Dead code elimination, constant folding, loop transformations
- **Advanced Scheduling**: ASAP, ALAP, and List scheduling algorithms
- **Resource Management**: Intelligent allocation and binding with technology scaling
- **Streaming Architecture**: FIFO, crossbar, and channel-based dataflow designs
- **RTL Verification**: Automated testbench generation and Verilator-based verification
- **Technology Scaling**: Support for 45nm to 3nm process nodes with realistic scaling models

---

## Supported Python Language Features

### Core Language Constructs

#### 1. Function Definitions
```python
def function_name(param1, param2, ...):
    """Docstrings are preserved for documentation"""
    # Function body
    return result
```

**Supported Features:**
- Function parameters with automatic type inference
- Return statements with single or multiple values
- Local variable declarations
- Nested function calls (with inlining optimization)

**Limitations:**
- No support for `*args` or `**kwargs`
- No support for default parameter values
- No support for lambda functions

#### 2. Data Types

**Primitive Types:**
- `int`: 32-bit signed integers (configurable bit width)
- `bool`: Single-bit boolean values
- `float`: 32-bit floating-point (limited support)

**Composite Types:**
- `list`: Fixed-size arrays with compile-time size determination
- Nested lists: Multi-dimensional arrays with automatic scratchpad allocation

**Type Inference:**
```python
x = 10          # Inferred as 32-bit signed integer
y = True        # Inferred as 1-bit boolean
arr = [0] * 16  # Inferred as 16-element integer array
```

#### 3. Control Flow

**Conditional Statements:**
```python
if condition:
    # if block
elif other_condition:
    # elif block
else:
    # else block
```

**Loop Constructs:**
```python
# For loops with range()
for i in range(start, stop, step):
    # loop body

# While loops
while condition:
    # loop body
```

**Supported Loop Patterns:**
- `range(n)`: 0 to n-1
- `range(start, stop)`: start to stop-1
- `range(start, stop, step)`: start to stop-1 with step increment
- Nested loops with automatic dependency analysis

#### 4. Operators

**Arithmetic Operators:**
- `+`, `-`, `*`, `/`, `%`, `**` (power)
- Automatic bit-width inference and overflow handling

**Bitwise Operators:**
- `&`, `|`, `^` (AND, OR, XOR)
- `<<`, `>>` (left shift, right shift)
- `~` (bitwise NOT)

**Comparison Operators:**
- `==`, `!=`, `<`, `<=`, `>`, `>=`
- Boolean result with 1-bit width

**Logical Operators:**
- `and`, `or`, `not`
- Short-circuit evaluation preserved in hardware

#### 5. Variable Assignment

**Simple Assignment:**
```python
x = expression
```

**Augmented Assignment:**
```python
x += y    # Equivalent to x = x + y
x -= y    # Equivalent to x = x - y
x *= y    # Equivalent to x = x * y
# ... and other compound operators
```

**Array Indexing:**
```python
arr[index] = value
value = arr[index]
```

### Advanced Features

#### 1. Array Operations
```python
# Multi-dimensional arrays
matrix = [[0 for _ in range(cols)] for _ in range(rows)]

# Array access patterns
for i in range(rows):
    for j in range(cols):
        matrix[i][j] = i * cols + j
```

#### 2. Memory Management
- Automatic identification of large arrays for scratchpad memory allocation
- Register vs. memory allocation based on usage patterns
- Configurable memory interfaces (simple, AXI-Stream, AXI-Lite)

---

## Generated RTL Coding Style Guidelines

### Module Structure

#### 1. Module Declaration
```verilog
module function_name (
    input wire clk,
    input wire rst_n,
    input wire signed [31:0] param1,
    input wire signed [31:0] param2,
    output reg signed [31:0] return_val,
    output reg valid,
    output reg done
);
```

**Naming Conventions:**
- Module names match Python function names
- Signal names use snake_case
- Temporary signals prefixed with `temp_`
- State signals prefixed with `state_`

#### 2. Signal Declarations
```verilog
// Internal signals
reg signed [31:0] local_var1;
reg signed [31:0] local_var2;
reg signed [31:0] temp_var_0;
reg signed [31:0] temp_var_1;

// State machine signals
reg [3:0] current_state;
reg [3:0] next_state;

// Control signals
reg valid_internal;
reg done_internal;
```

#### 3. State Machine Implementation
```verilog
// State encoding
parameter IDLE = 4'b0000;
parameter COMPUTE_0 = 4'b0001;
parameter COMPUTE_1 = 4'b0010;
parameter DONE = 4'b1111;

// State register
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        current_state <= IDLE;
    end else begin
        current_state <= next_state;
    end
end

// Next state logic
always @(*) begin
    case (current_state)
        IDLE: begin
            next_state = COMPUTE_0;
        end
        COMPUTE_0: begin
            next_state = COMPUTE_1;
        end
        // ... additional states
        default: begin
            next_state = IDLE;
        end
    endcase
end
```

#### 4. Datapath Implementation
```verilog
// Combinational logic for operations
always @(*) begin
    case (current_state)
        COMPUTE_0: begin
            temp_var_0 = param1 + param2;
        end
        COMPUTE_1: begin
            return_val = temp_var_0 * 2;
        end
        // ... additional computations
    endcase
end

// Sequential logic for registers
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        local_var1 <= 32'b0;
        local_var2 <= 32'b0;
    end else begin
        case (current_state)
            COMPUTE_0: begin
                local_var1 <= temp_var_0;
            end
            // ... additional register updates
        endcase
    end
end
```

### Coding Standards

#### 1. Reset Strategy
- **Asynchronous Reset**: All sequential elements use `negedge rst_n`
- **Reset Values**: All registers initialized to known states
- **Reset Hierarchy**: Consistent reset polarity throughout design

#### 2. Clock Strategy
- **Single Clock Domain**: All logic operates on `clk`
- **Clock Enable**: Used for conditional register updates
- **Clock Gating**: Applied for power optimization when enabled

#### 3. Signal Naming
- **Inputs**: Preserve Python parameter names
- **Outputs**: `return_val` for function return, `valid`/`done` for control
- **Internal**: Descriptive names with type prefixes
- **Temporary**: Numbered temporary variables (`temp_var_0`, `temp_var_1`)

#### 4. Bit Width Management
- **Default Width**: 32-bit signed integers
- **Configurable**: Bit widths inferred from usage and constraints
- **Overflow Handling**: Explicit width declarations prevent overflow

#### 5. Memory Interface
```verilog
// Scratchpad memory interface
output reg [9:0] mem_addr,
output reg [31:0] mem_wdata,
output reg mem_wen,
input wire [31:0] mem_rdata,
output reg mem_ren
```

---

## Traceability: Python ↔ RTL Mapping

### Line-Level Traceability

The framework maintains comprehensive traceability between Python source code and generated RTL through multiple mechanisms:

#### 1. Source Line Preservation
```python
# Python source (line 15)
result = a * b + c

# Generated Verilog (with traceability comments)
// Source: line 15 - result = a * b + c
always @(*) begin
    temp_var_0 = a * b;      // Line 15: multiplication
    result = temp_var_0 + c; // Line 15: addition
end
```

#### 2. IR Node Mapping
Each IR node maintains references to:
- **Source Location**: File, line number, column
- **AST Node**: Original Python AST element
- **Generated RTL**: Corresponding Verilog statements

```python
# IROperation structure includes:
class IROperation:
    source_line: int          # Original Python line
    source_column: int        # Original Python column
    source_text: str          # Original Python text
    generated_rtl: List[str]  # Generated Verilog lines
```

#### 3. Control Flow Mapping
```python
# Python control flow (lines 20-25)
if x > 0:
    y = x * 2
else:
    y = -x

# RTL state machine mapping
// Control flow from lines 20-25
parameter IF_CONDITION = 4'b0001;  // Line 20: if x > 0
parameter IF_BODY = 4'b0010;       // Line 21: y = x * 2
parameter ELSE_BODY = 4'b0011;     // Line 23: y = -x
```

#### 4. Loop Structure Mapping
```python
# Python loop (lines 30-35)
for i in range(N):
    sum_val += arr[i]

# RTL loop implementation
// Loop structure from lines 30-35
parameter LOOP_INIT = 4'b0100;     // Line 30: for i in range(N)
parameter LOOP_BODY = 4'b0101;     // Line 31: sum_val += arr[i]
parameter LOOP_INCREMENT = 4'b0110; // Line 30: i++
parameter LOOP_CHECK = 4'b0111;    // Line 30: i < N
```

### Debugging Support

#### 1. Synthesis Reports
```
=== TRACEABILITY REPORT ===
Python Function: matrix_multiply (line 10)
RTL Module: matrix_multiply

Source Mapping:
  Line 15: result = a * b + c
    → State COMPUTE_0: temp_var_0 = a * b
    → State COMPUTE_1: result = temp_var_0 + c
  
  Line 20-25: if x > 0 ... else ...
    → States IF_CONDITION, IF_BODY, ELSE_BODY
    → Control logic: x_gt_zero = (x > 32'b0)
```

#### 2. Waveform Annotations
Generated testbenches include source line annotations:
```verilog
// Testbench with source annotations
initial begin
    $display("Testing line 15: result = a * b + c");
    a = 32'd5; b = 32'd3; c = 32'd2;
    #10;
    $display("Expected: 17, Actual: %d", result);
end
```

#### 3. Performance Mapping
```
=== PERFORMANCE TRACEABILITY ===
Python Line → RTL Cycles → Latency
  Line 15: result = a * b + c → 2 cycles → 20ns @ 100MHz
  Line 20: if x > 0 → 1 cycle → 10ns @ 100MHz
  Line 30-35: for loop → 10 cycles → 100ns @ 100MHz
```

---

## Pragma System

### Supported Pragmas

#### 1. Memory Type Specification
```python
# pragma hls memory_type RAM
large_array = [0] * 1024

# pragma hls memory_type ROM
lookup_table = [1, 2, 4, 8, 16, 32]

# pragma hls memory_type REGISTER
small_buffer = [0] * 4
```

#### 2. Loop Optimization
```python
# pragma hls unroll factor=4
for i in range(16):
    # Loop body will be unrolled 4x
    
# pragma hls pipeline enable
for i in range(N):
    # Loop will be pipelined
    
# pragma loop_count 100
for i in range(dynamic_limit):
    # Compiler hint for loop iteration count
```

#### 3. Interface Specification
```python
# pragma hls interface s_axilite port=param1
# pragma hls interface s_axilite port=return
def function(param1):
    return param1 * 2
```

#### 4. Streaming Interfaces
```python
# pragma hls fifo input_fifo(depth=32, width=32)
# pragma hls stream input_stream(direction=in, protocol="axis")
def streaming_function():
    # Streaming implementation
```

### Pragma Processing

#### 1. Extraction Phase
- Pragmas extracted from Python comments during parsing
- Validated against supported pragma syntax
- Associated with relevant code constructs (functions, loops, variables)

#### 2. Application Phase
- Memory pragmas influence variable allocation decisions
- Loop pragmas modify scheduling and unrolling behavior
- Interface pragmas affect port generation and protocols

#### 3. Verification Phase
- Pragma consistency checking
- Resource constraint validation
- Performance impact analysis

---

## Memory Architecture

### Memory Hierarchy

#### 1. Register File
- **Usage**: Small variables (≤ 4 elements)
- **Implementation**: Flip-flops in RTL
- **Access**: Single-cycle read/write
- **Area**: Low area overhead

#### 2. Scratchpad Memory
- **Usage**: Large arrays (> 4 elements or > 1KB total)
- **Implementation**: Block RAM or distributed RAM
- **Access**: Multi-cycle with address generation
- **Interfaces**: Simple, AXI-Stream, AXI-Lite

#### 3. Memory Classification Algorithm
```python
def classify_memory_type(variable):
    total_bits = variable.bit_width * variable.memory_size
    
    if total_bits <= 128:  # Small variables
        return "REGISTER"
    elif total_bits <= 8192:  # Medium arrays
        return "DISTRIBUTED_RAM"
    else:  # Large arrays
        return "BLOCK_RAM"
```

### Address Generation Units (AGUs)

#### 1. Linear AGU
```verilog
// Linear address generation
always @(posedge clk) begin
    if (reset) begin
        addr <= 0;
    end else if (enable) begin
        addr <= addr + stride;
    end
end
```

#### 2. Multi-dimensional AGU
```verilog
// 2D array address generation
always @(posedge clk) begin
    if (reset) begin
        row_addr <= 0;
        col_addr <= 0;
    end else if (enable) begin
        if (col_addr == max_col) begin
            col_addr <= 0;
            row_addr <= row_addr + 1;
        end else begin
            col_addr <= col_addr + 1;
        end
    end
end

assign addr = row_addr * row_size + col_addr;
```

### Memory Interfaces

#### 1. Simple Interface
```verilog
// Simple memory interface
output reg [ADDR_WIDTH-1:0] mem_addr,
output reg [DATA_WIDTH-1:0] mem_wdata,
output reg mem_wen,
input wire [DATA_WIDTH-1:0] mem_rdata,
output reg mem_ren
```

#### 2. AXI-Stream Interface
```verilog
// AXI-Stream interface
output reg [DATA_WIDTH-1:0] m_axis_tdata,
output reg m_axis_tvalid,
input wire m_axis_tready,
output reg m_axis_tlast,
output reg [KEEP_WIDTH-1:0] m_axis_tkeep
```

#### 3. AXI-Lite Interface
```verilog
// AXI-Lite interface
output reg [ADDR_WIDTH-1:0] m_axilite_awaddr,
output reg m_axilite_awvalid,
input wire m_axilite_awready,
output reg [DATA_WIDTH-1:0] m_axilite_wdata,
output reg m_axilite_wvalid,
input wire m_axilite_wready
```

---

## Optimization Framework

### Multi-Level Optimization

#### 1. Optimization Levels
- **Level 0**: No optimization (debug builds)
- **Level 1**: Basic optimizations (constant folding, dead code elimination)
- **Level 2**: Medium optimizations (+ CSE, loop invariant motion)
- **Level 3**: Aggressive optimizations (+ inlining, unrolling, resource sharing)

#### 2. Constant Folding
```python
# Before optimization
x = 5 + 3
y = x * 2

# After constant folding
x = 8
y = 16
```

**RTL Impact:**
```verilog
// Before: Multiple operations
temp_0 = 5 + 3;
temp_1 = temp_0 * 2;

// After: Direct assignment
x = 8;
y = 16;
```

#### 3. Dead Code Elimination
```python
# Before optimization
def function(a, b):
    x = a + b      # Used
    y = a - b      # Unused
    z = a * b      # Unused
    return x

# After dead code elimination
def function(a, b):
    x = a + b      # Used
    return x
```

#### 4. Common Subexpression Elimination (CSE)
```python
# Before CSE
result1 = a * b + c
result2 = a * b - c

# After CSE
temp = a * b
result1 = temp + c
result2 = temp - c
```

#### 5. Loop Invariant Code Motion
```python
# Before optimization
for i in range(N):
    constant_calc = a * b  # Invariant
    array[i] = constant_calc + i

# After optimization
constant_calc = a * b      # Moved outside loop
for i in range(N):
    array[i] = constant_calc + i
```

#### 6. Loop Unrolling
```python
# Original loop
# pragma hls unroll factor=4
for i in range(16):
    array[i] = i * 2

# Unrolled loop (factor=4)
for i in range(0, 16, 4):
    array[i] = i * 2
    array[i+1] = (i+1) * 2
    array[i+2] = (i+2) * 2
    array[i+3] = (i+3) * 2
```

### Resource Sharing

#### 1. Arithmetic Resource Sharing
```python
# Multiple multiplications in different states
if state == 0:
    result1 = a * b
elif state == 1:
    result2 = c * d
```

**Shared Implementation:**
```verilog
// Single multiplier shared across states
reg [31:0] mult_a, mult_b, mult_result;

always @(*) begin
    case (state)
        0: begin
            mult_a = a;
            mult_b = b;
        end
        1: begin
            mult_a = c;
            mult_b = d;
        end
    endcase
end

assign mult_result = mult_a * mult_b;
```

#### 2. Memory Resource Sharing
- Multiple arrays mapped to single memory block
- Time-multiplexed access with arbitration
- Address space partitioning

---

## Scheduling and Resource Allocation

### Scheduling Algorithms

#### 1. ASAP (As Soon As Possible)
- **Objective**: Minimize latency
- **Method**: Schedule operations at earliest possible time
- **Use Case**: Performance-critical applications

```
Operation Dependencies:
  A → B → D
  A → C → D

ASAP Schedule:
  Cycle 0: A
  Cycle 1: B, C
  Cycle 2: D
```

#### 2. ALAP (As Late As Possible)
- **Objective**: Minimize resource usage
- **Method**: Schedule operations at latest allowable time
- **Use Case**: Resource-constrained designs

```
ALAP Schedule (with 4-cycle constraint):
  Cycle 0: A
  Cycle 2: B, C
  Cycle 3: D
```

#### 3. List Scheduling
- **Objective**: Balance latency and resources
- **Method**: Priority-based scheduling with resource constraints
- **Use Case**: General-purpose optimization

```
Resource Constraints: 1 Multiplier, 2 Adders
Priority: Critical path length

List Schedule:
  Cycle 0: A (mult)
  Cycle 1: B (add), C (add)
  Cycle 2: D (mult)
```

### Resource Allocation

#### 1. Allocation Strategies

**Area Optimization:**
```python
# Minimize total area
allocated_resources = {
    "Adder_32bit": 1,      # Shared across operations
    "Multiplier_32bit": 1,  # Shared across operations
    "Register_32bit": 8     # Minimum required
}
```

**Performance Optimization:**
```python
# Maximize throughput
allocated_resources = {
    "Adder_32bit": 4,      # Parallel execution
    "Multiplier_32bit": 2,  # Parallel execution
    "Register_32bit": 16    # Reduce register pressure
}
```

**Power Optimization:**
```python
# Minimize power consumption
allocated_resources = {
    "Adder_32bit": 1,      # Minimal resources
    "Multiplier_32bit": 0,  # Use shift-add instead
    "Register_32bit": 6     # Clock gating opportunities
}
```

#### 2. Resource Binding

**Temporal Binding:**
```verilog
// Same resource used in different time slots
always @(posedge clk) begin
    case (state)
        STATE_0: alu_result <= a + b;  // Addition
        STATE_1: alu_result <= c - d;  // Subtraction
        STATE_2: alu_result <= e & f;  // Bitwise AND
    endcase
end
```

**Spatial Binding:**
```verilog
// Multiple resources for parallel execution
assign result1 = alu1_a + alu1_b;  // ALU 1
assign result2 = alu2_a + alu2_b;  // ALU 2
```

### Data Flow Graph (DFG) Analysis

#### 1. DFG Construction
```python
# Python code
c = a + b
d = a - b
e = c * d

# DFG representation
nodes = {
    "add": {"inputs": ["a", "b"], "output": "c"},
    "sub": {"inputs": ["a", "b"], "output": "d"}, 
    "mul": {"inputs": ["c", "d"], "output": "e"}
}

edges = [
    ("add", "mul"),  # c flows from add to mul
    ("sub", "mul")   # d flows from sub to mul
]
```

#### 2. Critical Path Analysis
```
Critical Path: add → mul (2 cycles)
Non-critical: sub (1 cycle, can be delayed)

Scheduling flexibility:
  add: ASAP=0, ALAP=0 (critical)
  sub: ASAP=0, ALAP=1 (flexible)
  mul: ASAP=1, ALAP=1 (critical)
```

---

## Technology Library

### Technology Node Support

#### 1. Supported Nodes
- **45nm**: Legacy node with conservative scaling
- **28nm**: Mainstream node with good area-power balance
- **16nm**: Advanced node with FinFET technology
- **7nm**: Leading-edge node with aggressive scaling
- **3nm**: Cutting-edge node with limited scaling benefits

#### 2. Resource Models

**Basic Resources:**
```python
# 45nm baseline models
resources_45nm = {
    "Register_32bit": {
        "area": 32.0,        # μm²
        "latency": 1,        # cycles
        "energy": 0.32,      # pJ/operation
        "leakage": 3.2,      # μW
        "frequency": 1000    # MHz
    },
    "Adder_32bit": {
        "area": 180.0,       # μm²
        "latency": 1,        # cycles
        "energy": 2.5,       # pJ/operation
        "leakage": 15.0,     # μW
        "frequency": 1000    # MHz
    },
    "Multiplier_32bit": {
        "area": 2400.0,      # μm²
        "latency": 2,        # cycles
        "energy": 45.0,      # pJ/operation
        "leakage": 180.0,    # μW
        "frequency": 800     # MHz
    }
}
```

#### 3. Scaling Models

**Realistic Scaling Laws:**
```python
def scale_resource(resource, target_node):
    node_ratio = target_node / resource.tech_node
    
    # Area scaling (diminishing returns)
    if target_node <= 7:
        area_exp = 1.25      # Limited scaling at advanced nodes
    elif target_node <= 16:
        area_exp = 1.50      # Moderate scaling
    else:
        area_exp = 1.85      # Near-classical scaling
    
    area_scale = node_ratio ** area_exp
    
    # Energy scaling (voltage scaling limitations)
    if target_node <= 7:
        energy_scale = node_ratio ** 0.8
    else:
        energy_scale = node_ratio ** 1.0
    
    # Frequency scaling (limited by interconnect)
    freq_scale = (resource.tech_node / target_node) ** 0.3
    
    return ScaledResource(
        area=resource.area * area_scale,
        energy=resource.energy * energy_scale,
        frequency=resource.frequency * freq_scale
    )
```

#### 4. Memory Models

**Memory Hierarchy:**
```python
memory_models = {
    "Register_File": {
        "access_time": 1,    # cycles
        "area_per_bit": 1.0, # μm²/bit
        "energy_per_access": 0.01  # pJ
    },
    "Distributed_RAM": {
        "access_time": 1,    # cycles
        "area_per_bit": 0.5, # μm²/bit
        "energy_per_access": 0.1   # pJ
    },
    "Block_RAM": {
        "access_time": 2,    # cycles
        "area_per_bit": 0.1, # μm²/bit
        "energy_per_access": 1.0   # pJ
    }
}
```

---

## Verification Framework

### RTL Verification Methodology

#### 1. Verification Flow
```
Python Source → HLS Compilation → Verilog RTL
     ↓                               ↓
Python Execution ← Comparison → RTL Simulation
     ↓                               ↓
Reference Results              RTL Results
     ↓                               ↓
     └─────── Verification ──────────┘
```

#### 2. Test Vector Generation

**Random Test Generation:**
```python
def generate_random_tests(func_signature, num_tests=100):
    test_vectors = []
    for _ in range(num_tests):
        inputs = {}
        for param, param_type in func_signature.items():
            if param_type == "int":
                inputs[param] = random.randint(-1000, 1000)
            elif param_type == "array":
                inputs[param] = [random.randint(-100, 100) 
                               for _ in range(array_size)]
        test_vectors.append(inputs)
    return test_vectors
```

**Edge Case Generation:**
```python
def generate_edge_cases(func_signature):
    edge_cases = []
    # Zero values
    edge_cases.append({param: 0 for param in func_signature})
    # Maximum values
    edge_cases.append({param: 2**31-1 for param in func_signature})
    # Minimum values
    edge_cases.append({param: -2**31 for param in func_signature})
    return edge_cases
```

#### 3. Testbench Generation

**Verilog Testbench Template:**
```verilog
module tb_function_name;
    // Clock and reset
    reg clk = 0;
    reg rst_n = 1;
    
    // DUT interface
    reg signed [31:0] param1;
    reg signed [31:0] param2;
    wire signed [31:0] return_val;
    wire valid;
    wire done;
    
    // DUT instantiation
    function_name dut (
        .clk(clk),
        .rst_n(rst_n),
        .param1(param1),
        .param2(param2),
        .return_val(return_val),
        .valid(valid),
        .done(done)
    );
    
    // Clock generation
    always #5 clk = ~clk;
    
    // Test execution
    initial begin
        // Test vector application
        rst_n = 0; #10; rst_n = 1; #10;
        
        // Test case 1
        param1 = 32'd5;
        param2 = 32'd3;
        wait(done);
        $display("Test 1: Expected=%d, Actual=%d", 
                 expected_result, return_val);
        
        // Additional test cases...
        $finish;
    end
endmodule
```

#### 4. Result Comparison

**Bit-Accurate Comparison:**
```python
def compare_results(python_result, rtl_result, tolerance=0):
    if isinstance(python_result, (int, bool)):
        return abs(python_result - rtl_result) <= tolerance
    elif isinstance(python_result, list):
        if len(python_result) != len(rtl_result):
            return False
        return all(abs(p - r) <= tolerance 
                  for p, r in zip(python_result, rtl_result))
    return False
```

#### 5. Coverage Analysis

**Functional Coverage:**
```python
coverage_metrics = {
    "statement_coverage": 95.2,    # % of RTL statements exercised
    "branch_coverage": 88.7,       # % of branches taken
    "toggle_coverage": 92.1,       # % of signals toggled
    "path_coverage": 76.3          # % of execution paths covered
}
```

---

## Streaming Architecture Support

### Streaming Components

#### 1. FIFO Interfaces

**Simple FIFO:**
```python
# pragma hls fifo data_fifo(depth=32, width=32)
def producer_consumer():
    # Producer writes to FIFO
    data_fifo.write(data)  # pragma hls fifo_write data_fifo
    
    # Consumer reads from FIFO
    result = data_fifo.read()  # pragma hls fifo_read data_fifo
```

**Generated RTL:**
```verilog
// FIFO interface signals
output reg [31:0] fifo_din,
output reg fifo_wr_en,
input wire fifo_full,
input wire [31:0] fifo_dout,
output reg fifo_rd_en,
input wire fifo_empty
```

#### 2. AXI-Stream Interface

**AXI-Stream FIFO:**
```python
# pragma hls fifo axis_fifo(depth=32, width=32, 
#                          input_interface="axis", 
#                          output_interface="axis",
#                          axis_tlast=True, axis_tkeep=True)
def streaming_processor():
    # Stream processing with AXI-Stream protocol
    pass
```

**Generated AXI-Stream Interface:**
```verilog
// AXI-Stream Master
output reg [31:0] m_axis_tdata,
output reg m_axis_tvalid,
input wire m_axis_tready,
output reg m_axis_tlast,
output reg [3:0] m_axis_tkeep,

// AXI-Stream Slave
input wire [31:0] s_axis_tdata,
input wire s_axis_tvalid,
output reg s_axis_tready,
input wire s_axis_tlast,
input wire [3:0] s_axis_tkeep
```

#### 3. Crossbar Networks

**Crossbar Declaration:**
```python
# pragma hls crossbar data_xbar(inputs=4, outputs=4, width=32)
def crossbar_routing():
    # Multi-input, multi-output routing
    pass
```

**Generated Crossbar RTL:**
```verilog
// Crossbar input ports
input wire [31:0] xbar_din_0,
input wire [31:0] xbar_din_1,
input wire [31:0] xbar_din_2,
input wire [31:0] xbar_din_3,

// Crossbar output ports  
output reg [31:0] xbar_dout_0,
output reg [31:0] xbar_dout_1,
output reg [31:0] xbar_dout_2,
output reg [31:0] xbar_dout_3,

// Routing control
input wire [1:0] route_sel_0,
input wire [1:0] route_sel_1,
input wire [1:0] route_sel_2,
input wire [1:0] route_sel_3
```

### Dataflow Architecture

#### 1. Pipeline Stages
```python
# Dataflow pipeline with explicit stages
def dataflow_pipeline():
    # Stage 1: Input processing
    # pragma hls channel stage1_to_stage2
    stage1_output = input_processing(input_data)
    
    # Stage 2: Computation
    # pragma hls channel stage2_to_stage3  
    stage2_output = computation(stage1_output)
    
    # Stage 3: Output formatting
    final_output = output_formatting(stage2_output)
    
    return final_output
```

#### 2. Generated Pipeline RTL
```verilog
// Pipeline stage registers
reg [31:0] stage1_reg;
reg [31:0] stage2_reg;
reg stage1_valid, stage2_valid;

// Pipeline advancement
always @(posedge clk) begin
    if (!rst_n) begin
        stage1_valid <= 0;
        stage2_valid <= 0;
    end else begin
        // Stage advancement with backpressure
        if (downstream_ready) begin
            stage2_reg <= stage1_reg;
            stage2_valid <= stage1_valid;
            stage1_reg <= input_data;
            stage1_valid <= input_valid;
        end
    end
end
```

---

## Performance Metrics

### Timing Analysis

#### 1. Latency Calculation
```python
def calculate_latency(ir_function):
    base_latency = ir_function.max_control_step
    
    # Account for loop iterations
    loop_latency = 0
    for block in ir_function.blocks:
        if block.loop_header == block:
            iterations = estimate_loop_iterations(block)
            body_latency = calculate_loop_body_latency(block)
            loop_latency += iterations * body_latency
    
    total_latency = base_latency + loop_latency
    return total_latency
```

#### 2. Throughput Analysis
```python
def calculate_throughput(ir_function, clock_freq_mhz):
    latency_cycles = calculate_latency(ir_function)
    latency_ns = (latency_cycles * 1000) / clock_freq_mhz
    throughput_ops_per_sec = 1e9 / latency_ns
    return throughput_ops_per_sec
```

### Area Analysis

#### 1. Resource Area Calculation
```python
def calculate_area(allocated_resources, tech_library):
    total_area = 0
    for resource_type, count in allocated_resources.items():
        resource_model = tech_library.get_resource(resource_type)
        total_area += count * resource_model.area
    return total_area
```

#### 2. Memory Area Calculation
```python
def calculate_memory_area(ir_function, tech_library):
    memory_area = 0
    for var_name, var in ir_function.local_vars.items():
        if var.is_scratchpad:
            bits = var.bit_width * var.memory_size
            if bits > 8192:  # Block RAM
                memory_area += bits * 0.1  # μm²/bit
            else:  # Distributed RAM
                memory_area += bits * 0.5  # μm²/bit
    return memory_area
```

### Power Analysis

#### 1. Dynamic Power
```python
def calculate_dynamic_power(allocated_resources, tech_library, 
                          activity_factor=0.1):
    dynamic_power = 0
    for resource_type, count in allocated_resources.items():
        resource_model = tech_library.get_resource(resource_type)
        ops_per_sec = calculate_operations_per_second(resource_type)
        power = count * resource_model.energy_per_op * ops_per_sec * 1e-12
        dynamic_power += power * activity_factor
    return dynamic_power  # Watts
```

#### 2. Static Power  
```python
def calculate_static_power(allocated_resources, tech_library):
    static_power = 0
    for resource_type, count in allocated_resources.items():
        resource_model = tech_library.get_resource(resource_type)
        static_power += count * resource_model.leakage_power * 1e-6
    return static_power  # Watts
```

### Quality Metrics

#### 1. Resource Utilization
```python
def calculate_resource_utilization(scheduled_ir):
    total_slots = 0
    used_slots = 0
    
    for func in scheduled_ir.functions.values():
        for block in func.blocks:
            for instruction in block.instructions:
                total_slots += func.max_control_step
                used_slots += len(instruction.operations)
    
    utilization = used_slots / total_slots if total_slots > 0 else 0
    return utilization * 100  # Percentage
```

#### 2. Critical Path Analysis
```python
def find_critical_path(dfg, tech_library):
    # Find longest path through the dataflow graph
    longest_path = 0
    longest_path_delay = 0
    
    for path in nx.all_simple_paths(dfg, source_nodes, sink_nodes):
        path_delay = 0
        for node in path:
            operation = dfg.nodes[node]['op']
            delay = get_operation_delay(operation, tech_library)
            path_delay += delay
        
        if path_delay > longest_path_delay:
            longest_path_delay = path_delay
            longest_path = path
    
    return longest_path, longest_path_delay
```

### Reporting

#### 1. Performance Summary
```
=== PERFORMANCE SUMMARY ===
Function: matrix_multiply
Technology Node: 28nm

Timing:
  Latency: 156 cycles (1.56 μs @ 100MHz)
  Throughput: 641,026 operations/second
  Critical Path: 8.2 ns

Area:
  Logic Area: 15,420 μm²
  Memory Area: 8,192 μm²
  Total Area: 23,612 μm²

Power:
  Dynamic Power: 12.5 mW
  Static Power: 3.2 mW
  Total Power: 15.7 mW

Resources:
  ALU_32bit: 2
  Multiplier_32bit: 1
  Register_32bit: 16
  Memory_1KB: 8
  MUX_32bit: 4

Quality:
  Resource Utilization: 78.3%
  Memory Efficiency: 92.1%
  Critical Path Slack: 1.8 ns
```

#### 2. Optimization Opportunities
```
=== OPTIMIZATION OPPORTUNITIES ===
1. Loop Unrolling: 
   - Target: Line 25-30 (inner loop)
   - Benefit: 2.3x speedup, 1.8x area increase
   
2. Resource Sharing:
   - Target: Multipliers in different states
   - Benefit: 15% area reduction, 5% latency increase
   
3. Memory Banking:
   - Target: Large array accesses
   - Benefit: 1.6x throughput improvement
```

---

## Conclusion

The Python-HLS framework provides enterprise-grade synthesis capabilities with comprehensive language support, advanced optimization techniques, and detailed traceability. The framework enables designers to leverage Python's expressiveness while generating efficient, high-quality RTL implementations suitable for FPGA and ASIC targets.

### Key Differentiators
- **Complete Traceability**: Line-by-line mapping between Python and RTL
- **Realistic Technology Models**: Industry-accurate scaling and power models
- **Advanced Optimization**: Multi-level optimization with measurable benefits
- **Streaming Architecture**: Native support for dataflow and streaming designs
- **Verification Integration**: Automated RTL verification with comprehensive coverage

### Enterprise Readiness
- **Scalable Architecture**: Supports designs from simple functions to complex systems
- **Industry Standards**: Generates industry-standard RTL coding styles
- **Comprehensive Documentation**: Detailed specifications and traceability reports
- **Quality Assurance**: Extensive verification and validation framework

---

*This specification document provides comprehensive coverage of the Python-HLS framework capabilities, serving as both a user guide and technical reference for enterprise deployment.* 