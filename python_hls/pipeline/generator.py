"""
Synthesizable Verilog Generator for Constraint-Driven Hardware Pipelines.

Supports:
- Initiation interval (II >= 1) targets with cycle-accurate pacing
- Downstream backpressure stalls with zero dropped or duplicated transactions
- Bubble propagation without spurious output assertion
- Drain semantics and pipeline empty/busy status flags
- Standard interfaces: AXI4-Stream (axis), Ready-Valid (ready_valid), and Decoupled Memory (memory)
"""

import ast
import inspect
import textwrap
from typing import Dict, List, Optional, Union, Callable, Any, Tuple

from .spec import PipelineSpec, PipelineInterfaceType, get_pipeline_spec


class ASTExpressionToVerilog(ast.NodeVisitor):
    """Translate Python AST arithmetic expressions into Verilog expressions."""

    OP_MAP = {
        ast.Add: "+",
        ast.Sub: "-",
        ast.Mult: "*",
        ast.Div: "/",
        ast.FloorDiv: "/",
        ast.Mod: "%",
        ast.BitAnd: "&",
        ast.BitOr: "|",
        ast.BitXor: "^",
        ast.LShift: "<<",
        ast.RShift: ">>",
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
    }

    def __init__(self, var_renames: Optional[Dict[str, str]] = None):
        self.var_renames = var_renames or {}

    def visit_BinOp(self, node: ast.BinOp) -> str:
        left = self.visit(node.left)
        op = self.OP_MAP.get(type(node.op), "+")
        right = self.visit(node.right)
        return f"({left} {op} {right})"

    def visit_UnaryOp(self, node: ast.UnaryOp) -> str:
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.USub):
            return f"(-{operand})"
        elif isinstance(node.op, ast.Invert):
            return f"(~{operand})"
        elif isinstance(node.op, ast.Not):
            return f"(!{operand})"
        return operand

    def visit_Compare(self, node: ast.Compare) -> str:
        left = self.visit(node.left)
        comparisons = []
        curr_left = left
        for op, comparator in zip(node.ops, node.comparators):
            op_str = self.OP_MAP.get(type(op), "==")
            right = self.visit(comparator)
            comparisons.append(f"({curr_left} {op_str} {right})")
            curr_left = right
        return " && ".join(comparisons)

    def visit_Name(self, node: ast.Name) -> str:
        return self.var_renames.get(node.id, node.id)

    def visit_Constant(self, node: ast.Constant) -> str:
        if isinstance(node.value, bool):
            return "1'b1" if node.value else "1'b0"
        elif isinstance(node.value, int):
            return f"{node.value}"
        return str(node.value)

    def generic_visit(self, node: ast.AST) -> str:
        raise ValueError(f"Unsupported AST node in pipeline expression: {type(node).__name__}")


