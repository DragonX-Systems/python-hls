#!/usr/bin/env python3
"""
Test script to demonstrate PPA (Power, Performance, Area) optimization functionality.
"""

import os
import sys
import tempfile
from python_hls import HLS

def create_test_function():
    """Create a simple test function for PPA optimization."""
    test_code = """
def matrix_multiply(a, b, c, size):
    '''
    Simple matrix multiplication for PPA optimization testing.
    '''
    # Memory size hints
    a_memory_size = size * size * 4  # 4 bytes per element
    b_memory_size = size * size * 4
    c_memory_size = size * size * 4
    
    # Loop with unrolling pragma
    for i in range(size):
        # pragma: loop_count 16
        for j in range(size):
            # pragma: unroll 2
            temp = 0
            for k in range(size):
                temp += a[i * size + k] * b[k * size + j]
            c[i * size + j] = temp
    
    return c
"""
    
    # Write test code to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_code)
        return f.name

def test_ppa_optimization():
    """Test PPA optimization with different objectives."""
    print("Testing PPA (Power, Performance, Area) Optimization")
    print("=" * 50)
    
    # Create test function
    test_file = create_test_function()
    
    try:
        # Test different PPA objectives
        objectives = ["area", "performance", "power", "balanced"]
        tech_nodes = [45, 28, 16, 7]
        
        for tech_node in tech_nodes:
            print(f"\nTesting Technology Node: {tech_node}nm")
            print("-" * 30)
            
            for objective in objectives:
                print(f"\nTesting {objective.upper()} optimization:")
                
                # Create HLS compiler
                hls = HLS(optimization_level=3, tech_node=tech_node)
                
                try:
                    # Compile with PPA optimization
                    netlist, logs = hls.compile(
                        source_file=test_file,
                        target="verilog",
                        ppa_optimization=True,
                        ppa_objective=objective,
                        entry_function="matrix_multiply"
                    )
                    
                    # Get performance metrics
                    metrics = hls.get_performance_metrics()
                    
                    print(f"  ✓ Compilation successful")
                    print(f"  ✓ Area: {metrics.get('total_area', 0):.2f} μm²")
                    print(f"  ✓ Power: {metrics.get('total_power', 0):.2f} mW")
                    print(f"  ✓ Latency: {metrics.get('latency_cycles', 0)} cycles")
                    print(f"  ✓ Frequency: {metrics.get('clock_frequency_mhz', 0):.2f} MHz")
                    
                    # Get optimization report
                    opt_report = hls.get_optimization_report()
                    applied_opts = len(opt_report.get('applied_optimizations', []))
                    print(f"  ✓ Applied optimizations: {applied_opts}")
                    
                    # Check if PPA-specific optimizations were applied
                    if netlist and hasattr(netlist, 'modules'):
                        module_count = len(netlist.modules)
                        print(f"  ✓ Generated modules: {module_count}")
                        
                        # Check for PPA-specific patterns in generated code
                        for module_name, module in netlist.modules.items():
                            if hasattr(module, 'verilog_blocks') and module.verilog_blocks:
                                code = module.verilog_blocks[0]
                                
                                # Check for objective-specific patterns
                                if objective == "area" and "shared" in code.lower():
                                    print(f"  ✓ Area optimization: Resource sharing detected")
                                elif objective == "performance" and "parallel" in code.lower():
                                    print(f"  ✓ Performance optimization: Parallel execution detected")
                                elif objective == "power" and "gated" in code.lower():
                                    print(f"  ✓ Power optimization: Clock gating detected")
                    
                except Exception as e:
                    print(f"  ✗ Compilation failed: {str(e)}")
                    continue
        
        print(f"\nPPA optimization testing completed successfully!")
        
    finally:
        # Clean up temporary file
        if os.path.exists(test_file):
            os.unlink(test_file)

def compare_standard_vs_ppa():
    """Compare standard compilation vs PPA optimization."""
    print("\nComparing Standard vs PPA Optimization")
    print("=" * 40)
    
    # Create test function
    test_file = create_test_function()
    
    try:
        # Test with 28nm technology node
        tech_node = 28
        
        print(f"Technology Node: {tech_node}nm")
        print("-" * 25)
        
        # Standard compilation
        print("\nStandard Compilation:")
        hls_std = HLS(optimization_level=2, tech_node=tech_node)
        netlist_std, _ = hls_std.compile(
            source_file=test_file,
            target="verilog",
            ppa_optimization=False,
            entry_function="matrix_multiply"
        )
        
        metrics_std = hls_std.get_performance_metrics()
        print(f"  Area: {metrics_std.get('total_area', 0):.2f} μm²")
        print(f"  Power: {metrics_std.get('total_power', 0):.2f} mW")
        print(f"  Latency: {metrics_std.get('latency_cycles', 0)} cycles")
        
        # PPA-optimized compilation (area)
        print("\nPPA-Optimized Compilation (Area):")
        hls_ppa = HLS(optimization_level=3, tech_node=tech_node)
        netlist_ppa, _ = hls_ppa.compile(
            source_file=test_file,
            target="verilog",
            ppa_optimization=True,
            ppa_objective="area",
            entry_function="matrix_multiply"
        )
        
        metrics_ppa = hls_ppa.get_performance_metrics()
        print(f"  Area: {metrics_ppa.get('total_area', 0):.2f} μm²")
        print(f"  Power: {metrics_ppa.get('total_power', 0):.2f} mW")
        print(f"  Latency: {metrics_ppa.get('latency_cycles', 0)} cycles")
        
        # Calculate improvements
        area_improvement = ((metrics_std.get('total_area', 0) - metrics_ppa.get('total_area', 0)) / 
                           max(metrics_std.get('total_area', 1), 1)) * 100
        power_improvement = ((metrics_std.get('total_power', 0) - metrics_ppa.get('total_power', 0)) / 
                            max(metrics_std.get('total_power', 1), 1)) * 100
        
        print(f"\nImprovement with PPA optimization:")
        print(f"  Area: {area_improvement:.1f}%")
        print(f"  Power: {power_improvement:.1f}%")
        
    finally:
        # Clean up temporary file
        if os.path.exists(test_file):
            os.unlink(test_file)

if __name__ == "__main__":
    print("PPA Optimization Test Suite")
    print("=" * 30)
    
    try:
        # Test PPA optimization
        test_ppa_optimization()
        
        # Compare standard vs PPA
        compare_standard_vs_ppa()
        
        print("\n" + "=" * 50)
        print("All tests completed successfully!")
        
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 