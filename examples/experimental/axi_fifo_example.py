"""
Example demonstrating AXI-Stream and AXI-Lite interfaces with FIFOs in python_hls.
"""

import numpy as np

def axi_stream_fifo_example(data, size):
    """
    Function demonstrating AXI-Stream interface with FIFOs.
    
    Args:
        data: Input data array
        size: Size of the data array
        
    Returns:
        Processed output data
    """
    # Define a FIFO with AXI-Stream interface
    # pragma hls fifo axis_fifo(depth=32, width=32, input_interface="axis", output_interface="axis", axis_tlast=True, axis_tkeep=True)
    
    # Define streaming interfaces
    # pragma hls stream input_stream(direction=in, protocol="axis", tkeep=True, tlast=True)
    # pragma hls stream output_stream(direction=out, protocol="axis", tkeep=True, tlast=True)
    
    # Initialize input and output buffers
    fifo_buffer = [0] * size
    output = [0] * size
    
    # Write to AXI-Stream FIFO
    for i in range(size):
        fifo_buffer[i] = data[i]
        # pragma hls fifo_write axis_fifo protocol=axis
    
    # Read from AXI-Stream FIFO
    for i in range(size):
        val = fifo_buffer[i]
        # pragma hls fifo_read axis_fifo protocol=axis
        output[i] = val * 2
    
    return output

def axi_lite_fifo_example(data, size):
    """
    Function demonstrating AXI-Lite interface with FIFOs.
    
    Args:
        data: Input data array
        size: Size of the data array
        
    Returns:
        Processed output data
    """
    # Define a FIFO with AXI-Lite interface
    # pragma hls fifo axilite_fifo(depth=16, width=32, input_interface="axilite", output_interface="axilite", axilite_addr_width=32, axilite_has_resp=True)
    
    # Define AXI-Lite interfaces for control
    # pragma hls interface s_axilite port=size
    # pragma hls interface s_axilite port=return
    
    # Initialize input and output buffers
    fifo_buffer = [0] * size
    output = [0] * size
    
    # Write to AXI-Lite FIFO
    for i in range(size):
        fifo_buffer[i] = data[i]
        # pragma hls fifo_write axilite_fifo protocol=axilite
    
    # Read from AXI-Lite FIFO
    for i in range(size):
        val = fifo_buffer[i]
        # pragma hls fifo_read axilite_fifo protocol=axilite
        output[i] = val * 2
    
    return output

def mixed_interfaces_example(data, size):
    """
    Function demonstrating mixed interfaces (AXI-Stream input, AXI-Lite output).
    
    Args:
        data: Input data array
        size: Size of the data array
        
    Returns:
        Processed output data
    """
    # Define a FIFO with mixed interfaces
    # pragma hls fifo mixed_fifo(depth=32, width=32, input_interface="axis", output_interface="axilite", 
    #                           axis_tlast=True, axilite_addr_width=32)
    
    # Define control interface
    # pragma hls interface s_axilite port=size
    # pragma hls interface s_axilite port=return
    
    # Define streaming interfaces
    # pragma hls stream input_stream(direction=in, protocol="axis", tlast=True)
    
    # Initialize input and output buffers
    fifo_buffer = [0] * size
    output = [0] * size
    
    # Write to FIFO using AXI-Stream interface
    for i in range(size):
        fifo_buffer[i] = data[i]
        # pragma hls fifo_write mixed_fifo protocol=axis
    
    # Read from FIFO using AXI-Lite interface
    for i in range(size):
        val = fifo_buffer[i]
        # pragma hls fifo_read mixed_fifo protocol=axilite
        output[i] = val * 2
    
    return output

if __name__ == "__main__":
    test_data = [1, 2, 3, 4, 5, 6, 7, 8]
    size = len(test_data)
    
    # Test AXI-Stream FIFO
    axis_result = axi_stream_fifo_example(test_data, size)
    print("AXI-Stream FIFO result:", axis_result)
    
    # Test AXI-Lite FIFO
    axilite_result = axi_lite_fifo_example(test_data, size)
    print("AXI-Lite FIFO result:", axilite_result)
    
    # Test mixed interfaces
    mixed_result = mixed_interfaces_example(test_data, size)
    print("Mixed interfaces result:", mixed_result) 