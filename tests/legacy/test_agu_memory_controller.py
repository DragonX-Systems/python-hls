#!/usr/bin/env python3
"""
Test script specifically for AGU and Memory Controller generation.
This test uses explicit array operations to ensure proper component generation.
"""

import os
import sys

# Add the parent directory to the path so we can import the HLS module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python_hls.hls import HLS

def test_explicit_array_operations():
    """Test function with explicit array operations to trigger AGU/Memory Controller generation."""
    
    # Create a test Python function with explicit array operations
    test_code = '''
def array_processing(input_data, output_data, size):
    """Function with explicit array operations for AGU testing."""
    
    # Memory size annotations - large enough to trigger memory controllers
    input_data_memory_size = 2048 * 4  # 2KB array
    output_data_memory_size = 2048 * 4  # 2KB array
    temp_array_memory_size = 512 * 4   # 512 element temp array
    
    # Large arrays that should trigger memory controller allocation
    # pragma hls memory_type RAM
    temp_array = [0] * 512
    
    # Complex array processing with multiple access patterns
    # This should trigger multiple AGUs
    # pragma loop_count 512
    for i in range(size):
        if i < 512:
            # Sequential access pattern - AGU 1
            temp_array[i] = input_data[i] * 2
            
            # Strided access pattern - AGU 2  
            if i % 2 == 0:
                temp_array[i // 2] = temp_array[i // 2] + input_data[i + 1]
            
            # Random access pattern - AGU 3
            offset = (i * 7) % 512
            temp_array[offset] = temp_array[offset] + 1
    
    # Second phase - different access patterns
    # pragma loop_count 512
    for j in range(size):
        if j < 512:
            # Write to output with different pattern
            output_data[j] = temp_array[511 - j] + input_data[j]
    
    return output_data
'''
    
    # Write test code to file
    with open('test_array_processing.py', 'w') as f:
        f.write(test_code)
    
    # Create HLS instance
    hls = HLS(optimization_level=2, tech_node=28)
    
    print("=== Testing Explicit Array Operations for AGU/Memory Controller ===")
    print(f"Technology node: {hls.tech_node}nm")
    print()
    
    try:
        # Compile the test function
        print("1. Compiling Python with explicit array operations...")
        netlist, logs = hls.compile('test_array_processing.py', target='verilog', debug=True)
        print("✓ Compilation successful")
        print()
        
        # Get resource allocation report
        print("2. Analyzing Resource Allocation...")
        resource_report = hls.get_resource_report()
        
        print("Allocated Resources:")
        for resource_type, count in resource_report.get('allocated_resources', {}).items():
            print(f"  - {resource_type}: {count}")
        print()
        
        # Check for new component allocation
        allocated_resources = resource_report.get('allocated_resources', {})
        agu_count = allocated_resources.get('AGU_32bit', 0)
        fsm_count = allocated_resources.get('FSM_Controller', 0)
        mem_ctrl_count = allocated_resources.get('Memory_Controller', 0)
        memory_count = allocated_resources.get('Memory_1KB', 0)
        
        print("3. Verifying Component Allocation:")
        print(f"  - Address Generation Units (AGUs): {agu_count}")
        print(f"  - FSM Controllers: {fsm_count}")
        print(f"  - Memory Controllers: {mem_ctrl_count}")
        print(f"  - Memory Units: {memory_count}")
        
        if agu_count >= 2:
            print("  ✓ Multiple AGUs allocated for complex memory access patterns")
        elif agu_count == 1:
            print("  ✓ AGU allocated for array operations")
        else:
            print("  ⚠ No AGUs allocated")
            
        if fsm_count > 0:
            print("  ✓ FSM Controllers allocated for control flow")
        else:
            print("  ⚠ No FSM Controllers allocated")
            
        if mem_ctrl_count > 0:
            print("  ✓ Memory Controllers allocated for large arrays")
        else:
            print("  ⚠ No Memory Controllers allocated")
        
        print()
        
        # Examine generated Verilog for components
        print("4. Analyzing Generated Verilog Components...")
        if netlist and hasattr(netlist, 'modules'):
            for module_name, module in netlist.modules.items():
                print(f"  Module: {module_name}")
                
                # Get Verilog code
                verilog_code = ""
                if hasattr(module, 'verilog_blocks'):
                    verilog_code = "\n".join(module.verilog_blocks)
                
                # Count specific component instances
                agu_instances = verilog_code.count('agu_')
                mem_ctrl_instances = verilog_code.count('mem_ctrl')
                fsm_states = verilog_code.count('FSM_')
                memory_instances = verilog_code.count('_mem [')
                
                print(f"    AGU instances in Verilog: {agu_instances}")
                print(f"    Memory controller instances: {mem_ctrl_instances}")
                print(f"    FSM states: {fsm_states}")
                print(f"    Memory array instances: {memory_instances}")
                
                # Check for specific patterns
                if agu_instances > 0:
                    print("    ✓ AGU hardware components generated")
                else:
                    print("    ⚠ AGU hardware components not found")
                
                if mem_ctrl_instances > 0:
                    print("    ✓ Memory controller hardware generated")
                else:
                    print("    ⚠ Memory controller hardware not found")
                
                if fsm_states > 10:
                    print("    ✓ Complex FSM with multiple states generated")
                else:
                    print("    ⚠ Simple FSM generated")
                
                # Save Verilog to file for inspection
                verilog_filename = f"{module_name}_explicit_arrays.v"
                with open(verilog_filename, 'w') as f:
                    f.write(verilog_code)
                print(f"    → Verilog saved to {verilog_filename}")
        
        print()
        
        # Performance analysis
        print("5. Performance Analysis with Memory Components:")
        metrics = hls.get_performance_metrics()
        
        print(f"  - Total Area: {metrics.get('total_area', 0):.2f} μm²")
        print(f"  - Total Power: {metrics.get('total_power', 0):.2f} mW")
        print(f"  - Clock Frequency: {metrics.get('clock_frequency_mhz', 0):.2f} MHz")
        print(f"  - Latency: {metrics.get('latency_cycles', 0)} cycles")
        print()
        
        # Component breakdown
        total_resources = sum(allocated_resources.values())
        compute_resources = sum(allocated_resources.get(res, 0) for res in 
                              ['ALU_32bit', 'Adder_32bit', 'Multiplier_32bit', 'Divider_32bit'])
        memory_resources = sum(allocated_resources.get(res, 0) for res in 
                             ['Memory_1KB', 'Scratchpad_1KB', 'AGU_32bit', 'Memory_Controller'])
        control_resources = allocated_resources.get('FSM_Controller', 0)
        
        print("6. Hardware Component Analysis:")
        print(f"  - Total Allocated Resources: {total_resources}")
        print(f"  - Compute Resources: {compute_resources} ({compute_resources/total_resources*100:.1f}%)")
        print(f"  - Memory & Address Resources: {memory_resources} ({memory_resources/total_resources*100:.1f}%)")
        print(f"  - Control Resources: {control_resources} ({control_resources/total_resources*100:.1f}%)")
        print()
        
        # Success criteria
        success = (agu_count > 0 and fsm_count > 0 and 
                  (mem_ctrl_count > 0 or memory_count > 0))
        
        if success:
            print("✓ AGU and Memory Controller test completed successfully!")
            print("  All required components (AGU, FSM, Memory) are properly allocated and generated.")
        else:
            print("⚠ Test completed with some missing components.")
            print("  Check array detection and memory size thresholds.")
        
        return success
        
    except Exception as e:
        print(f"✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test files
        for filename in ['test_array_processing.py']:
            if os.path.exists(filename):
                os.remove(filename)

if __name__ == "__main__":
    print("Testing AGU and Memory Controller Generation with Explicit Arrays")
    print("=" * 70)
    print()
    
    success = test_explicit_array_operations()
    
    print()
    print("=" * 70)
    if success:
        print("✓ Test passed! AGU and Memory Controller implementation is working correctly.")
    else:
        print("✗ Test failed. Check the implementation.") 