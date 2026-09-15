"""
Testbench generator for RTL verification with Verilator debugging support.
"""

import os
import tempfile
import json
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TestbenchGenerator:
    """
    Generates Verilog testbenches for RTL verification with debugging capabilities.
    """
    
    def __init__(self, enable_debug: bool = False, enable_vcd_trace: bool = False, max_cycles: int = 1000):
        """Initialize the testbench generator with debugging and cycle options."""
        self.enable_debug = enable_debug
        self.enable_vcd_trace = enable_vcd_trace
        self.max_cycles = max_cycles
    
    def generate_testbench(self, 
                          module: Any, 
                          port_info: Dict[str, Any], 
                          test_vectors: List[Dict[str, Any]], 
                          testbench_name: str) -> str:
        """
        Generate a Verilog testbench for a module.
        
        Args:
            module: Module object from netlist
            port_info: Port information dictionary
            test_vectors: List of test vectors
            testbench_name: Name for the testbench module
            
        Returns:
            Path to generated testbench file
        """
        logger.info(f"Generating testbench for module {module.name}")
        
        # Generate testbench code
        testbench_code = self._generate_testbench_code(
            module, port_info, test_vectors, testbench_name
        )
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.v', delete=False) as f:
            f.write(testbench_code)
            return f.name

    def generate_debug_testbench(self, 
                               module: Any, 
                               port_info: Dict[str, Any], 
                               test_vectors: List[Dict[str, Any]], 
                               testbench_name: str) -> str:
        """
        Generate a specialized debug testbench with enhanced monitoring.
        
        Args:
            module: Module object from netlist
            port_info: Port information dictionary  
            test_vectors: List of test vectors
            testbench_name: Name for the testbench module
            
        Returns:
            Path to generated debug testbench file
        """
        logger.info(f"Generating debug testbench for module {module.name}")
        
        # Enable debugging features
        old_debug = self.enable_debug
        old_vcd = self.enable_vcd_trace
        self.enable_debug = True
        self.enable_vcd_trace = True
        
        try:
            # Generate enhanced testbench code
            testbench_code = self._generate_debug_testbench_code(
                module, port_info, test_vectors, testbench_name
            )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.v', delete=False) as f:
                f.write(testbench_code)
                return f.name
        finally:
            # Restore original settings
            self.enable_debug = old_debug
            self.enable_vcd_trace = old_vcd
    
    def _generate_testbench_code(self, 
                                module: Any, 
                                port_info: Dict[str, Any], 
                                test_vectors: List[Dict[str, Any]], 
                                testbench_name: str) -> str:
        """Generate the actual testbench Verilog code."""
        code = []
        
        # Header
        code.append(f"// Testbench for {module.name}")
        code.append(f"// Generated automatically for RTL verification")
        code.append("")
        code.append("`timescale 1ns/1ps")
        code.append("")
        
        # Testbench module
        code.append(f"module {testbench_name};")
        code.append("")
        
        # Clock and reset signals
        code.append("    // Clock and reset")
        code.append("    reg clk;")
        code.append("    reg rst_n;")
        code.append("")
        
        # Input/output signals based on actual port information
        code.append("    // DUT signals")
        input_signals = []
        output_signals = []
        array_signals = {}  # Track array interface signals
        
        # Add input signals from port information
        if port_info and "input_ports" in port_info:
            for port in port_info["input_ports"]:
                port_name = port["name"]
                bit_width = port["bit_width"]
                is_signed = port["is_signed"]
                
                # Check if this is an array interface signal
                if self._is_array_interface_signal(port_name):
                    array_name = self._extract_array_name(port_name)
                    if array_name not in array_signals:
                        array_signals[array_name] = {"type": "input", "signals": []}
                    array_signals[array_name]["signals"].append(port)
                
                if bit_width > 1:
                    if is_signed:
                        code.append(f"    reg signed [{bit_width-1}:0] {port_name};")
                    else:
                        code.append(f"    reg [{bit_width-1}:0] {port_name};")
                else:
                    code.append(f"    reg {port_name};")
                input_signals.append(port_name)
        else:
            # Fallback to default pattern
            code.append("    reg signed [31:0] a;")
            code.append("    reg signed [31:0] b;")
            input_signals.extend(["a", "b"])
        
        # Add output signals from port information
        if port_info and "output_ports" in port_info:
            for port in port_info["output_ports"]:
                port_name = port["name"]
                bit_width = port["bit_width"]
                is_signed = port["is_signed"]
                
                # Check if this is an array interface signal
                if self._is_array_interface_signal(port_name):
                    array_name = self._extract_array_name(port_name)
                    if array_name not in array_signals:
                        array_signals[array_name] = {"type": "output", "signals": []}
                    array_signals[array_name]["signals"].append(port)
                
                if bit_width > 1:
                    if is_signed:
                        code.append(f"    wire signed [{bit_width-1}:0] {port_name};")
                    else:
                        code.append(f"    wire [{bit_width-1}:0] {port_name};")
                else:
                    code.append(f"    wire {port_name};")
                output_signals.append(port_name)
        else:
            # Default return value
            code.append("    wire signed [31:0] return_val;")
            output_signals.append("return_val")
        
        # Add control signals
        code.append("    wire valid;")
        code.append("    wire done;")
        output_signals.extend(["valid", "done"])
        
        code.append("")
        
        # Generate array handling logic
        if array_signals:
            array_logic = self._generate_array_testbench_logic(array_signals)
            code.extend(array_logic)
            code.append("")
        
        # DUT instantiation
        code.append("    // DUT instantiation")
        code.append(f"    {module.name} dut (")
        port_connections = []
        port_connections.append("        .clk(clk)")
        port_connections.append("        .rst_n(rst_n)")
        for signal in input_signals:
            port_connections.append(f"        .{signal}({signal})")
        for signal in output_signals:
            port_connections.append(f"        .{signal}({signal})")
        code.append(",\n".join(port_connections))
        code.append("    );")
        code.append("")
        
        # Clock generation - compatible with --no-timing
        code.append("    // Clock generation")
        code.append("    initial begin")
        code.append("        clk = 0;")
        code.append("    end")
        code.append("")
        
        # Test stimulus - enhanced for arrays
        code.append("    // Test stimulus")
        code.append("    initial begin")
        code.append("        // Initialize signals")
        code.append("        rst_n = 0;")
        for signal in input_signals:
            code.append(f"        {signal} = 0;")
        code.append("")
        
        code.append("        // Reset sequence")
        code.append("        rst_n = 1;")
        code.append("")
        
        # Test vectors - enhanced for arrays
        code.append("        // Test vectors")
        for i, test_vector in enumerate(test_vectors):
            logger.debug(f"Processing Verilog test vector {i}: {test_vector} (type: {type(test_vector)})")
            
            code.append(f"        // Test case {i+1}")
            
            # Check if test_vector is a dictionary
            if not isinstance(test_vector, dict):
                logger.error(f"Verilog test vector {i} is not a dictionary: {test_vector} (type: {type(test_vector)})")
                continue
            
            # Handle array parameters specially
            array_test_code = self._generate_array_test_sequence(test_vector, array_signals)
            if array_test_code:
                code.extend(array_test_code)
            
            # Apply scalar inputs - use only signals that exist in the test vector
            for param_name, value in test_vector.items():
                if param_name in input_signals and not self._is_array_parameter(param_name, array_signals):
                    if isinstance(value, list):
                        # Skip array parameters here - they're handled above
                        continue
                    code.append(f"        {param_name} = {value};")
            
            # Wait for computation to complete
            code.append("        // Wait for computation to complete")
            code.append("        repeat (100) begin")
            code.append("            clk = 0; clk = 1;")
            code.append("            if (done) begin")
            code.append("                clk = 0;")
            code.append("                break;")
            code.append("            end")
            code.append("        end")
            code.append("        clk = 0;")  # End with clock low
            
            # Output result in JSON format
            result_json = self._format_result_output(test_vector, output_signals)
            code.append(f'        $display("RESULT: %s", {result_json});')
            code.append("")
        
        code.append("        // End simulation")
        code.append("        $finish;")
        code.append("    end")
        code.append("")
        
        code.append("endmodule")
        
        return "\n".join(code)

    def _generate_debug_testbench_code(self, 
                                     module: Any, 
                                     port_info: Dict[str, Any], 
                                     test_vectors: List[Dict[str, Any]], 
                                     testbench_name: str) -> str:
        """Generate enhanced debug testbench with detailed monitoring."""
        code = []
        
        # Module header
        code.append(f"module {testbench_name};")
        code.append("")
        
        # Clock and reset
        code.append("    reg clk;")
        code.append("    reg rst_n;")
        code.append("")
        
        # Input/output declarations
        input_ports = port_info.get("input_ports", [])
        output_ports = port_info.get("output_ports", [])
        
        # Declare input signals
        for port in input_ports:
            if port["width"] == 1:
                code.append(f"    reg {port['name']};")
            else:
                code.append(f"    reg [{port['width']-1}:0] {port['name']};")
        
        # Declare output signals
        for port in output_ports:
            if port["width"] == 1:
                code.append(f"    wire {port['name']};")
            else:
                code.append(f"    wire [{port['width']-1}:0] {port['name']};")
        
        code.append("")
        
        # Detect array interfaces
        array_signals = {}
        for port in input_ports:
            if self._is_array_interface_signal(port["name"]):
                array_name = self._extract_array_name(port["name"])
                if array_name not in array_signals:
                    array_signals[array_name] = {"type": "input", "signals": []}
                array_signals[array_name]["signals"].append(port)
        
        # Module instantiation
        code.append(f"    {module.name} dut (")
        port_connections = []
        port_connections.append("        .clk(clk)")
        port_connections.append("        .rst_n(rst_n)")
        
        for port in input_ports:
            port_connections.append(f"        .{port['name']}({port['name']})")
        for port in output_ports:
            port_connections.append(f"        .{port['name']}({port['name']})")
        
        code.append(",\n".join(port_connections))
        code.append("    );")
        code.append("")
        
        # Clock generation
        code.append("    // Clock generation")
        code.append("    initial begin")
        code.append("        clk = 0;")
        code.append("        forever #5 clk = ~clk;")
        code.append("    end")
        code.append("")
        
        # VCD dump setup
        if self.enable_vcd_trace:
            code.append("    // VCD dump setup")
            code.append("    initial begin")
            code.append(f'        $dumpfile("{testbench_name}_debug.vcd");')
            code.append("        $dumpvars(0, dut);")
            code.append("    end")
            code.append("")
        
        # Debug monitoring
        if self.enable_debug:
            code.append("    // Debug monitoring")
            code.append("    always @(posedge clk) begin")
            code.append("        if (rst_n) begin")
            code.append('            $display("Cycle %0d: FSM_state=%0d, loop_counter=%0d, done=%0d", ')
            code.append('                     $time/10, dut.FSM_state, dut.loop_counter, dut.done);')
            
            # Monitor array interface signals if present
            for array_name in array_signals:
                code.append(f'            if (dut.{array_name}_enable)')
                code.append(f'                $display("  Array {array_name}: addr=%0d, data=%0d, enable=%0d", ')
                code.append(f'                         dut.{array_name}_addr, dut.{array_name}_data, dut.{array_name}_enable);')
            
            code.append("        end")
            code.append("    end")
            code.append("")
        
        # Generate array testbench logic
        if array_signals:
            code.extend(self._generate_array_testbench_logic(array_signals))
        
        # Main test sequence
        code.append("    // Main test sequence")
        code.append("    initial begin")
        code.append("        // Initialize")
        code.append("        rst_n = 0;")
        
        # Initialize all inputs
        for port in input_ports:
            code.append(f"        {port['name']} = 0;")
        
        code.append("        #20;")
        code.append("        rst_n = 1;")
        code.append("        #10;")
        code.append("")
        
        # Test vectors
        for i, test_vector in enumerate(test_vectors):
            code.append(f"        // Test case {i+1}")
            
            # Generate array test sequence
            if array_signals:
                code.extend(self._generate_array_test_sequence(test_vector, array_signals))
            
            # Set scalar inputs
            for param_name, value in test_vector.items():
                if not isinstance(value, list):
                    input_port_names = [port["name"] for port in input_ports]
                    if param_name in input_port_names:
                        code.append(f"        {param_name} = {value};")
            
            # Wait for completion
            code.append("        @(posedge done);")
            code.append("        #10;")
            
            # Display result
            output_signal = output_ports[0]["name"] if output_ports else "return_val"
            code.append(f'        $display("Test {i+1} Result: %0d", {output_signal});')
            code.append("")
        
        code.append("        $finish;")
        code.append("    end")
        code.append("")
        code.append("endmodule")
        
        return "\n".join(code)

    def _generate_cpp_array_helpers(self, array_signals: Dict[str, Any], module_name: str) -> List[str]:
        """Generate C++ helper functions for array operations."""
        code = []
        
        for array_name, array_info in array_signals.items():
            if array_info["type"] == "input":
                code.extend(self._generate_cpp_array_input_helper(array_name, module_name))
            elif array_info["type"] == "output":
                code.extend(self._generate_cpp_array_output_helper(array_name, module_name))
        
        return code
    
    def _generate_cpp_array_input_helper(self, array_name: str, module_name: str) -> List[str]:
        """Generate C++ helper function for array input."""
        code = []
        code.append(f"// Helper function to write array data for {array_name}")
        code.append(f"void write_array_{array_name}(V{module_name}* dut, const std::vector<uint32_t>& data) {{")
        code.append(f"    dut->{array_name}_size = data.size();")
        code.append(f"    dut->{array_name}_enable = 1;  // Keep enable high for entire write sequence")
        code.append(f"    for (size_t i = 0; i < data.size(); i++) {{")
        code.append(f"        dut->{array_name}_addr = i;")
        code.append(f"        dut->{array_name}_data_in = data[i];")
        code.append(f"        dut->{array_name}_write_enable = 1;")
        code.append(f"        dut->clk = 0; dut->eval();")
        code.append(f"        dut->clk = 1; dut->eval();")
        code.append(f"        dut->{array_name}_write_enable = 0;")
        code.append(f"        dut->clk = 0; dut->eval();")
        code.append(f"    }}")
        code.append(f"    // Signal completion by disabling enable")
        code.append(f"    dut->{array_name}_enable = 0;")
        code.append(f"    dut->clk = 0; dut->eval();")
        code.append(f"    dut->clk = 1; dut->eval();")
        code.append(f"}}")
        code.append("")
        
        return code
    
    def _generate_cpp_array_output_helper(self, array_name: str, module_name: str) -> List[str]:
        """Generate C++ helper function for array output."""
        code = []
        code.append(f"// Helper function to read array data for {array_name}")
        code.append(f"std::vector<uint32_t> read_array_{array_name}(V{module_name}* dut, size_t size) {{")
        code.append(f"    std::vector<uint32_t> data(size);")
        code.append(f"    for (size_t i = 0; i < size; i++) {{")
        code.append(f"        dut->{array_name}_addr = i;")
        code.append(f"        dut->{array_name}_enable = 1;")
        code.append(f"        dut->{array_name}_read_enable = 1;")
        code.append(f"        dut->clk = 0; dut->eval();")
        code.append(f"        dut->clk = 1; dut->eval();")
        code.append(f"        data[i] = dut->{array_name}_data_out;")
        code.append(f"        dut->{array_name}_enable = 0;")
        code.append(f"        dut->{array_name}_read_enable = 0;")
        code.append(f"        dut->clk = 0; dut->eval();")
        code.append(f"    }}")
        code.append(f"    return data;")
        code.append(f"}}")
        code.append("")
        
        return code
    
    def _is_array_interface_signal(self, signal_name: str) -> bool:
        """Check if a signal is part of an array interface."""
        # Order suffixes from longest to shortest to ensure proper matching
        array_suffixes = ['_write_enable', '_read_enable', '_data_in', '_data_out', 
                         '_addr', '_enable', '_ready', '_valid', '_size']
        return any(signal_name.endswith(suffix) for suffix in array_suffixes)
    
    def _extract_array_name(self, signal_name: str) -> str:
        """Extract the array name from an array interface signal."""
        # Order suffixes from longest to shortest to ensure proper matching
        array_suffixes = ['_write_enable', '_read_enable', '_data_in', '_data_out', 
                         '_addr', '_enable', '_ready', '_valid', '_size']
        for suffix in array_suffixes:
            if signal_name.endswith(suffix):
                return signal_name[:-len(suffix)]
        return signal_name
    
    def _is_array_parameter(self, param_name: str, array_signals: Dict[str, Any]) -> bool:
        """Check if a parameter is an array parameter."""
        return param_name in array_signals
    
    def _generate_array_testbench_logic(self, array_signals: Dict[str, Any]) -> List[str]:
        """Generate testbench logic for array interfaces."""
        code = []
        code.append("    // Array interface handling logic")
        
        for array_name, array_info in array_signals.items():
            if array_info["type"] == "input":
                code.extend(self._generate_array_input_logic(array_name, array_info))
            elif array_info["type"] == "output":
                code.extend(self._generate_array_output_logic(array_name, array_info))
        
        return code
    
    def _generate_array_input_logic(self, array_name: str, array_info: Dict[str, Any]) -> List[str]:
        """Generate testbench logic for array input interfaces."""
        code = []
        code.append(f"    // Array input logic for {array_name}")
        
        # Add task for writing array data
        code.append(f"    task write_array_{array_name};")
        code.append(f"        input [31:0] data [];")
        code.append(f"        input [31:0] size;")
        code.append(f"        integer i;")
        code.append(f"        begin")
        code.append(f"            {array_name}_size = size;")
        code.append(f"            {array_name}_enable = 1'b1;  // Keep enable high for entire write sequence")
        code.append(f"            for (i = 0; i < size; i = i + 1) begin")
        code.append(f"                {array_name}_addr = i;")
        code.append(f"                {array_name}_data_in = data[i];")
        code.append(f"                {array_name}_write_enable = 1'b1;")
        code.append(f"                clk = 0; clk = 1; clk = 0;")
        code.append(f"                {array_name}_write_enable = 1'b0;")
        code.append(f"                clk = 0; clk = 1; clk = 0;")
        code.append(f"            end")
        code.append(f"            // Signal completion by disabling enable")
        code.append(f"            {array_name}_enable = 1'b0;")
        code.append(f"            clk = 0; clk = 1; clk = 0;")
        code.append(f"        end")
        code.append(f"    endtask")
        code.append("")
        
        return code
    
    def _generate_array_output_logic(self, array_name: str, array_info: Dict[str, Any]) -> List[str]:
        """Generate testbench logic for array output interfaces."""
        code = []
        code.append(f"    // Array output logic for {array_name}")
        
        # Add task for reading array data
        code.append(f"    task read_array_{array_name};")
        code.append(f"        output [31:0] data [];")
        code.append(f"        input [31:0] size;")
        code.append(f"        integer i;")
        code.append(f"        begin")
        code.append(f"            for (i = 0; i < size; i = i + 1) begin")
        code.append(f"                {array_name}_addr = i;")
        code.append(f"                {array_name}_enable = 1'b1;")
        code.append(f"                {array_name}_read_enable = 1'b1;")
        code.append(f"                clk = 0; clk = 1; clk = 0;")
        code.append(f"                data[i] = {array_name}_data_out;")
        code.append(f"                {array_name}_enable = 1'b0;")
        code.append(f"                {array_name}_read_enable = 1'b0;")
        code.append(f"                clk = 0; clk = 1; clk = 0;")
        code.append(f"            end")
        code.append(f"        end")
        code.append(f"    endtask")
        code.append("")
        
        return code
    
    def _generate_array_test_sequence(self, test_vector: Dict[str, Any], array_signals: Dict[str, Any]) -> List[str]:
        """Generate test sequence for array parameters."""
        code = []
        
        for param_name, value in test_vector.items():
            if isinstance(value, list) and param_name in array_signals:
                array_info = array_signals[param_name]
                if array_info["type"] == "input":
                    code.append(f"        // Write array data for {param_name}")
                    
                    # Handle empty arrays
                    if len(value) == 0:
                        # Empty array - declare empty array and call write task with 0 size
                        code.append(f"        reg [31:0] {param_name}_data [1];  // Dummy array for empty case")
                        code.append(f"        write_array_{param_name}({param_name}_data, 0);")
                    # Handle 2D arrays by flattening them
                    elif isinstance(value[0], list):
                        # 2D array - flatten it for Verilog
                        flattened_values = []
                        for row in value:
                            flattened_values.extend(row)
                        
                        # Declare flattened array variable
                        code.append(f"        reg [31:0] {param_name}_data [{len(flattened_values)}];")
                        
                        # Initialize array data element by element
                        for i, item in enumerate(flattened_values):
                            code.append(f"        {param_name}_data[{i}] = {item};")
                        
                        # Call write task with flattened size
                        code.append(f"        write_array_{param_name}({param_name}_data, {len(flattened_values)});")
                    else:
                        # 1D array - use as is
                        # Declare array variable
                        code.append(f"        reg [31:0] {param_name}_data [{len(value)}];")
                        
                        # Initialize array data
                        for i, item in enumerate(value):
                            code.append(f"        {param_name}_data[{i}] = {item};")
                        
                        # Call write task
                        code.append(f"        write_array_{param_name}({param_name}_data, {len(value)});")
                    
                    code.append("")
        
        return code
    
    def _format_result_output(self, test_vector: Dict[str, Any], output_signals: List[str]) -> str:
        """Format the result output as JSON string for parsing."""
        # Create a simple format string for Verilog $display
        test_inputs_str = json.dumps(test_vector).replace('"', '\\"')
        
        if output_signals:
            # Create format specifiers for outputs
            output_format_parts = []
            output_args = []
            
            for signal in output_signals:
                output_format_parts.append(f'\\"{signal}\\": %d')
                output_args.append(signal)
            
            output_format = ', '.join(output_format_parts)
            format_string = f'{{\\"test_inputs\\": \\"{test_inputs_str}\\", \\"outputs\\": {{{output_format}}}}}'
            
            if output_args:
                return f'"{format_string}", ' + ', '.join(output_args)
            else:
                return f'"{format_string}"'
        else:
            # No outputs
            format_string = f'{{\\"test_inputs\\": \\"{test_inputs_str}\\", \\"outputs\\": {{}}}}'
            return f'"{format_string}"'
    def generate_cpp_testbench(self, 
                              module: Any, 
                              port_info: Dict[str, Any], 
                              test_vectors: List[Dict[str, Any]], 
                              testbench_name: str,
                              max_cycles: Optional[int] = None,
                              vcd_file: Optional[str] = None) -> str:
        """
        Generate a C++ testbench for Verilator.
        
        Args:
            module: Module object from netlist
            port_info: Port information dictionary
            test_vectors: List of test vectors
            testbench_name: Name for the testbench module
            max_cycles: Optional maximum simulation cycles before timeout
            vcd_file: Optional path for VCD waveform dump
            
        Returns:
            Path to generated C++ testbench file
        """
        logger.info(f"Generating C++ testbench for module {module.name}")
        cycles = max_cycles if max_cycles is not None else self.max_cycles
        
        cpp_code = self._generate_cpp_testbench_code(
            module, port_info, test_vectors, testbench_name, max_cycles=cycles, vcd_file=vcd_file
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
            f.write(cpp_code)
            return f.name
    
    def _generate_cpp_testbench_code(self, 
                                    module: Any, 
                                    port_info: Dict[str, Any], 
                                    test_vectors: List[Dict[str, Any]], 
                                    testbench_name: str,
                                    max_cycles: int = 1000,
                                    vcd_file: Optional[str] = None) -> str:
        """Generate C++ testbench code for Verilator."""
        logger.debug(f"Generating C++ testbench for {module.name}")
        logger.debug(f"Port info type: {type(port_info)}")
        logger.debug(f"Test vectors type: {type(test_vectors)}")
        logger.debug(f"Test vectors length: {len(test_vectors) if hasattr(test_vectors, '__len__') else 'N/A'}")
        if test_vectors and len(test_vectors) > 0:
            logger.debug(f"First test vector type: {type(test_vectors[0])}")
            logger.debug(f"First test vector: {test_vectors[0]}")
        
        use_vcd = bool(vcd_file or self.enable_vcd_trace)
        code = []
        
        # Headers
        code.append("#include <iostream>")
        code.append("#include <vector>")
        code.append("#include <verilated.h>")
        if use_vcd:
            code.append("#include <verilated_vcd_c.h>")
        code.append(f"#include \"V{module.name}.h\"")
        code.append("")
        
        # Detect array interfaces
        array_signals = {}
        if port_info and "input_ports" in port_info:
            for port in port_info["input_ports"]:
                if self._is_array_interface_signal(port["name"]):
                    array_name = self._extract_array_name(port["name"])
                    if array_name not in array_signals:
                        array_signals[array_name] = {"type": "input", "signals": []}
                    array_signals[array_name]["signals"].append(port)
        
        if port_info and "output_ports" in port_info:
            for port in port_info["output_ports"]:
                if self._is_array_interface_signal(port["name"]):
                    array_name = self._extract_array_name(port["name"])
                    if array_name not in array_signals:
                        array_signals[array_name] = {"type": "output", "signals": []}
                    array_signals[array_name]["signals"].append(port)
        
        # Generate array helper functions
        if array_signals:
            code.extend(self._generate_cpp_array_helpers(array_signals, module.name))
        
        # Main function
        code.append("int main(int argc, char** argv) {")
        code.append("    Verilated::commandArgs(argc, argv);")
        code.append("")
        
        # Create DUT
        code.append(f"    V{module.name}* dut = new V{module.name};")
        if use_vcd:
            actual_vcd = vcd_file if vcd_file else f"{testbench_name}.vcd"
            code.append("    Verilated::traceEverOn(true);")
            code.append("    VerilatedVcdC* tfp = new VerilatedVcdC;")
            code.append("    dut->trace(tfp, 99);")
            code.append(f"    tfp->open(\"{actual_vcd}\");")
            code.append("    vluint64_t sim_time = 0;")
        code.append("")
        
        # Reset sequence
        code.append("    // Reset")
        code.append("    dut->rst_n = 0;")
        code.append("    dut->clk = 0;")
        code.append("    dut->eval();")
        if use_vcd:
            code.append("    if (tfp) tfp->dump(sim_time++);")
        code.append("    dut->clk = 1;")
        code.append("    dut->eval();")
        if use_vcd:
            code.append("    if (tfp) tfp->dump(sim_time++);")
        code.append("    dut->rst_n = 1;")
        code.append("")
        code.append("    int cycles_to_done = -1;")
        code.append("")
        
        # Test vectors
        for i, test_vector in enumerate(test_vectors):
            logger.debug(f"Processing test vector {i}: {test_vector} (type: {type(test_vector)})")
            
            code.append(f"    // Test case {i+1}")
            
            # Reset DUT before each test to ensure clean state
            if i > 0:
                code.append("    // Reset DUT for clean state")
                code.append("    dut->rst_n = 0;")
                code.append("    dut->clk = 0;")
                code.append("    dut->eval();")
                if use_vcd:
                    code.append("    if (tfp) tfp->dump(sim_time++);")
                code.append("    dut->clk = 1;")
                code.append("    dut->eval();")
                if use_vcd:
                    code.append("    if (tfp) tfp->dump(sim_time++);")
                code.append("    dut->rst_n = 1;")
                code.append("")
            
            # Set inputs - only set inputs that exist in the port info
            input_port_names = [port["name"] for port in port_info.get("input_ports", [])] if port_info else []
            
            if not isinstance(test_vector, dict):
                logger.error(f"Test vector {i} is not a dictionary: {test_vector} (type: {type(test_vector)})")
                continue
            
            # Handle array parameters
            for param_name, value in test_vector.items():
                if isinstance(value, list) and param_name in array_signals:
                    array_info = array_signals[param_name]
                    if array_info["type"] == "input":
                        code.append(f"    // Write array data for {param_name}")
                        if len(value) == 0:
                            code.append(f"    std::vector<uint32_t> {param_name}_data_{i};")
                        elif isinstance(value[0], list):
                            flattened_values = []
                            for row in value:
                                flattened_values.extend(row)
                            code.append(f"    std::vector<uint32_t> {param_name}_data_{i} = {{{', '.join(map(str, flattened_values))}}};")
                        else:
                            code.append(f"    std::vector<uint32_t> {param_name}_data_{i} = {{{', '.join(map(str, value))}}};")
                        
                        if self.enable_debug:
                            code.append(f"    std::cout << \"Writing array {param_name} with {len(value)} elements\" << std::endl;")
                        code.append(f"    write_array_{param_name}(dut, {param_name}_data_{i});")
                        code.append("")
            
            # Set scalar inputs
            for param_name, value in test_vector.items():
                if param_name in input_port_names and not self._is_array_parameter(param_name, array_signals):
                    if not isinstance(value, list):
                        code.append(f"    dut->{param_name} = {value};")
            
            # Clock cycles - wait for computation to complete
            code.append("    // Run until computation completes")
            code.append("    cycles_to_done = -1;")
            code.append(f"    for (int cycle = 0; cycle < {max_cycles}; cycle++) {{")
            code.append("        dut->clk = 0;")
            code.append("        dut->eval();")
            if use_vcd:
                code.append("        if (tfp) tfp->dump(sim_time++);")
            code.append("        dut->clk = 1;")
            code.append("        dut->eval();")
            if use_vcd:
                code.append("        if (tfp) tfp->dump(sim_time++);")
            code.append("        if (dut->done) {")
            code.append("            cycles_to_done = cycle + 1;")
            code.append("            break;")
            code.append("        }")
            code.append("    }")
            code.append("")
            
            # Output result
            inputs_list = [f"{k}={v}" for k, v in test_vector.items() if k in input_port_names and not isinstance(v, list)]
            inputs_str = ','.join(inputs_list)
            
            # Check for output arrays
            output_arrays = [name for name, info in array_signals.items() if info.get("type") == "output"]
            if output_arrays:
                out_name = output_arrays[0]
                code.append(f"    size_t out_len_{out_name} = dut->{out_name}_size;")
                code.append(f"    if (out_len_{out_name} == 0) out_len_{out_name} = 8;")
                code.append(f"    std::vector<uint32_t> out_data_{out_name} = read_array_{out_name}(dut, out_len_{out_name});")
                code.append(f'    std::cout << "RESULT: inputs={{{inputs_str}}},output=[";')
                code.append(f"    for (size_t k = 0; k < out_data_{out_name}.size(); ++k) {{")
                code.append(f'        if (k > 0) std::cout << ",";')
                code.append(f"        std::cout << out_data_{out_name}[k];")
                code.append("    }")
                code.append(f'    std::cout << "],cycles=" << cycles_to_done << std::endl;')
            else:
                data_output_ports = [
                    p for p in port_info.get("output_ports", [])
                    if p["name"] not in ["valid", "done"] and not self._is_array_interface_signal(p["name"])
                ] if port_info else []
                
                if len(data_output_ports) > 1:
                    ret_exprs = [f'\\"{p["name"]}\\": " << dut->{p["name"]}' for p in data_output_ports]
                    ret_str = ' << ", " << '.join(ret_exprs)
                    code.append(f'    std::cout << "RESULT: inputs={{{inputs_str}}},output={{{{" << {ret_str} << "}}}},cycles=" << cycles_to_done << std::endl;')
                else:
                    output_port_name = data_output_ports[0]["name"] if data_output_ports else "return_val"
                    code.append(f'    std::cout << "RESULT: inputs={{{inputs_str}}},output=" << dut->{output_port_name} << ",cycles=" << cycles_to_done << std::endl;')
            code.append("")
        
        # Cleanup
        if use_vcd:
            code.append("    if (tfp) {")
            code.append("        tfp->close();")
            code.append("        delete tfp;")
            code.append("    }")
        code.append("    delete dut;")
        code.append("    return 0;")
        code.append("}")
        
        return '\n'.join(code)

    def generate_cpp_debug_testbench(self, 
                                   module: Any, 
                                   port_info: Dict[str, Any], 
                                   test_vectors: List[Dict[str, Any]], 
                                   testbench_name: str) -> str:
        """Generate C++ testbench with Verilator debugging features."""
        # Enable debugging features
        old_debug = self.enable_debug
        old_vcd = self.enable_vcd_trace
        self.enable_debug = True
        self.enable_vcd_trace = True
        
        try:
            # Generate enhanced C++ testbench code
            testbench_code = self._generate_cpp_debug_testbench_code(
                module, port_info, test_vectors, testbench_name
            )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
                f.write(testbench_code)
                return f.name
        finally:
            # Restore original settings
            self.enable_debug = old_debug
            self.enable_vcd_trace = old_vcd

    def _generate_cpp_debug_testbench_code(self, 
                                         module: Any, 
                                         port_info: Dict[str, Any], 
                                         test_vectors: List[Dict[str, Any]], 
                                         testbench_name: str) -> str:
        """Generate enhanced C++ testbench code with debugging features."""
        code = []
        
        # Headers
        code.append("#include <iostream>")
        code.append("#include <vector>")
        code.append("#include <iomanip>")
        code.append("#include <verilated.h>")
        if self.enable_vcd_trace:
            code.append("#include <verilated_vcd_c.h>")
        code.append(f"#include \"V{module.name}.h\"")
        code.append("")
        
        # Detect array interfaces
        array_signals = {}
        if port_info and "input_ports" in port_info:
            for port in port_info["input_ports"]:
                if self._is_array_interface_signal(port["name"]):
                    array_name = self._extract_array_name(port["name"])
                    if array_name not in array_signals:
                        array_signals[array_name] = {"type": "input", "signals": []}
                    array_signals[array_name]["signals"].append(port)
        
        # Generate array helper functions
        if array_signals:
            code.extend(self._generate_cpp_array_helpers(array_signals, module.name))
        
        # Debug helper function
        if self.enable_debug:
            code.append("// Debug helper function")
            code.append(f"void print_debug_info(V{module.name}* dut, int cycle) {{")
            code.append("    std::cout << \"Cycle \" << std::setw(3) << cycle << \": \"")
            code.append("              << \"FSM_state=\" << (int)dut->FSM_state")
            code.append("              << \", loop_counter=\" << (int)dut->loop_counter")
            code.append("              << \", done=\" << (int)dut->done")
            
            # Add array interface monitoring
            for array_name in array_signals:
                code.append(f"              << \", {array_name}_enable=\" << (int)dut->{array_name}_enable")
                code.append(f"              << \", {array_name}_addr=\" << (int)dut->{array_name}_addr")
                code.append(f"              << \", {array_name}_data=\" << (int)dut->{array_name}_data")
            
            code.append("              << std::endl;")
            code.append("}")
            code.append("")
        
        # Main function
        code.append("int main(int argc, char** argv) {")
        code.append("    Verilated::commandArgs(argc, argv);")
        if self.enable_debug:
            code.append("    Verilated::debug(1);")
        code.append("")
        
        # Create DUT
        code.append(f"    V{module.name}* dut = new V{module.name};")
        code.append("")
        
        # VCD trace setup
        if self.enable_vcd_trace:
            code.append("    // VCD trace setup")
            code.append("    VerilatedVcdC* tfp = nullptr;")
            code.append("    if (Verilated::commandArgsPlusMatch(\"trace\")) {")
            code.append("        Verilated::traceEverOn(true);")
            code.append("        tfp = new VerilatedVcdC;")
            code.append("        dut->trace(tfp, 99);")
            code.append(f"        tfp->open(\"{testbench_name}_debug.vcd\");")
            code.append("    }")
            code.append("")
        
        # Reset sequence
        code.append("    // Reset sequence")
        code.append("    dut->rst_n = 0;")
        code.append("    dut->clk = 0;")
        code.append("    dut->eval();")
        if self.enable_vcd_trace:
            code.append("    if (tfp) tfp->dump(0);")
        code.append("")
        
        code.append("    dut->clk = 1;")
        code.append("    dut->eval();")
        if self.enable_vcd_trace:
            code.append("    if (tfp) tfp->dump(5);")
        code.append("")
        
        code.append("    dut->rst_n = 1;")
        code.append("    dut->clk = 0;")
        code.append("    dut->eval();")
        if self.enable_vcd_trace:
            code.append("    if (tfp) tfp->dump(10);")
        code.append("")
        
        # Test vectors with detailed monitoring
        for i, test_vector in enumerate(test_vectors):
            code.append(f"    // Test case {i+1}")
            if self.enable_debug:
                code.append(f"    std::cout << \"\\n=== Test Case {i+1} ===\" << std::endl;")
            
            # Reset DUT before each test
            if i > 0:
                code.append("    // Reset DUT for clean state")
                code.append("    dut->rst_n = 0;")
                code.append("    dut->clk = 0;")
                code.append("    dut->eval();")
                code.append("    dut->clk = 1;")
                code.append("    dut->eval();")
                code.append("    dut->rst_n = 1;")
                code.append("")
            
            # Set inputs
            input_port_names = [port["name"] for port in port_info.get("input_ports", [])] if port_info else []
            
            # Handle array parameters
            for param_name, value in test_vector.items():
                if isinstance(value, list) and param_name in array_signals:
                    array_info = array_signals[param_name]
                    if array_info["type"] == "input":
                        code.append(f"    // Write array data for {param_name}")
                        
                        # Handle empty arrays
                        if len(value) == 0:
                            # Empty array - create empty vector
                            code.append(f"    std::vector<uint32_t> {param_name}_data_{i};")
                        # Flatten 2D arrays for C++ vector initialization
                        elif isinstance(value[0], list):
                            # 2D array - flatten it
                            flattened_values = []
                            for row in value:
                                flattened_values.extend(row)
                            code.append(f"    std::vector<uint32_t> {param_name}_data_{i} = {{{', '.join(map(str, flattened_values))}}};")
                        else:
                            # 1D array - use as is
                            code.append(f"    std::vector<uint32_t> {param_name}_data_{i} = {{{', '.join(map(str, value))}}};")
                        
                        if self.enable_debug:
                            code.append(f"    std::cout << \"Writing array {param_name} with {len(value)} elements\" << std::endl;")
                        code.append(f"    write_array_{param_name}(dut, {param_name}_data_{i});")
                        code.append("")
            
            # Set scalar inputs
            for param_name, value in test_vector.items():
                if param_name in input_port_names and not self._is_array_parameter(param_name, array_signals):
                    if not isinstance(value, list):
                        code.append(f"    dut->{param_name} = {value};")
            
            # Run with detailed monitoring
            code.append("    // Run with detailed monitoring")
            code.append("    int cycle = 0;")
            code.append("    while (cycle < 100 && !dut->done) {")
            code.append("        dut->clk = 0;")
            code.append("        dut->eval();")
            if self.enable_vcd_trace:
                code.append("        if (tfp) tfp->dump(cycle * 10);")
            
            if self.enable_debug:
                code.append("        print_debug_info(dut, cycle);")
            
            code.append("        dut->clk = 1;")
            code.append("        dut->eval();")
            if self.enable_vcd_trace:
                code.append("        if (tfp) tfp->dump(cycle * 10 + 5);")
            
            code.append("        cycle++;")
            code.append("    }")
            code.append("")
            
            # Output result
            output_port_name = "return_val"
            if port_info and "output_ports" in port_info and len(port_info["output_ports"]) > 0:
                output_port_name = port_info["output_ports"][0]["name"]
            
            code.append("    // Output result")
            inputs_list = [f"{k}={v}" for k, v in test_vector.items() if k in input_port_names and not isinstance(v, list)]
            inputs_str = ','.join(inputs_list)
            code.append(f'    std::cout << "RESULT: inputs={{{inputs_str}}},output=" << dut->{output_port_name} << std::endl;')
            
            if self.enable_debug:
                code.append(f"    std::cout << \"Final state: FSM_state=\" << (int)dut->FSM_state")
                code.append(f"              << \", loop_counter=\" << (int)dut->loop_counter")
                code.append(f"              << \", cycles=\" << cycle << std::endl;")
            code.append("")
        
        # Cleanup
        if self.enable_vcd_trace:
            code.append("    // Cleanup")
            code.append("    if (tfp) {")
            code.append("        tfp->close();")
            code.append("        delete tfp;")
            code.append("    }")
        
        code.append("    delete dut;")
        code.append("    return 0;")
        code.append("}")
        
        return "\n".join(code)