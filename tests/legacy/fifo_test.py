"""
Minimal test file for python_hls FIFO and crossbar pragma usage.
"""

def simple_fifo_test(data, size):
    """
    A simple function to test FIFO pragma syntax.
    """
    # Define a FIFO buffer with minimum attributes required
    #pragma hls fifo test_fifo depth=16
    
    # Initialize input and output buffers
    fifo_buffer = [0] * size
    output = [0] * size
    
    # Write to FIFO
    for i in range(size):
        fifo_buffer[i] = data[i]
        #pragma hls fifo_write test_fifo
    
    # Read from FIFO
    for i in range(size):
        val = fifo_buffer[i]
        #pragma hls fifo_read test_fifo
        output[i] = val * 2
    
    return output

def simple_crossbar_test(data, size):
    """
    A simple function to test crossbar pragma syntax.
    """
    # Define a crossbar with minimum attributes required
    #pragma hls crossbar test_crossbar inputs=1 outputs=4
    
    # Initialize input and output buffers
    output = [0] * size
    
    # Route through crossbar
    for i in range(size):
        dest = i % 4  # Route to one of 4 outputs
        #pragma hls crossbar_route test_crossbar input=0 output=dest
        output[i] = data[i] * (dest + 1)
    
    return output

def direct_instantiation_test(data, size):
    """
    Test with direct instantiation of StreamingComponent objects.
    """
    from python_hls.components import FIFO, Crossbar
    
    # Create streaming components directly
    fifo = FIFO(name="direct_fifo", depth=16, width=32)
    crossbar = Crossbar(name="direct_crossbar", inputs=1, outputs=4)
    
    # Initialize buffers
    output = [0] * size
    
    # Process through streaming components
    for i in range(size):
        # Use FIFO
        fifo.write(data[i])
        val = fifo.read()
        
        # Use crossbar
        dest = i % 4
        crossbar.route(input_idx=0, output_idx=dest, value=val)
        output[i] = val * (dest + 1)
    
    return output

if __name__ == "__main__":
    test_data = [1, 2, 3, 4, 5, 6, 7, 8]
    size = len(test_data)
    
    # Test FIFO
    fifo_result = simple_fifo_test(test_data, size)
    print("FIFO test result:", fifo_result)
    
    # Test crossbar
    crossbar_result = simple_crossbar_test(test_data, size)
    print("Crossbar test result:", crossbar_result)
    
    # Test direct instantiation
    direct_result = direct_instantiation_test(test_data, size)
    print("Direct instantiation result:", direct_result) 