class PipelineVerilogGenerator:
    """
    Synthesizable Verilog Generator for cycle-accounted hardware pipeline lanes.
    """

    def __init__(self, spec: Optional[PipelineSpec] = None):
        self.spec = spec or PipelineSpec()

    def generate_from_function(self, func: Callable, spec: Optional[PipelineSpec] = None) -> str:
        """Generate pipeline Verilog from a Python callable."""
        try:
            source = inspect.getsource(func)
            dedented_source = textwrap.dedent(source)
        except (OSError, TypeError):
            source = getattr(func, "__source__", None)
            if not source:
                # If inspect fails and no __source__, attempt to disassemble / reconstruct simple return
                raise ValueError(
                    f"Could not inspect source code for {getattr(func, '__name__', str(func))}. "
                    "Define function in a file or provide source string directly to generate_from_source()."
                )
            dedented_source = textwrap.dedent(source)

        fn_spec = spec or getattr(func, "_hls_pipeline_spec", None) or get_pipeline_spec(func.__name__) or self.spec
        return self.generate_from_source(dedented_source, func.__name__, fn_spec)

    def generate_from_source(self, source: str, function_name: Optional[str] = None,
                             spec: Optional[PipelineSpec] = None) -> str:
        """Generate pipeline Verilog from Python source code string."""
        tree = ast.parse(source)
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if function_name is None or node.name == function_name:
                    func_def = node
                    break

        if func_def is None:
            raise ValueError(f"Function {function_name or ''} not found in provided source")

        active_spec = spec or self.spec
        return self._generate_module(func_def, active_spec)

    def _generate_module(self, func_def: ast.FunctionDef, spec: PipelineSpec) -> str:
        """Internal worker to construct synthesizable Verilog code."""
        module_name = func_def.name
        arg_names = [arg.arg for arg in func_def.args.args]
        data_width = spec.data_width
        addr_width = spec.addr_width
        depth = max(1, spec.depth)
        ii = max(1, spec.ii)
        iface = spec.interface
        if isinstance(iface, str):
            iface = PipelineInterfaceType(iface.lower())

        # Extract statements and return expression
        statements, return_expr = self._extract_logic(func_def)

        # Plan stage operations
        stage_operations = self._partition_operations(statements, return_expr, arg_names, depth)

        lines: List[str] = []
        lines.append("// ==============================================================================")
        lines.append(f"// Module: {module_name}")
        lines.append("// Synthesized by Python-HLS Constraint-Driven Pipeline Backend")
        lines.append(f"// Interface: {iface.value.upper()}")
        lines.append(f"// Initiation Interval (II): {ii} cycle(s)")
        lines.append(f"// Latency / Pipeline Depth: {depth} cycle(s)")
        lines.append(f"// Data Width: {data_width}-bit, Address Width: {addr_width}-bit")
        lines.append("// Architecture: Single-clock domain accelerator lane with backpressure stalls,")
        lines.append("//               bubble propagation, and in-flight transaction draining.")
        lines.append("// ==============================================================================")
        lines.append("`timescale 1ns / 1ps")
        lines.append("/* verilator lint_off UNUSEDPARAM */")
        lines.append("/* verilator lint_off UNUSEDSIGNAL */")
        lines.append("/* verilator lint_off WIDTHTRUNC */")
        lines.append("")
        lines.append(f"module {module_name} #(")
        lines.append(f"    parameter DATA_WIDTH = {data_width},")
        if iface == PipelineInterfaceType.MEMORY:
            lines.append(f"    parameter ADDR_WIDTH = {addr_width},")
            lines.append("    parameter MEM_DEPTH = 64,")
        lines.append(f"    parameter PIPELINE_DEPTH = {depth},")
        lines.append(f"    parameter II = {ii}")
        lines.append(") (")
        lines.append("    // Clock and active-low asynchronous reset")
        lines.append("    input  wire                   clk,")
        lines.append("    input  wire                   rst_n,")
        lines.append("")

        # Ports based on interface type
        if iface == PipelineInterfaceType.AXIS:
            lines.extend(self._generate_axis_ports(arg_names))
        elif iface == PipelineInterfaceType.READY_VALID:
            lines.extend(self._generate_ready_valid_ports(arg_names))
        elif iface == PipelineInterfaceType.MEMORY:
            lines.extend(self._generate_memory_ports())

        lines.append(");")
        lines.append("")

        # Logic implementation
        lines.extend(self._generate_pipeline_body(arg_names, stage_operations, spec, iface))

        lines.append(f"endmodule // {module_name}")
        lines.append("")
        return "\n".join(lines)

    def _generate_axis_ports(self, arg_names: List[str]) -> List[str]:
        p: List[str] = []
        p.append("    // AXI4-Stream Slave Interface (Input)")
        if len(arg_names) <= 1:
            p.append("    input  wire [DATA_WIDTH-1:0]   s_axis_tdata,")
        else:
            total_w = len(arg_names)
            p.append(f"    input  wire [DATA_WIDTH*{total_w}-1:0] s_axis_tdata,")
            for i, name in enumerate(arg_names):
                p.append(f"    // Note: arg '{name}' is mapped to s_axis_tdata[{i+1}*DATA_WIDTH-1:{i}*DATA_WIDTH]")
        p.append("    input  wire                   s_axis_tvalid,")
        p.append("    output wire                   s_axis_tready,")
        p.append("    input  wire                   s_axis_tlast,")
        p.append("")
        p.append("    // AXI4-Stream Master Interface (Output)")
        p.append("    output wire [DATA_WIDTH-1:0]   m_axis_tdata,")
        p.append("    output wire                   m_axis_tvalid,")
        p.append("    input  wire                   m_axis_tready,")
        p.append("    output wire                   m_axis_tlast,")
        p.append("")
        p.append("    // Pipeline Status Indicators")
        p.append("    output wire                   pipeline_empty,")
        p.append("    output wire                   pipeline_busy")
        return p

    def _generate_ready_valid_ports(self, arg_names: List[str]) -> List[str]:
        p: List[str] = []
        p.append("    // Ready-Valid Decoupled Streaming Interface (Input)")
        if len(arg_names) <= 1:
            p.append("    input  wire [DATA_WIDTH-1:0]   in_data,")
        else:
            total_w = len(arg_names)
            p.append(f"    input  wire [DATA_WIDTH*{total_w}-1:0] in_data,")
        p.append("    input  wire                   in_valid,")
        p.append("    output wire                   in_ready,")
        p.append("")
        p.append("    // Ready-Valid Decoupled Streaming Interface (Output)")
        p.append("    output wire [DATA_WIDTH-1:0]   out_data,")
        p.append("    output wire                   out_valid,")
        p.append("    input  wire                   out_ready,")
        p.append("")
        p.append("    // Pipeline Status Indicators")
        p.append("    output wire                   pipeline_empty,")
        p.append("    output wire                   pipeline_busy")
        return p

    def _generate_memory_ports(self) -> List[str]:
        p: List[str] = []
        p.append("    // Decoupled Memory Request Channel (Input)")
        p.append("    input  wire                   mem_req,")
        p.append("    output wire                   mem_ready,")
        p.append("    input  wire                   mem_we,")
        p.append("    input  wire [ADDR_WIDTH-1:0]   mem_addr,")
        p.append("    input  wire [DATA_WIDTH-1:0]   mem_wdata,")
        p.append("")
        p.append("    // Decoupled Memory Response Channel (Output)")
        p.append("    output wire [DATA_WIDTH-1:0]   mem_rdata,")
        p.append("    output wire                   mem_rvalid,")
        p.append("    input  wire                   mem_resp_ready,")
        p.append("")
        p.append("    // Pipeline Status Indicators")
        p.append("    output wire                   pipeline_empty,")
        p.append("    output wire                   pipeline_busy")
        return p

    def _extract_logic(self, func_def: ast.FunctionDef) -> Tuple[List[ast.stmt], Optional[ast.expr]]:
        statements: List[ast.stmt] = []
        return_expr: Optional[ast.expr] = None
        for stmt in func_def.body:
            if isinstance(stmt, ast.Return):
                return_expr = stmt.value
            else:
                statements.append(stmt)
        return statements, return_expr

    def _partition_operations(self, statements: List[ast.stmt], return_expr: Optional[ast.expr],
                              arg_names: List[str], depth: int) -> List[Dict[str, Any]]:
        """Partition logic across pipeline stages and pipeline operands."""
        stages = [{"index": i, "computations": [], "outputs": []} for i in range(depth)]

        # If statements exist, map them
        if statements:
            for idx, stmt in enumerate(statements):
                stage_idx = min(idx, depth - 1)
                if isinstance(stmt, ast.Assign):
                    target_name = stmt.targets[0].id if isinstance(stmt.targets[0], ast.Name) else f"var_{idx}"
                    expr_str = ASTExpressionToVerilog().visit(stmt.value)
                    stages[stage_idx]["computations"].append((target_name, expr_str))
                    stages[stage_idx]["outputs"].append(target_name)

        # Handle return expression
        if return_expr is not None:
            expr_str = ASTExpressionToVerilog().visit(return_expr)
            if depth == 1:
                stages[0]["computations"].append(("result", expr_str))
                stages[0]["outputs"].append("result")
            else:
                if isinstance(return_expr, ast.BinOp) and not statements:
                    left_str = ASTExpressionToVerilog().visit(return_expr.left)
                    right_str = ASTExpressionToVerilog().visit(return_expr.right)
                    op_str = ASTExpressionToVerilog.OP_MAP.get(type(return_expr.op), "+")
                    
                    stages[0]["computations"].append(("stage_0_sub", left_str))
                    stages[0]["outputs"].append("stage_0_sub")
                    
                    if depth == 2:
                        stages[1]["computations"].append(("result", f"(stage_0_sub {op_str} {right_str})"))
                        stages[1]["outputs"].append("result")
                    else:
                        for s in range(1, depth - 1):
                            prev_sym = "stage_0_sub" if s == 1 else f"stage_{s-1}_pass"
                            stages[s]["computations"].append((f"stage_{s}_pass", prev_sym))
                            stages[s]["outputs"].append(f"stage_{s}_pass")
                        stages[depth - 1]["computations"].append(("result", f"(stage_{depth-2}_pass {op_str} {right_str})"))
                        stages[depth - 1]["outputs"].append("result")
                else:
                    last_stage = depth - 1
                    stages[last_stage]["computations"].append(("result", expr_str))
                    stages[last_stage]["outputs"].append("result")

        # Automatically pipeline any argument used in stage s >= 1
        import re
        for s in range(1, depth):
            new_computations = []
            for target, expr in stages[s]["computations"]:
                updated_expr = expr
                for arg in arg_names:
                    # Check if arg is referenced in expr as a standalone word
                    if re.search(rf'\b{arg}\b', expr):
                        # Ensure stage 0 samples it
                        if f"{arg}_pipe_0" not in stages[0]["outputs"]:
                            stages[0]["computations"].append((f"{arg}_pipe_0", arg))
                            stages[0]["outputs"].append(f"{arg}_pipe_0")
                        # Pass through intermediate stages
                        for k in range(1, s):
                            pipe_prev = f"{arg}_pipe_{k-1}"
                            pipe_curr = f"{arg}_pipe_{k}"
                            if pipe_curr not in stages[k]["outputs"]:
                                stages[k]["computations"].append((pipe_curr, pipe_prev))
                                stages[k]["outputs"].append(pipe_curr)
                        # Replace in stage s expr
                        needed_pipe = f"{arg}_pipe_{s-1}"
                        updated_expr = re.sub(rf'\b{arg}\b', needed_pipe, updated_expr)
                new_computations.append((target, updated_expr))
            stages[s]["computations"] = new_computations

        return stages

    def _generate_pipeline_body(self, arg_names: List[str], stage_operations: List[Dict[str, Any]],
                                spec: PipelineSpec, iface: PipelineInterfaceType) -> List[str]:
        lines: List[str] = []
        depth = spec.depth
        ii = spec.ii

        # Unified interface aliasing
        lines.append("    // -------------------------------------------------------------------------")
        lines.append("    // Interface Signal Aliasing & Unpacking")
        lines.append("    // -------------------------------------------------------------------------")
        if iface == PipelineInterfaceType.AXIS:
            lines.append("    wire                   lane_in_valid  = s_axis_tvalid;")
            lines.append("    wire                   lane_out_ready = m_axis_tready;")
            lines.append("    wire                   lane_in_last   = s_axis_tlast;")
            lines.append("    assign s_axis_tready = lane_in_ready;")
            lines.append("    assign m_axis_tvalid = stage_valid[PIPELINE_DEPTH-1];")
            lines.append("    assign m_axis_tdata  = stage_data[PIPELINE_DEPTH-1];")
            lines.append("    assign m_axis_tlast  = stage_last[PIPELINE_DEPTH-1];")
            # Unpack args
            for i, name in enumerate(arg_names):
                if len(arg_names) == 1:
                    lines.append(f"    wire [DATA_WIDTH-1:0] in_{name} = s_axis_tdata;")
                else:
                    lines.append(f"    wire [DATA_WIDTH-1:0] in_{name} = s_axis_tdata[{i+1}*DATA_WIDTH-1:{i}*DATA_WIDTH];")

        elif iface == PipelineInterfaceType.READY_VALID:
            lines.append("    wire                   lane_in_valid  = in_valid;")
            lines.append("    wire                   lane_out_ready = out_ready;")
            lines.append("    wire                   lane_in_last   = 1'b0;")
            lines.append("    assign in_ready      = lane_in_ready;")
            lines.append("    assign out_valid     = stage_valid[PIPELINE_DEPTH-1];")
            lines.append("    assign out_data      = stage_data[PIPELINE_DEPTH-1];")
            # Unpack args
            for i, name in enumerate(arg_names):
                if len(arg_names) == 1:
                    lines.append(f"    wire [DATA_WIDTH-1:0] in_{name} = in_data;")
                else:
                    lines.append(f"    wire [DATA_WIDTH-1:0] in_{name} = in_data[{i+1}*DATA_WIDTH-1:{i}*DATA_WIDTH];")

        elif iface == PipelineInterfaceType.MEMORY:
            lines.append("    wire                   lane_in_valid  = mem_req;")
            lines.append("    wire                   lane_out_ready = mem_resp_ready;")
            lines.append("    wire                   lane_in_last   = 1'b0;")
            lines.append("    assign mem_ready     = lane_in_ready;")
            lines.append("    assign mem_rvalid    = stage_valid[PIPELINE_DEPTH-1] && !stage_mem_we[PIPELINE_DEPTH-1];")
            lines.append("    assign mem_rdata     = stage_data[PIPELINE_DEPTH-1];")
            # Unpack args
            for i, name in enumerate(arg_names):
                if name in ("addr", "address", "mem_addr"):
                    lines.append(f"    wire [ADDR_WIDTH-1:0] in_{name} = mem_addr;")
                else:
                    lines.append(f"    wire [DATA_WIDTH-1:0] in_{name} = mem_wdata;")
            if not arg_names:
                lines.append("    wire [ADDR_WIDTH-1:0] in_addr = mem_addr;")
                lines.append("    wire [DATA_WIDTH-1:0] in_wdata = mem_wdata;")

        lines.append("")
        lines.append("    // -------------------------------------------------------------------------")
        lines.append("    // Flow Control: Stalls, Bubbles, and Advance Logic")
        lines.append("    // -------------------------------------------------------------------------")
        lines.append("    // Downstream backpressure stall: output valid and downstream not ready")
        lines.append("    wire pipe_stall = stage_valid[PIPELINE_DEPTH-1] && !lane_out_ready;")
        lines.append("    wire pipe_advance = !pipe_stall;")
        lines.append("")

        # II counter logic
        if ii > 1:
            lines.append(f"    // Initiation Interval (II={ii}) Counter")
            lines.append(f"    reg [7:0] ii_counter;")
            lines.append("    wire in_handshake = lane_in_valid && lane_in_ready;")
            lines.append("    always @(posedge clk or negedge rst_n) begin")
            lines.append("        if (!rst_n) begin")
            lines.append("            ii_counter <= 8'd0;")
            lines.append("        end else if (pipe_advance) begin")
            lines.append("            if (in_handshake) begin")
            lines.append(f"                ii_counter <= 8'd{ii - 1};")
            lines.append("            end else if (ii_counter > 8'd0) begin")
            lines.append("                ii_counter <= ii_counter - 8'd1;")
            lines.append("            end")
            lines.append("        end")
            lines.append("    end")
            lines.append("    wire lane_in_ready = pipe_advance && (ii_counter == 8'd0);")
        else:
            lines.append("    // Initiation Interval (II=1): accept item every un-stalled cycle")
            lines.append("    wire lane_in_ready = pipe_advance;")
            lines.append("    wire in_handshake  = lane_in_valid && lane_in_ready;")

        lines.append("")
        lines.append("    // -------------------------------------------------------------------------")
        lines.append("    // Pipeline Registers and Datapath Storage")
        lines.append("    // -------------------------------------------------------------------------")
        lines.append(f"    reg [DATA_WIDTH-1:0] stage_data  [0:PIPELINE_DEPTH-1];")
        lines.append(f"    reg                  stage_valid [0:PIPELINE_DEPTH-1];")
        lines.append(f"    reg                  stage_last  [0:PIPELINE_DEPTH-1];")
        if iface == PipelineInterfaceType.MEMORY:
            lines.append(f"    reg                  stage_mem_we [0:PIPELINE_DEPTH-1];")
            lines.append(f"    reg [ADDR_WIDTH-1:0] stage_mem_addr [0:PIPELINE_DEPTH-1];")

        # Additional stage registers for multi-stage computation
        for s in range(depth):
            for var_name in stage_operations[s]["outputs"]:
                if var_name != "result":
                    lines.append(f"    reg [DATA_WIDTH-1:0] reg_s{s}_{var_name};")

        lines.append("")
        lines.append("    // Status output assignments")
        lines.append("    integer i_st;")
        lines.append("    reg any_valid;")
        lines.append("    always @(*) begin")
        lines.append("        any_valid = 1'b0;")
        lines.append("        for (i_st = 0; i_st < PIPELINE_DEPTH; i_st = i_st + 1) begin")
        lines.append("            any_valid = any_valid | stage_valid[i_st];")
        lines.append("        end")
        lines.append("    end")
        lines.append("    assign pipeline_empty = !any_valid;")
        lines.append("    assign pipeline_busy  = any_valid;")
        lines.append("")

        # Sequential pipeline stepping
        lines.append("    // -------------------------------------------------------------------------")
        lines.append("    // Synchronous Pipeline Update with Bubble Propagation and Hold on Stall")
        lines.append("    // -------------------------------------------------------------------------")
        lines.append("    integer s_idx;")
        lines.append("    always @(posedge clk or negedge rst_n) begin")
        lines.append("        if (!rst_n) begin")
        lines.append("            for (s_idx = 0; s_idx < PIPELINE_DEPTH; s_idx = s_idx + 1) begin")
        lines.append("                stage_valid[s_idx] <= 1'b0;")
        lines.append("                stage_data[s_idx]  <= {DATA_WIDTH{1'b0}};")
        lines.append("                stage_last[s_idx]  <= 1'b0;")
        if iface == PipelineInterfaceType.MEMORY:
            lines.append("                stage_mem_we[s_idx]   <= 1'b0;")
            lines.append("                stage_mem_addr[s_idx] <= {ADDR_WIDTH{1'b0}};")
        lines.append("            end")
        for s in range(depth):
            for var_name in stage_operations[s]["outputs"]:
                if var_name != "result":
                    lines.append(f"            reg_s{s}_{var_name} <= {{DATA_WIDTH{{1'b0}}}};")
        lines.append("        end else if (pipe_advance) begin")

        # Advance downstream stages
        lines.append("            // Advance pipeline stages downstream")
        for s in range(depth - 1, 0, -1):
            lines.append(f"            // --- Stage {s} ---")
            lines.append(f"            stage_valid[{s}] <= stage_valid[{s-1}];")
            lines.append(f"            stage_last[{s}]  <= stage_last[{s-1}];")
            if iface == PipelineInterfaceType.MEMORY:
                lines.append(f"            stage_mem_we[{s}]   <= stage_mem_we[{s-1}];")
                lines.append(f"            stage_mem_addr[{s}] <= stage_mem_addr[{s-1}];")
            
            # Compute data for stage s
            s_ops = stage_operations[s]["computations"]
            if s_ops:
                for target, expr in s_ops:
                    renamed_expr = self._rewrite_stage_expr(expr, arg_names, stage_operations, s)
                    if target == "result":
                        lines.append(f"            stage_data[{s}] <= {renamed_expr};")
                    else:
                        lines.append(f"            reg_s{s}_{target} <= {renamed_expr};")
            else:
                lines.append(f"            stage_data[{s}] <= stage_data[{s-1}];")

        # Stage 0 update (New input or Bubble)
        lines.append("            // --- Stage 0 (Input Sampling / Bubble Insertion) ---")
        lines.append("            if (in_handshake) begin")
        lines.append("                stage_valid[0] <= 1'b1;")
        lines.append("                stage_last[0]  <= lane_in_last;")
        if iface == PipelineInterfaceType.MEMORY:
            lines.append("                stage_mem_we[0]   <= mem_we;")
            lines.append("                stage_mem_addr[0] <= mem_addr;")
        
        # Stage 0 computations
        s0_ops = stage_operations[0]["computations"]
        if s0_ops:
            for target, expr in s0_ops:
                renamed_expr = self._rewrite_stage_expr(expr, arg_names, stage_operations, 0)
                if target == "result":
                    lines.append(f"                stage_data[0] <= {renamed_expr};")
                else:
                    lines.append(f"                reg_s0_{target} <= {renamed_expr};")
        else:
            if iface == PipelineInterfaceType.MEMORY:
                lines.append("                stage_data[0] <= mem_wdata;")
            elif arg_names:
                lines.append(f"                stage_data[0] <= in_{arg_names[0]};")
            else:
                lines.append("                stage_data[0] <= {DATA_WIDTH{1'b0}};")

        lines.append("            end else begin")
        lines.append("                // Insert bubble when no input is ready/valid")
        lines.append("                stage_valid[0] <= 1'b0;")
        lines.append("                stage_last[0]  <= 1'b0;")
        lines.append("            end")
        lines.append("        end")
        lines.append("        // Implicit: else if (pipe_stall) hold all registers and valid bits")
        lines.append("    end")
        lines.append("")

        return lines

    def _rewrite_stage_expr(self, expr: str, arg_names: List[str],
                            stage_operations: List[Dict[str, Any]], stage_idx: int) -> str:
        """Rewrite Python variable references to pipeline hardware registers."""
        out = expr
        import re
        for name in arg_names:
            out = re.sub(rf'\b{name}\b', f'in_{name}', out)

        for prev_s in range(stage_idx):
            for v in stage_operations[prev_s]["outputs"]:
                if v != "result":
                    out = re.sub(rf'\b{v}\b', f'reg_s{prev_s}_{v}', out)

        return out
