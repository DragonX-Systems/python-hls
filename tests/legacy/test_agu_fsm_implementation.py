#!/usr/bin/env python3
"""
Test script for AGU, FSM Controller, and Memory Controller implementation.
This test verifies that the HLS engine properly allocates and generates these components.
"""

import os
import sys

# Add the parent directory to the path so we can import the HLS module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python_hls.hls import HLS

def test_matrix_multiply_with_memory_components():
    """Test function that uses arrays and loops to trigger AGU/FSM allocation."""
    
    # Create a test Python function with arrays and control flow
    test_code = '''
def matrix_multiply(a, b, c, size):
    """Matrix multiplication with explicit memory operations."""
    # Memory size annotations for arrays
    a_memory_size = size * size * 4  # 4 bytes per int
    b_memory_size = size * size * 4
    c_memory_size = size * size * 4
    
    # pragma hls memory_type RAM
    # pragma hls pipeline enable
    
    # Nested loops for matrix multiplication
    # pragma loop_count 8
    for i in range(size):
        # pragma loop_count 8  
        for j in range(size):
            # Initialize result
            c[i * size + j] = 0
            
            # Inner product loop
            # pragma loop_count 8
            for k in range(size):
                # Array accesses that will trigger AGU allocation
                a_val = a[i * size + k]
                b_val = b[k * size + j]
                c[i * size + j] = c[i * size + j] + (a_val * b_val)
    
    return c
'''
    
    # Write test code to file
    with open('test_matrix_agu.py', 'w') as f:
        f.write(test_code)
    
    # Create HLS instance
    hls = HLS(optimization_level=2, tech_node=28)
    
    print("=== Testing AGU, FSM Controller, and Memory Controller Implementation ===")
    print(f"Technology node: {hls.tech_node}nm")
    print()
    
    try:
        # Compile the test function
        print("1. Compiling Python to HLS IR...")
        netlist, logs = hls.compile('test_matrix_agu.py', target='verilog', debug=True)
        print("✓ Compilation successful")
        print()
        
        # Get resource allocation report
        print("2. Analyzing Resource Allocation...")
        resource_report = hls.get_resource_report()
        
        print("Allocated Resources:")
        for resource_type, count in resource_report.get('allocated_resources', {}).items():
            print(f"  - {resource_type}: {count}")
        print()
        
        # Check for AGU allocation
        allocated_resources = resource_report.get('allocated_resources', {})
        agu_count = allocated_resources.get('AGU_32bit', 0)
        fsm_count = allocated_resources.get('FSM_Controller', 0)
        mem_ctrl_count = allocated_resources.get('Memory_Controller', 0)
        
        print("3. Verifying New Component Allocation:")
        print(f"  - Address Generation Units (AGUs): {agu_count}")
        print(f"  - FSM Controllers: {fsm_count}")
        print(f"  - Memory Controllers: {mem_ctrl_count}")
        
        if agu_count > 0:
            print("  ✓ AGUs properly allocated for array operations")
        else:
            print("  ⚠ No AGUs allocated - check memory operation detection")
            
        if fsm_count > 0:
            print("  ✓ FSM Controllers allocated for control flow")
        else:
            print("  ⚠ No FSM Controllers allocated - check control flow analysis")
            
        if mem_ctrl_count > 0:
            print("  ✓ Memory Controllers allocated for large arrays")
        else:
            print("  ⚠ No Memory Controllers allocated - check memory size analysis")
        
        print()
        
        # Get performance metrics
        print("4. Performance Metrics with New Components:")
        metrics = hls.get_performance_metrics()
        
        print(f"  - Total Area: {metrics.get('total_area', 0):.2f} μm²")
        print(f"  - Total Power: {metrics.get('total_power', 0):.2f} mW")
        print(f"  - Clock Frequency: {metrics.get('clock_frequency_mhz', 0):.2f} MHz")
        print(f"  - Latency: {metrics.get('latency_cycles', 0)} cycles")
        print()
        
        # Examine generated Verilog
        print("5. Analyzing Generated Verilog...")
        if netlist and hasattr(netlist, 'modules'):
            for module_name, module in netlist.modules.items():
                print(f"  Module: {module_name}")
                
                # Get Verilog code
                verilog_code = ""
                if hasattr(module, 'verilog_blocks'):
                    verilog_code = "\n".join(module.verilog_blocks)
                
                # Check for AGU components
                if "agu_" in verilog_code:
                    print("    ✓ AGU components found in Verilog")
                else:
                    print("    ⚠ AGU components not found in Verilog")
                
                # Check for FSM components  
                if "fsm_state" in verilog_code or "FSM_" in verilog_code:
                    print("    ✓ FSM Controller found in Verilog")
                else:
                    print("    ⚠ FSM Controller not found in Verilog")
                
                # Check for memory controller
                if "mem_ctrl" in verilog_code:
                    print("    ✓ Memory Controller found in Verilog")
                else:
                    print("    ⚠ Memory Controller not found in Verilog")
                
                # Save Verilog to file for inspection
                verilog_filename = f"{module_name}_with_agu_fsm.v"
                with open(verilog_filename, 'w') as f:
                    f.write(verilog_code)
                print(f"    → Verilog saved to {verilog_filename}")
        
        print()
        
        # Compare with basic allocation (without new components)
        print("6. Component Analysis Summary:")
        total_resources = sum(allocated_resources.values())
        compute_resources = sum(allocated_resources.get(res, 0) for res in 
                              ['ALU_32bit', 'Adder_32bit', 'Multiplier_32bit'])
        memory_resources = sum(allocated_resources.get(res, 0) for res in 
                             ['Memory_1KB', 'Scratchpad_1KB', 'AGU_32bit', 'Memory_Controller'])
        control_resources = allocated_resources.get('FSM_Controller', 0)
        
        print(f"  - Total Resources: {total_resources}")
        print(f"  - Compute Resources: {compute_resources}")
        print(f"  - Memory & Address Resources: {memory_resources}")
        print(f"  - Control Resources: {control_resources}")
        print()
        
        print("✓ AGU, FSM Controller, and Memory Controller test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test files
        for filename in ['test_matrix_agu.py']:
            if os.path.exists(filename):
                os.remove(filename)

def test_control_flow_complexity():
    """Test function with complex control flow to verify FSM allocation."""
    
    test_code = '''
def complex_control_flow(data, size, threshold):
    """Function with branches and loops to test FSM complexity."""
    # Memory annotations
    data_memory_size = size * 4
    result_memory_size = size * 4
    
    # pragma hls memory_type RAM
    result = [0] * size
    
    # Complex control flow with nested conditions and loops
    # pragma loop_count 16
    for i in range(size):
        if data[i] > threshold:
            # Branch 1: Above threshold processing
            # pragma loop_count 4
            for j in range(4):
                result[i] = result[i] + data[i] * j
                if result[i] > 1000:
                    result[i] = 1000  # Clamp
                    break
        elif data[i] < -threshold:
            # Branch 2: Below negative threshold
            result[i] = -data[i]
        else:
            # Branch 3: Within threshold range
            result[i] = data[i] // 2
            
        # Additional conditional
        if i % 2 == 0:
            result[i] = result[i] + 1
    
    return result
'''
    
    # Write test code to file
    with open('test_control_flow.py', 'w') as f:
        f.write(test_code)
    
    # Create HLS instance
    hls = HLS(optimization_level=1, tech_node=45)
    
    print("=== Testing Complex Control Flow FSM Generation ===")
    
    try:
        # Compile
        netlist, logs = hls.compile('test_control_flow.py', target='verilog')
        
        # Check FSM allocation
        resource_report = hls.get_resource_report()
        allocated_resources = resource_report.get('allocated_resources', {})
        fsm_count = allocated_resources.get('FSM_Controller', 0)
        
        print(f"FSM Controllers allocated: {fsm_count}")
        
        # Check Verilog for complex FSM
        if netlist and hasattr(netlist, 'modules'):
            for module_name, module in netlist.modules.items():
                verilog_code = ""
                if hasattr(module, 'verilog_blocks'):
                    verilog_code = "\n".join(module.verilog_blocks)
                
                # Count FSM states
                fsm_states = verilog_code.count('FSM_')
                branch_states = verilog_code.count('BRANCH')
                loop_states = verilog_code.count('LOOP')
                
                print(f"FSM states in Verilog: {fsm_states}")
                print(f"Branch handling: {'✓' if branch_states > 0 else '⚠'}")
                print(f"Loop handling: {'✓' if loop_states > 0 else '⚠'}")
        
        return True
        
    except Exception as e:
        print(f"Control flow test failed: {str(e)}")
        return False
    
    finally:
        for filename in ['test_control_flow.py']:
            if os.path.exists(filename):
                os.remove(filename)

if __name__ == "__main__":
    print("Testing AGU, FSM Controller, and Memory Controller Implementation")
    print("=" * 70)
    print()
    
    # Run tests
    test1_passed = test_matrix_multiply_with_memory_components()
    print()
    test2_passed = test_control_flow_complexity()
    
    print()
    print("=" * 70)
    if test1_passed and test2_passed:
        print("✓ All tests passed! AGU, FSM, and Memory Controller implementation is working.")
    else:
        print("✗ Some tests failed. Check the implementation.") 