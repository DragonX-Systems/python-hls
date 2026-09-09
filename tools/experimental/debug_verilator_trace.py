#!/usr/bin/env python3
"""
Debug script using Verilator with VCD tracing to analyze loop counter timing issues.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS
from python_hls.verification.testbench_generator import TestbenchGenerator
import logging
import tempfile
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_array_sum_with_verilator():
    """Debug array sum function using Verilator with VCD tracing."""
    print("=" * 60)
    print("Debugging Array Sum with Verilator VCD Tracing")
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
        
        # Extract port information
        port_info = hls.rtl_verifier._extract_module_port_info(main_module)
        print(f"✅ Extracted port info: {len(port_info.get('input_ports', []))} inputs, {len(port_info.get('output_ports', []))} outputs")
        
        # Create test vectors - focus on the problematic case
        test_vectors = [
            {"data": [100, 200, 300]},  # Should return 600, but RTL returns 200
            {"data": [5, 10]},          # Should return 15, but RTL returns 10
            {"data": [42]},             # Should return 42 (works correctly)
            {"data": []},               # Should return 0 (works correctly)
        ]
        
        # Create enhanced testbench generator with debugging
        testbench_gen = TestbenchGenerator(enable_debug=True, enable_vcd_trace=True)
        
        # Generate debug C++ testbench
        print("🔧 Generating debug C++ testbench...")
        cpp_testbench_path = testbench_gen.generate_cpp_debug_testbench(
            main_module, port_info, test_vectors, "debug_array_sum"
        )
        
        print(f"✅ Generated debug C++ testbench: {cpp_testbench_path}")
        
        # Generate Verilog files
        print("🔧 Generating Verilog files...")
        verilog_files = []
        for module_name, module in modules.items():
            # Use the VerilogGenerator to generate Verilog code
            verilog_netlist = hls.verilog_generator.generate(hls.scheduled_ir)
            
            # Extract Verilog code from the netlist
            if hasattr(verilog_netlist, 'modules') and module_name in verilog_netlist.modules:
                netlist_module = verilog_netlist.modules[module_name]
                if hasattr(netlist_module, 'verilog_blocks') and netlist_module.verilog_blocks:
                    verilog_code = netlist_module.verilog_blocks[0]  # Get the first (and usually only) block
                else:
                    print(f"⚠️  No Verilog blocks found for module {module_name}")
                    continue
            else:
                print(f"⚠️  Module {module_name} not found in generated netlist")
                continue
            
            verilog_file = f"{module_name}.v"
            with open(verilog_file, "w") as f:
                f.write(verilog_code)
                f.write("\n")  # Add newline at end of file
            verilog_files.append(verilog_file)
            print(f"  📄 Generated: {verilog_file}")
        
        if not verilog_files:
            print("❌ No Verilog files generated")
            return False
        
        # Compile with Verilator
        print("🔧 Compiling with Verilator...")
        verilator_cmd = [
            "verilator",
            "--cc",
            "--exe",
            "--build",
            "--trace",
            "-CFLAGS", "-std=c++14",
            "-Wall",
            "-Wno-WIDTH",
            "-Wno-UNUSED",
            "-Wno-UNOPTFLAT",
            "-Wno-BLKANDNBLK",
            "-I.", 
            cpp_testbench_path
        ] + verilog_files
        
        try:
            result = subprocess.run(verilator_cmd, capture_output=True, text=True, cwd=".")
            if result.returncode != 0:
                print(f"❌ Verilator compilation failed:")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False
            
            print("✅ Verilator compilation successful")
            
        except FileNotFoundError:
            print("❌ Verilator not found. Please install Verilator first.")
            print("   On macOS: brew install verilator")
            print("   On Ubuntu: sudo apt-get install verilator")
            return False
        
        # Run simulation with VCD trace
        print("🔧 Running simulation with VCD trace...")
        executable = f"./obj_dir/V{main_module.name}"
        
        if not os.path.exists(executable):
            print(f"❌ Executable not found: {executable}")
            return False
        
        # Run with trace enabled
        sim_cmd = [executable, "+trace"]
        try:
            result = subprocess.run(sim_cmd, capture_output=True, text=True, cwd=".")
            
            print("📊 Simulation Output:")
            print(result.stdout)
            
            if result.stderr:
                print("⚠️  Simulation Errors:")
                print(result.stderr)
            
            # Check if VCD file was generated
            vcd_file = "debug_array_sum_debug.vcd"
            if os.path.exists(vcd_file):
                print(f"✅ VCD trace file generated: {vcd_file}")
                print(f"📊 VCD file size: {os.path.getsize(vcd_file)} bytes")
                
                # Provide instructions for viewing the VCD
                print("\n🔍 To view the VCD trace:")
                print(f"   gtkwave {vcd_file}")
                print("\n🎯 Key signals to monitor:")
                print("   - FSM_state: Current FSM state")
                print("   - loop_counter: Loop counter value")
                print("   - data_addr: Array address being accessed")
                print("   - data_data: Array data being read")
                print("   - data_enable: Array enable signal")
                print("   - done: Completion signal")
                
                # Try to analyze the VCD file programmatically
                try:
                    analyze_vcd_file(vcd_file)
                except Exception as e:
                    print(f"⚠️  Could not analyze VCD file: {e}")
                
            else:
                print("❌ VCD trace file not generated")
            
            return True
            
        except Exception as e:
            print(f"❌ Simulation failed: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Debug failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        cleanup_files = [
            "debug_array_function.py",
            "debug_array_sum_debug.vcd",
        ]
        
        # Add cpp_testbench_path to cleanup if it was defined
        if 'cpp_testbench_path' in locals():
            cleanup_files.append(cpp_testbench_path)
        
        for pattern in ["*.v", "obj_dir"]:
            import glob
            if pattern == "obj_dir":
                import shutil
                if os.path.exists("obj_dir"):
                    shutil.rmtree("obj_dir")
            else:
                for file_path in glob.glob(pattern):
                    try:
                        os.remove(file_path)
                    except:
                        pass

def analyze_vcd_file(vcd_file):
    """Analyze VCD file to extract key timing information."""
    print(f"\n🔍 Analyzing VCD file: {vcd_file}")
    
    try:
        # Try to use pyvcd if available
        import vcd
        
        with open(vcd_file, 'rb') as f:
            vcd_reader = vcd.VCDReader(f)
            
            # Find key signals
            key_signals = {}
            for var in vcd_reader.scope.toposort():
                if hasattr(var, 'name'):
                    if var.name in ['FSM_state', 'loop_counter', 'data_addr', 'done']:
                        key_signals[var.name] = var
            
            print(f"📊 Found {len(key_signals)} key signals")
            
            # Track signal changes
            signal_changes = {}
            for timestamp, var, value in vcd_reader:
                if var in key_signals.values():
                    signal_name = var.name
                    if signal_name not in signal_changes:
                        signal_changes[signal_name] = []
                    signal_changes[signal_name].append((timestamp, value))
            
            # Print signal timeline
            print("\n📈 Signal Timeline:")
            for signal_name, changes in signal_changes.items():
                print(f"  {signal_name}:")
                for timestamp, value in changes[:10]:  # Show first 10 changes
                    print(f"    {timestamp}: {value}")
                if len(changes) > 10:
                    print(f"    ... and {len(changes) - 10} more changes")
            
    except ImportError:
        print("⚠️  pyvcd not available for detailed analysis")
        print("   Install with: pip install pyvcd")
        
        # Basic text analysis
        try:
            with open(vcd_file, 'r') as f:
                content = f.read()
                
            # Count signal declarations
            signal_count = content.count('$var')
            print(f"📊 VCD contains {signal_count} signal declarations")
            
            # Look for key signals
            key_signals = ['FSM_state', 'loop_counter', 'data_addr', 'done']
            found_signals = []
            for signal in key_signals:
                if signal in content:
                    found_signals.append(signal)
            
            print(f"🎯 Found key signals: {found_signals}")
            
        except Exception as e:
            print(f"⚠️  Could not perform basic VCD analysis: {e}")

if __name__ == "__main__":
    success = debug_array_sum_with_verilator()
    if success:
        print("\n🎉 Verilator debug session completed!")
        print("📊 Check the generated VCD file for detailed timing analysis")
        sys.exit(0)
    else:
        print("\n💥 Verilator debug session failed!")
        sys.exit(1) 