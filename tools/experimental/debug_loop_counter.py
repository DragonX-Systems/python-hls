#!/usr/bin/env python3
"""
Debug script to examine loop counter behavior in detail.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

def debug_loop_counter():
    """Debug the loop counter behavior."""
    print("=" * 60)
    print("Debug Loop Counter Behavior")
    print("=" * 60)
    
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
            
            # Extract the datapath logic
            lines = rtl_code.split('\n')
            in_datapath = False
            datapath_lines = []
            
            for line in lines:
                if "// Industry-Grade Datapath Logic" in line:
                    in_datapath = True
                elif in_datapath and "endmodule" in line:
                    break
                elif in_datapath:
                    datapath_lines.append(line)
            
            print("Datapath Logic:")
            print("=" * 40)
            for i, line in enumerate(datapath_lines):
                print(f"{i+1:3d}: {line}")
            
            print("\n" + "=" * 40)
            print("Key Observations:")
            print("1. FSM_INIT: loop_counter <= 32'h0")
            print("2. FSM_LOOP_BODY: if (loop_counter < loop_limit)")
            print("3. FSM_LOOP_BODY: total <= total + data_mem[loop_counter]")
            print("4. FSM_LOOP_BODY: loop_counter <= loop_counter + 1'b1")
            print("\nThe issue is that steps 3 and 4 happen in the SAME clock cycle!")
            print("This means the array access uses the OLD loop_counter value,")
            print("but the comparison in the next cycle uses the NEW loop_counter value.")
            
            # Show the expected execution
            print("\n" + "=" * 40)
            print("Expected execution for [5, 10]:")
            print("Clock 1: FSM_INIT -> loop_counter = 0, total = 0")
            print("Clock 2: FSM_LOOP_BODY -> loop_counter = 0, total = 0 + data[0] = 5, loop_counter = 1")
            print("Clock 3: FSM_LOOP_BODY -> loop_counter = 1, total = 5 + data[1] = 15, loop_counter = 2")
            print("Clock 4: FSM_LOOP_BODY -> loop_counter = 2 >= loop_limit = 2, exit to FSM_DONE")
            print("Clock 5: FSM_DONE -> return_val = 15")
            
            print("\nActual execution (suspected):")
            print("Clock 1: FSM_INIT -> loop_counter = 0, total = 0")
            print("Clock 2: FSM_LOOP_BODY -> loop_counter = 1, total = 0 + data[1] = 10, loop_counter = 2")
            print("Clock 3: FSM_LOOP_BODY -> loop_counter = 2 >= loop_limit = 2, exit to FSM_DONE")
            print("Clock 4: FSM_DONE -> return_val = 10")
            
            print("\nThe loop counter is being incremented BEFORE the array access!")
            
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
    success = debug_loop_counter()
    if success:
        print("\n🎉 Debug completed successfully!")
    else:
        print("\n💥 Debug failed!") 