#!/usr/bin/env python3
"""
Simple test for the small memory optimization.
Tests the allocator directly without going through the full HLS flow.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from python_hls.ir.ir_nodes import IR, IRFunction, IRVariable, DataType
from python_hls.hls_engine.allocator import Allocator
from python_hls.tech.tech_library import TechLibrary
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def create_test_ir():
    """Create a test IR with various sized variables."""
    ir = IR()
    
    # Create a test function
    func = IRFunction(name="test_function", node_id=1)
    
    # Small variables that should use registers
    small_var1 = IRVariable(
        name="small_array_1",
        node_id=2,
        data_type=DataType.ARRAY,
        bit_width=32,
        memory_size=16  # 16 * 32 bits = 512 bits = 64 bytes
    )
    
    small_var2 = IRVariable(
        name="small_array_2", 
        node_id=3,
        data_type=DataType.ARRAY,
        bit_width=32,
        memory_size=24  # 24 * 32 bits = 768 bits = 96 bytes
    )
    
    # Medium variable at boundary (should use registers under high port pressure)
    medium_var = IRVariable(
        name="medium_array",
        node_id=4,
        data_type=DataType.ARRAY,
        bit_width=32,
        memory_size=48  # 48 * 32 bits = 1536 bits = 192 bytes
    )
    
    # Large variable that should use scratchpad
    large_var = IRVariable(
        name="large_array",
        node_id=5,
        data_type=DataType.ARRAY,
        bit_width=32,
        memory_size=1000  # 1000 * 32 bits = 32000 bits = 4000 bytes
    )
    
    # Add variables to function
    func.local_vars["small_array_1"] = small_var1
    func.local_vars["small_array_2"] = small_var2
    func.local_vars["medium_array"] = medium_var
    func.local_vars["large_array"] = large_var
    
    # Set high unroll factor to simulate high port pressure
    func.total_unroll_factor = 8
    func.max_block_unroll = 4
    
    # Add function to IR
    ir.add_function(func)
    
    return ir

def test_small_memory_optimization():
    """Test the small memory optimization."""
    print("🧪 Testing Small Memory Optimization")
    print("=" * 50)
    
    # Create test IR
    ir = create_test_ir()
    
    # Create tech library and allocator
    tech_lib = TechLibrary()
    allocator = Allocator(tech_lib)
    
    # Run allocation
    updated_ir, resources = allocator.allocate(ir, optimization_target="area")
    
    print("\n📊 Allocation Results:")
    print("-" * 30)
    for resource_type, count in resources.items():
        print(f"  {resource_type}: {count}")
    
    print("\n🔍 Variable Memory Allocation Decisions:")
    print("-" * 45)
    
    test_func = updated_ir.functions["test_function"]
    
    for var_name, var in test_func.local_vars.items():
        size_bits = var.bit_width * var.memory_size
        size_bytes = size_bits // 8
        
        is_register = getattr(var, 'is_register', False)
        is_scratchpad = getattr(var, 'is_scratchpad', False)
        
        if is_register:
            allocation_type = "REGISTER ✅"
        elif is_scratchpad:
            allocation_type = "SCRATCHPAD 💾"
        else:
            allocation_type = "DEFAULT ❓"
        
        print(f"  {var_name:15} ({size_bytes:4d} bytes) -> {allocation_type}")
        
        # Verify optimization logic
        if size_bytes < 128:  # Should use registers
            if not is_register:
                print(f"    ❌ ERROR: Small variable should use registers!")
            else:
                print(f"    ✅ Correct: Small variable using registers")
        elif size_bytes >= 4000:  # Should use scratchpad
            if not is_scratchpad:
                print(f"    ❌ ERROR: Large variable should use scratchpad!")
            else:
                print(f"    ✅ Correct: Large variable using scratchpad")
        else:  # Medium size - depends on port pressure
            port_pressure = test_func.total_unroll_factor >= 4
            if port_pressure and size_bytes < 256:
                if not is_register:
                    print(f"    ❌ WARNING: Medium variable should use registers under high port pressure")
                else:
                    print(f"    ✅ Correct: Medium variable using registers under high port pressure")
    
    print(f"\n📈 Port Pressure Analysis:")
    print(f"  Total unroll factor: {test_func.total_unroll_factor}")
    print(f"  Max block unroll: {test_func.max_block_unroll}")
    print(f"  High port pressure: {'Yes' if test_func.total_unroll_factor >= 4 else 'No'}")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_small_memory_optimization() 