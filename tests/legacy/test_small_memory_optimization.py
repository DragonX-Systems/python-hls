# Test script for small memory optimization
# Tests that variables <128 bytes use registers instead of scratchpad,
# especially when ports are high (high unroll factors)

def test_small_memory_variables():
    """
    Test function with small memory variables that should use registers
    instead of scratchpad memory, especially under high port pressure.
    """
    
    # Small arrays that should use registers
    small_array_1 = [0] * 16      # 16 * 4 = 64 bytes
    small_array_2 = [0] * 20      # 20 * 4 = 80 bytes  
    small_array_3 = [0] * 30      # 30 * 4 = 120 bytes
    
    # Memory size annotations (all < 128 bytes)
    small_array_1_memory_size = 64   # 64 bytes
    small_array_2_memory_size = 80   # 80 bytes
    small_array_3_memory_size = 120  # 120 bytes
    
    # Medium array at the boundary (should use registers under high port pressure)
    medium_array = [0] * 50       # 50 * 4 = 200 bytes
    medium_array_memory_size = 200
    
    # Large array that should definitely use scratchpad
    large_array = [0] * 1000      # 1000 * 4 = 4000 bytes
    large_array_memory_size = 4000
    
    # High unroll factor loops to create port pressure
    # pragma unroll 8
    for i in range(100):
        # Multiple concurrent memory accesses due to unrolling
        # pragma unroll 4  
        for j in range(16):
            # Access small arrays - should use registers
            small_array_1[j % 16] += i + j
            small_array_2[j % 20] += i * j
            small_array_3[j % 30] += i - j
            
            # Access medium array - should use registers under high port pressure
            medium_array[j % 50] += small_array_1[j % 16]
            
            # Access large array - should use scratchpad regardless
            large_array[j % 1000] += small_array_2[j % 20]
    
    return small_array_1, small_array_2, small_array_3, medium_array, large_array

def test_low_port_pressure():
    """
    Test function with low port pressure where medium variables might use scratchpad.
    """
    
    # Small arrays that should still use registers
    tiny_array = [0] * 8          # 8 * 4 = 32 bytes
    tiny_array_memory_size = 32
    
    # Medium array that might use scratchpad under low pressure
    medium_array = [0] * 40       # 40 * 4 = 160 bytes  
    medium_array_memory_size = 160
    
    # No unroll pragmas - low port pressure
    for i in range(50):
        for j in range(8):
            tiny_array[j] += i
            
        for j in range(40):
            medium_array[j] += tiny_array[j % 8]
    
    return tiny_array, medium_array 