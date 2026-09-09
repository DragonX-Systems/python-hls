#!/usr/bin/env python3
"""
Debug script to trace the exact execution flow and timing of the array sum function.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import shutil

def create_debug_testbench():
    """Create a manual testbench to trace execution step by step."""
    
    # Create test function
    test_code = """
def array_sum(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
"""
    
    with open("test_array_function.py", "w") as f:
        f.write(test_code)
    
    try:
        # Compile
        hls = HLS()
        result = hls.compile("test_array_function.py", entry_function="array_sum")
        
        if isinstance(result, tuple):
            netlist, _ = result
            rtl_code = netlist.modules['array_sum'].verilog_blocks[0]
            
            # Create a custom testbench with detailed tracing
            testbench_code = """
`timescale 1ns / 1ps

module debug_testbench();

// Signals
reg clk;
reg rst_n;
reg [31:0] data_data_in;
reg [9:0] data_addr;
reg data_enable;
reg data_write_enable;
wire data_ready;
reg [31:0] data_size;
wire signed [31:0] return_val;
wire valid;
wire done;

// Instantiate DUT
array_sum dut (
    .clk(clk),
    .rst_n(rst_n),
    .data_data_in(data_data_in),
    .data_addr(data_addr),
    .data_enable(data_enable),
    .data_write_enable(data_write_enable),
    .data_ready(data_ready),
    .data_size(data_size),
    .return_val(return_val),
    .valid(valid),
    .done(done)
);

// Clock generation
initial begin
    clk = 0;
    forever #5 clk = ~clk;
end

// Test sequence
initial begin
    $display("Starting debug trace...");
    
    // Initialize
    rst_n = 0;
    data_enable = 0;
    data_write_enable = 0;
    data_data_in = 0;
    data_addr = 0;
    data_size = 0;
    
    // Reset
    #10;
    rst_n = 1;
    #10;
    
    $display("Time=%0t: After reset, fsm_state=%d, loop_counter=%d, loop_limit=%d", 
             $time, dut.fsm_state, dut.loop_counter, dut.loop_limit);
    
    // Write array data [5, 10]
    data_size = 2;
    data_enable = 1;
    data_write_enable = 1;
    
    // Write data[0] = 5
    data_addr = 0;
    data_data_in = 5;
    #10;
    $display("Time=%0t: Writing data[0]=5, fsm_state=%d, data_operation_done=%d", 
             $time, dut.fsm_state, dut.data_operation_done);
    
    // Write data[1] = 10
    data_addr = 1;
    data_data_in = 10;
    #10;
    $display("Time=%0t: Writing data[1]=10, fsm_state=%d, data_operation_done=%d", 
             $time, dut.fsm_state, dut.data_operation_done);
    
    // End write operation
    data_enable = 0;
    data_write_enable = 0;
    #10;
    $display("Time=%0t: End write, fsm_state=%d, data_operation_done=%d", 
             $time, dut.fsm_state, dut.data_operation_done);
    
    // Monitor execution
    repeat (20) begin
        #10;
        $display("Time=%0t: fsm_state=%d, loop_counter=%d, loop_limit=%d, total=%d, return_val=%d, done=%d", 
                 $time, dut.fsm_state, dut.loop_counter, dut.loop_limit, dut.total, return_val, done);
        
        if (done) begin
            $display("Final result: %d", return_val);
            break;
        end
    end
    
    $display("Array contents: data[0]=%d, data[1]=%d", dut.data_mem[0], dut.data_mem[1]);
    $finish;
end

endmodule
"""
            
            # Save files
            with open("debug_rtl.v", "w") as f:
                f.write(rtl_code)
            
            with open("debug_testbench.v", "w") as f:
                f.write(testbench_code)
            
            print("✅ Debug files created:")
            print("  - debug_rtl.v (RTL module)")
            print("  - debug_testbench.v (Debug testbench)")
            print("\nTo run simulation:")
            print("  iverilog -o debug_sim debug_rtl.v debug_testbench.v")
            print("  ./debug_sim")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists("test_array_function.py"):
            os.remove("test_array_function.py")

if __name__ == "__main__":
    success = create_debug_testbench()
    if success:
        print("\n🎉 Debug testbench created successfully!")
    else:
        print("\n💥 Debug testbench creation failed!") 