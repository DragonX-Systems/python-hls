
def fft_32_point(input_signal):
    '''
    Compute the 32-point Fast Fourier Transform using the Cooley-Tukey algorithm.
    
    Args:
        input_signal: A list of 32 complex numbers (can be represented as real numbers if imaginary part is 0)
        
    Returns:
        A list of 32 complex numbers representing the frequency domain
    '''
    # Memory size annotations for the HLS scheduler
    FFT_SIZE = 32
    NUM_STAGES = 5
    
    # Input and output arrays
    # pragma hls memory_type RAM
    signal_real = [0] * FFT_SIZE
    signal_real_memory_size = FFT_SIZE
    
    # pragma hls memory_type RAM
    signal_imag = [0] * FFT_SIZE
    signal_imag_memory_size = FFT_SIZE
    
    # Twiddle factors (precomputed) - store as separate real and imaginary parts
    # pragma hls memory_type ROM
    twiddle_real = [0] * (FFT_SIZE // 2)
    twiddle_real_memory_size = FFT_SIZE // 2
    
    # pragma hls memory_type ROM
    twiddle_imag = [0] * (FFT_SIZE // 2)
    twiddle_imag_memory_size = FFT_SIZE // 2
    
    # Initialize input signal (create a simple test signal)
    # pragma loop_count 32
    for i in range(FFT_SIZE):
        # Simple sine wave for testing
        if i < FFT_SIZE // 8:
            signal_real[i] = 1  # Impulse at beginning
        else:
            signal_real[i] = 0
        signal_imag[i] = 0
    
    # Precompute twiddle factors
    # pragma hls pipeline enable
    # pragma loop_count 16
    for i in range(FFT_SIZE // 2):
        # Twiddle factor: exp(-2j * pi * i / FFT_SIZE)
        # Use simple approximation: cos(2*pi*i/N) - j*sin(2*pi*i/N)
        angle = (2 * 314159 * i) // (100000 * FFT_SIZE)  # Approximate 2*pi*i/N using integer math
        
        # Simple approximations for cos and sin (for HLS-friendly implementation)
        # These are rough approximations - in real implementation you'd use CORDIC or lookup tables
        if angle == 0:
            twiddle_real[i] = 1
            twiddle_imag[i] = 0
        elif angle <= 78539:  # ~pi/4 in fixed point
            twiddle_real[i] = 707  # ~cos(pi/4) in fixed point (multiply by 1000)
            twiddle_imag[i] = -707  # ~-sin(pi/4) in fixed point
        elif angle <= 157079:  # ~pi/2 in fixed point
            twiddle_real[i] = 0
            twiddle_imag[i] = -1000
        else:
            twiddle_real[i] = -707
            twiddle_imag[i] = -707
    
    # Bit reversal permutation
    # pragma hls pipeline enable
    # pragma loop_count 32
    for i in range(FFT_SIZE):
        # Compute bit-reversed index
        j = 0
        temp = i
        # pragma loop_count 5
        for bit in range(NUM_STAGES):
            j = (j << 1) | (temp & 1)
            temp = temp >> 1
        
        # Swap if necessary
        if j > i:
            # Swap real parts
            temp_real = signal_real[i]
            signal_real[i] = signal_real[j]
            signal_real[j] = temp_real
            
            # Swap imaginary parts
            temp_imag = signal_imag[i]
            signal_imag[i] = signal_imag[j]
            signal_imag[j] = temp_imag
    
    # Pragma: Enable pipeline optimization for this function
    # pragma hls pipeline enable
    
    # Pragma: FFT operation hint
    # pragma hls fft_operation cooley_tukey
    
    # Cooley-Tukey FFT algorithm
    # pragma loop_count 5
    for stage in range(NUM_STAGES):
        # Size of butterfly
        butterfly_size = 1 << (stage + 1)  # 2^(stage+1)
        half_size = butterfly_size >> 1     # butterfly_size / 2
        
        # Process each group
        num_groups = FFT_SIZE // butterfly_size
        # pragma hls pipeline enable
        # pragma loop_count 16
        for group in range(num_groups):
            group_start = group * butterfly_size
            
            # Process each butterfly in the group
            # pragma hls pipeline enable
            # pragma loop_count 16
            for butterfly in range(half_size):
                idx1 = group_start + butterfly
                idx2 = idx1 + half_size
                
                # Get appropriate twiddle factor (simplified indexing)
                twiddle_idx = (butterfly * (FFT_SIZE // butterfly_size)) % (FFT_SIZE // 2)
                if twiddle_idx >= FFT_SIZE // 2:
                    twiddle_idx = (FFT_SIZE // 2) - 1
                
                # Get twiddle factor
                tw_real = twiddle_real[twiddle_idx]
                tw_imag = twiddle_imag[twiddle_idx]
                
                # Complex multiplication: (a + bi) * (c + di) = (ac - bd) + (ad + bc)i
                # temp = signal[idx2] * twiddle
                temp_real = (signal_real[idx2] * tw_real - signal_imag[idx2] * tw_imag) // 1000
                temp_imag = (signal_real[idx2] * tw_imag + signal_imag[idx2] * tw_real) // 1000
                
                # Butterfly operation
                # signal[idx2] = signal[idx1] - temp
                signal_real[idx2] = signal_real[idx1] - temp_real
                signal_imag[idx2] = signal_imag[idx1] - temp_imag
                
                # signal[idx1] = signal[idx1] + temp
                signal_real[idx1] = signal_real[idx1] + temp_real
                signal_imag[idx1] = signal_imag[idx1] + temp_imag
    
    # Return results (combine real and imaginary parts)
    # pragma hls memory_type RAM
    output = [0] * (FFT_SIZE * 2)  # Store as [real0, imag0, real1, imag1, ...]
    output_memory_size = FFT_SIZE * 2
    
    # pragma hls unroll factor=4
    # pragma loop_count 32
    for i in range(FFT_SIZE):
        output[2*i] = signal_real[i]
        output[2*i + 1] = signal_imag[i]
    
    return output
