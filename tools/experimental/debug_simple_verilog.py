#!/usr/bin/env python3
"""
Simple debug script to generate and examine Verilog code for array sum function.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_and_examine_verilog():
    """Generate Verilog code for array sum function and examine it."""
    print("=" * 60)
    print("Generating and Examining Verilog Code for Array Sum")
    print("=" * 60)
    
    # Create test function
    test_code = """
def array_sum(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
"""
    
    # Write test code to file
    with open("debug_array_function.py", "w") as f:
        f.write(test_code)
    
    try:
        # Create HLS instance and compile
        hls = HLS()
        compile_result = hls.compile("debug_array_function.py", entry_function="array_sum")
        
        # Handle tuple return (netlist, synthesis_logs)
        if isinstance(compile_result, tuple):
            netlist, synthesis_logs = compile_result
        else:
            print(f"❌ Unexpected compile result type: {type(compile_result)}")
            return False
        
        if not netlist:
            print("❌ No netlist generated")
            return False
        
        print("✅ Compilation successful")
        
        # Get modules from netlist
        modules = netlist.modules if hasattr(netlist, 'modules') else {}
        if not modules:
            print("❌ No modules generated")
            return False
        
        # Get the main module
        main_module = None
        for module_name, module in modules.items():
            if "array_sum" in module_name:
                main_module = module
                break
        
        if not main_module:
            print("❌ Main module not found")
            return False
        
        print(f"✅ Found main module: {main_module.name}")
        
        # Generate Verilog code using the VerilogGenerator
        verilog_netlist = hls.verilog_generator.generate(hls.scheduled_ir)
        
        # Extract Verilog code from the netlist
        if hasattr(verilog_netlist, 'modules') and main_module.name in verilog_netlist.modules:
            netlist_module = verilog_netlist.modules[main_module.name]
            if hasattr(netlist_module, 'verilog_blocks') and netlist_module.verilog_blocks:
                verilog_code = netlist_module.verilog_blocks[0]  # Get the first (and usually only) block
            else:
                print(f"⚠️  No Verilog blocks found for module {main_module.name}")
                return False
        else:
            print(f"⚠️  Module {main_module.name} not found in generated netlist")
            return False
        
        # Save Verilog code to file
        verilog_file = f"{main_module.name}_debug.v"
        with open(verilog_file, "w") as f:
            f.write(verilog_code)
            f.write("\n")
        
        print(f"✅ Generated Verilog file: {verilog_file}")
        print(f"📊 Verilog code size: {len(verilog_code)} characters")
        
        # Analyze the Verilog code
        print("\n🔍 Analyzing Verilog Code Structure:")
        
        # Check for FSM states
        fsm_states = []
        for line in verilog_code.split('\n'):
            if 'FSM_' in line and 'localparam' in line:
                fsm_states.append(line.strip())
        
        if fsm_states:
            print("🎯 FSM States found:")
            for state in fsm_states:
                print(f"  {state}")
        else:
            print("⚠️  No FSM states found")
        
        # Check for loop counter logic
        loop_counter_lines = []
        for i, line in enumerate(verilog_code.split('\n')):
            if 'loop_counter' in line.lower():
                loop_counter_lines.append(f"Line {i+1}: {line.strip()}")
        
        if loop_counter_lines:
            print("\n🎯 Loop Counter Logic:")
            for line in loop_counter_lines[:10]:  # Show first 10 occurrences
                print(f"  {line}")
            if len(loop_counter_lines) > 10:
                print(f"  ... and {len(loop_counter_lines) - 10} more occurrences")
        else:
            print("⚠️  No loop counter logic found")
        
        # Check for array interface signals
        array_signals = []
        for line in verilog_code.split('\n'):
            if 'data_' in line and ('input' in line or 'output' in line or 'wire' in line or 'reg' in line):
                array_signals.append(line.strip())
        
        if array_signals:
            print("\n🎯 Array Interface Signals:")
            for signal in array_signals[:10]:  # Show first 10
                print(f"  {signal}")
            if len(array_signals) > 10:
                print(f"  ... and {len(array_signals) - 10} more signals")
        else:
            print("⚠️  No array interface signals found")
        
        # Check for key logic patterns
        key_patterns = [
            ('FSM_INIT', 'FSM initialization'),
            ('FSM_LOOP_BODY', 'Loop body execution'),
            ('FSM_LOOP_UPDATE', 'Loop counter update'),
            ('loop_counter <= 32\'h0', 'Loop counter reset'),
            ('loop_counter <=', 'Loop counter assignment'),
            ('data_mem[', 'Array memory access'),
            ('total <=', 'Accumulator update')
        ]
        
        print("\n🎯 Key Logic Patterns:")
        for pattern, description in key_patterns:
            count = verilog_code.count(pattern)
            if count > 0:
                print(f"  ✅ {description}: {count} occurrences")
            else:
                print(f"  ❌ {description}: Not found")
        
        # Extract module ports
        print("\n🎯 Module Ports:")
        in_module = False
        for line in verilog_code.split('\n'):
            if line.strip().startswith('module'):
                in_module = True
                print(f"  {line.strip()}")
            elif in_module and line.strip() == ');':
                print(f"  {line.strip()}")
                in_module = False
            elif in_module and ('input' in line or 'output' in line):
                print(f"  {line.strip()}")
        
        print(f"\n📄 Full Verilog code saved to: {verilog_file}")
        print("🔍 You can examine the complete code to understand the FSM and loop logic")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists("debug_array_function.py"):
            os.remove("debug_array_function.py")

if __name__ == "__main__":
    success = generate_and_examine_verilog()
    if success:
        print("\n🎉 Verilog generation and analysis completed!")
        sys.exit(0)
    else:
        print("\n💥 Verilog generation failed!")
        sys.exit(1) 