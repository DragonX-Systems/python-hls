# Manual implementations of mathematical functions for HLS synthesis
# No external library dependencies

# Constants
PI = 3.141592653589793

def log2_int_hardware_optimized(n):
    """
    Hardware-optimized integer log2 computation.
    Uses lookup table for common FFT sizes and unrolled logic for synthesis.
    
    For FFT applications, we typically only need log2 of powers of 2:
    log2(256) = 8, log2(128) = 7, log2(64) = 6, etc.
    """
    # Common FFT sizes lookup table (most efficient for hardware)
    # pragma hls memory_type ROM
    if n == 256:
        return 8
    elif n == 128:
        return 7
    elif n == 64:
        return 6
    elif n == 32:
        return 5
    elif n == 16:
        return 4
    elif n == 8:
        return 3
    elif n == 4:
        return 2
    elif n == 2:
        return 1
    elif n == 1:
        return 0
    else:
        # Fallback for non-power-of-2 (unrolled for hardware efficiency)
        # pragma hls unroll complete
        result = 0
        temp_n = n
        
        # Unrolled log2 computation (max 32 bits)
        if temp_n >= (1 << 16):
            result += 16
            temp_n >>= 16
        if temp_n >= (1 << 8):
            result += 8
            temp_n >>= 8
        if temp_n >= (1 << 4):
            result += 4
            temp_n >>= 4
        if temp_n >= (1 << 2):
            result += 2
            temp_n >>= 2
        if temp_n >= (1 << 1):
            result += 1
            temp_n >>= 1
        
        return result

# def log2_int_original(n):
#     """
#     ⚠️ DEPRECATED: Original variable-length loop implementation.
#     Replaced with hardware-optimized version for better synthesis.
#     """
#     result = 0
#     while n > 1:
#         n >>= 1
#         result += 1
#     return result

# Alias for backwards compatibility
log2_int = log2_int_hardware_optimized

# def is_power_of_two(n):
#     """
#     Hardware-optimized check for power of 2.
#     More efficient than using log2 for this check.
#     """
#     # pragma hls inline
#     return n > 0 and (n & (n - 1)) == 0

# def next_power_of_two(n):
#     """
#     Hardware-optimized computation of next power of 2.
#     Useful for padding algorithms to efficient sizes.
#     """
#     if n <= 0:
#         return 1
#     if is_power_of_two(n):
#         return n
    
#     # Unrolled for hardware efficiency
#     # pragma hls unroll complete
#     result = 1
    
#     # Find the next power of 2 (unrolled version)
#     if n > (1 << 16):
#         result = 1 << 17
#     elif n > (1 << 15):
#         result = 1 << 16
#     elif n > (1 << 14):
#         result = 1 << 15
#     elif n > (1 << 13):
#         result = 1 << 14
#     elif n > (1 << 12):
#         result = 1 << 13
#     elif n > (1 << 11):
#         result = 1 << 12
#     elif n > (1 << 10):
#         result = 1 << 11
#     elif n > (1 << 9):
#         result = 1 << 10
#     elif n > (1 << 8):
#         result = 1 << 9
#     elif n > (1 << 7):
#         result = 1 << 8
#     elif n > (1 << 6):
#         result = 1 << 7
#     elif n > (1 << 5):
#         result = 1 << 6
#     elif n > (1 << 4):
#         result = 1 << 5
#     elif n > (1 << 3):
#         result = 1 << 4
#     elif n > (1 << 2):
#         result = 1 << 3
#     elif n > (1 << 1):
#         result = 1 << 2
#     else:
#         result = 1 << 1
    
#     return result

# Pre-computed twiddle factors for 256-point FFT (industry standard approach)
# These would normally be computed offline and stored in ROM
TWIDDLE_FACTORS_256 = [
    (1.0, 0.0), (0.9996988186962042, -0.024541228522912288), (0.9987954562051724, -0.049067674327418015),
    (0.9972904566786902, -0.07356456359966743), (0.9951847266721969, -0.09801714032956077),
    (0.9924795345987100, -0.12241067519921619), (0.9891765099647810, -0.14673047445536175),
    (0.9852776423889412, -0.17096188876030122), (0.9807852804032304, -0.19509032201612825),
    (0.9757021300385286, -0.21910124015686980), (0.9700312531945440, -0.24298017990326387),
    (0.9637760657954398, -0.26671275747489837), (0.9569403357322088, -0.29028467725446233),
    (0.9495281805930367, -0.31368174039889152), (0.9415440651830208, -0.33688985339222005),
    (0.9329927988347388, -0.35989503653498811), (0.9238795325112867, -0.38268343236508978),
    (0.9142097557035307, -0.40524131400498986), (0.9039892931234433, -0.42755509343028208),
    (0.8932243011955153, -0.44961132965460654), (0.8819212643483549, -0.47139673682599764),
    (0.8700869911087113, -0.49289819222978404), (0.8577286100002721, -0.51410274419322166),
    (0.8448535652497072, -0.53499761988709715), (0.8314696123025452, -0.55557023301960218),
    (0.8175848131515837, -0.57580819141784534), (0.8032075314806448, -0.59569930449243336),
    (0.7883464276266062, -0.61523159058062682), (0.7730104533627370, -0.63439328416364549),
    (0.7572088465064845, -0.65317284295377676), (0.7409511253549590, -0.67155895484701833),
    (0.7242470829514669, -0.68954054473706683), (0.7071067811865476, -0.70710678118654746),
    (0.6895405447370668, -0.72424708295146689), (0.6715589548470183, -0.74095112535495911),
    (0.6531728429537768, -0.75720884650648446), (0.6343932841636455, -0.77301045336273699),
    (0.6152315905806268, -0.78834642762660623), (0.5956993044924334, -0.80320753148064494),
    (0.5758081914178453, -0.81758481315158371), (0.5555702330196022, -0.83146961230254524),
    (0.5349976198870972, -0.84485356524970711), (0.5141027441932217, -0.85772861000027212),
    (0.4928981922297841, -0.87008699110871135), (0.4713967368259976, -0.88192126434835505),
    (0.4496113296546065, -0.89322430119551532), (0.4275550934302821, -0.90398929312344334),
    (0.4052413140049899, -0.91420975570353069), (0.3826834323650898, -0.92387953251128674),
    (0.3598950365349881, -0.93299279883473885), (0.3368898533922200, -0.94154406518302081),
    (0.3136817403988915, -0.94952818059303667), (0.2902846772544623, -0.95694033573220894),
    (0.2667127574748984, -0.96377606579543984), (0.2429801799032639, -0.97003125319454397),
    (0.2191012401568698, -0.97570213003852857), (0.1950903220161283, -0.98078528040323043),
    (0.1709618887603012, -0.98527764238894122), (0.1467304744553617, -0.98917650996478101),
    (0.1224106751992162, -0.99247953459870997), (0.0980171403295606, -0.99518472667219693),
    (0.0735645635996674, -0.99729045667869021), (0.0490676743274180, -0.99879545620517241),
    (0.0245412285229123, -0.99969881869620425), (0.0000000000000000, -1.00000000000000000),
    (-0.0245412285229122, -0.99969881869620425), (-0.0490676743274180, -0.99879545620517241),
    (-0.0735645635996674, -0.99729045667869021), (-0.0980171403295606, -0.99518472667219693),
    (-0.1224106751992162, -0.99247953459870997), (-0.1467304744553617, -0.98917650996478101),
    (-0.1709618887603012, -0.98527764238894122), (-0.1950903220161283, -0.98078528040323043),
    (-0.2191012401568698, -0.97570213003852857), (-0.2429801799032639, -0.97003125319454397),
    (-0.2667127574748984, -0.96377606579543984), (-0.2902846772544623, -0.95694033573220894),
    (-0.3136817403988915, -0.94952818059303667), (-0.3368898533922200, -0.94154406518302081),
    (-0.3598950365349881, -0.93299279883473885), (-0.3826834323650898, -0.92387953251128674),
    (-0.4052413140049899, -0.91420975570353069), (-0.4275550934302821, -0.90398929312344334),
    (-0.4496113296546065, -0.89322430119551532), (-0.4713967368259976, -0.88192126434835505),
    (-0.4928981922297841, -0.87008699110871135), (-0.5141027441932217, -0.85772861000027212),
    (-0.5349976198870972, -0.84485356524970711), (-0.5555702330196022, -0.83146961230254524),
    (-0.5758081914178453, -0.81758481315158371), (-0.5956993044924334, -0.80320753148064494),
    (-0.6152315905806268, -0.78834642762660623), (-0.6343932841636455, -0.77301045336273699),
    (-0.6531728429537768, -0.75720884650648446), (-0.6715589548470183, -0.74095112535495911),
    (-0.6895405447370668, -0.72424708295146689), (-0.7071067811865476, -0.70710678118654746),
    (-0.7242470829514669, -0.68954054473706683), (-0.7409511253549590, -0.67155895484701833),
    (-0.7572088465064845, -0.65317284295377676), (-0.7730104533627370, -0.63439328416364549),
    (-0.7883464276266062, -0.61523159058062682), (-0.8032075314806448, -0.59569930449243336),
    (-0.8175848131515837, -0.57580819141784534), (-0.8314696123025452, -0.55557023301960218),
    (-0.8448535652497072, -0.53499761988709715), (-0.8577286100002721, -0.51410274419322166),
    (-0.8700869911087113, -0.49289819222978404), (-0.8819212643483549, -0.47139673682599764),
    (-0.8932243011955153, -0.44961132965460654), (-0.9039892931234433, -0.42755509343028208),
    (-0.9142097557035307, -0.40524131400498986), (-0.9238795325112867, -0.38268343236508978),
    (-0.9329927988347388, -0.35989503653498811), (-0.9415440651830208, -0.33688985339222005),
    (-0.9495281805930367, -0.31368174039889152), (-0.9569403357322088, -0.29028467725446233),
    (-0.9637760657954398, -0.26671275747489837), (-0.9700312531945440, -0.24298017990326387),
    (-0.9757021300385286, -0.21910124015686980), (-0.9807852804032304, -0.19509032201612825),
    (-0.9852776423889412, -0.17096188876030122), (-0.9891765099647810, -0.14673047445536175),
    (-0.9924795345987100, -0.12241067519921619), (-0.9951847266721969, -0.09801714032956077),
    (-0.9972904566786902, -0.07356456359966743), (-0.9987954562051724, -0.049067674327418015),
    (-0.9996988186962042, -0.024541228522912288), (-1.0000000000000000, -0.000000000000000000)
]

def main(input_data):
    """
    Hardware-optimized 256-point FFT using pre-computed twiddle factors.
    This eliminates the catastrophic Taylor series computation.
    
    Args:
        input_data: A list of 256 numbers (real or tuples of (real, imag))
        
    Returns:
        A list of 256 tuples representing complex numbers (real, imag)
    """
    # Memory size annotations for the HLS scheduler
    FFT_SIZE = 256
    
    # Output array - single buffer approach
    # pragma hls memory_type RAM
    samples = [(0.0, 0.0)] * FFT_SIZE
    
    # Copy input with bit reversal (optimized)
    # pragma hls pipeline enable
    # pragma loop_count 256
    for i in range(FFT_SIZE):
        # Optimized bit reversal using lookup or hardcoded mapping
        reversed_i = ((i & 0x01) << 7) | ((i & 0x02) << 5) | ((i & 0x04) << 3) | \
                     ((i & 0x08) << 1) | ((i & 0x10) >> 1) | ((i & 0x20) >> 3) | \
                     ((i & 0x40) >> 5) | ((i & 0x80) >> 7)
        
        if isinstance(input_data[i], tuple) and len(input_data[i]) == 2:
            samples[reversed_i] = (float(input_data[i][0]), float(input_data[i][1]))
        else:
            samples[reversed_i] = (float(input_data[i]), 0.0)
    
    # Hardware-optimized FFT computation
    # Stage 1: 2-point butterflies (no twiddle factors needed)
    # pragma hls pipeline enable
    # pragma loop_count 128
    for i in range(0, FFT_SIZE, 2):
        temp_real, temp_imag = samples[i]
        w1_real, w1_imag = samples[i+1]
        
        samples[i] = complex_add(temp_real, temp_imag, w1_real, w1_imag)
        samples[i+1] = complex_sub(temp_real, temp_imag, w1_real, w1_imag)
    
    # Subsequent stages with pre-computed twiddle factors
    # pragma loop_count 7  # Stages 2-8
    for stage in range(1, 8):
        butterfly_size = 1 << (stage + 1)  # 2^(stage + 1)
        half_size = butterfly_size >> 1     # butterfly_size // 2
        twiddle_step = FFT_SIZE >> (stage + 1)  # Twiddle factor step
        
        # Process each group
        # pragma hls pipeline enable
        # pragma loop_count 18
        for group in range(FFT_SIZE >> (stage + 1)):
            group_start = group * butterfly_size
            
            # Process each butterfly in the group
            # pragma loop_count 36
            for butterfly in range(half_size):
                idx1 = group_start + butterfly
                idx2 = idx1 + half_size
                
                # Use pre-computed twiddle factor (HUGE PERFORMANCE GAIN!)
                twiddle_idx = (butterfly * twiddle_step) % (FFT_SIZE // 2)
                twiddle_real, twiddle_imag = TWIDDLE_FACTORS_256[twiddle_idx]
                
                # Get values
                w1_real, w1_imag = samples[idx1]
                w2_real, w2_imag = samples[idx2]
                
                # Butterfly operation
                temp_real, temp_imag = complex_mult(w2_real, w2_imag, twiddle_real, twiddle_imag)
                samples[idx2] = complex_sub(w1_real, w1_imag, temp_real, temp_imag)
                samples[idx1] = complex_add(w1_real, w1_imag, temp_real, temp_imag)
    
    return samples

# Legacy functions kept for backwards compatibility but marked as deprecated
# def sin_taylor(x):
#     """⚠️ DEPRECATED: Catastrophically slow for hardware - use lookup tables instead"""
#     pass

# def cos_taylor(x):
#     """⚠️ DEPRECATED: Catastrophically slow for hardware - use lookup tables instead"""
#     pass

# def complex_exp(angle):
#     """⚠️ DEPRECATED: Use pre-computed twiddle factors instead"""
#     pass

def complex_mult(a_real, a_imag, b_real, b_imag):
    """Multiply two complex numbers: (a_real + i*a_imag) * (b_real + i*b_imag)"""
    real_part = a_real * b_real - a_imag * b_imag
    imag_part = a_real * b_imag + a_imag * b_real
    return (real_part, imag_part)

def complex_add(a_real, a_imag, b_real, b_imag):
    """Add two complex numbers"""
    return (a_real + b_real, a_imag + b_imag)

def complex_sub(a_real, a_imag, b_real, b_imag):
    """Subtract two complex numbers"""
    return (a_real - b_real, a_imag - b_imag)

# def fft_256_point(input_data):
#     """
#     Compute the 256-point Fast Fourier Transform using the Cooley-Tukey algorithm.
#     No external math libraries - all functions implemented manually for HLS synthesis.
    
#     Args:
#         input_data: A list of 256 numbers (real or tuples of (real, imag))
        
#     Returns:
#         A list of 256 tuples representing complex numbers (real, imag)
#     """
#     # Memory size annotations for the HLS scheduler
#     FFT_SIZE = 256
#     input_memory_size = FFT_SIZE  # 256 complex values
    
#     # Convert input to complex representation (real, imag)
#     samples = [(0.0, 0.0)] * FFT_SIZE
#     for i in range(FFT_SIZE):
#         x = input_data[i]
#         if isinstance(x, tuple) and len(x) == 2:
#             samples[i] = (float(x[0]), float(x[1]))
#         else:
#             samples[i] = (float(x), 0.0)
    
#     # Output array
#     # pragma hls memory_type RAM
#     output = [(0.0, 0.0)] * FFT_SIZE
#     output_memory_size = FFT_SIZE  # 256 complex values
    
#     # Bit reversal permutation
#     # pragma hls function_inline
#     def bit_reversal_permutation(data):
#         n = len(data)
#         # Number of bits needed to represent indices (log2(256) = 8)
#         num_bits = log2_int(n)
        
#         # pragma hls pipeline enable
#         # pragma loop_count 256
#         for i in range(n):
#             # Reverse the bits of i
#             reversed_i = 0
#             # pragma loop_count 8
#             for j in range(num_bits):
#                 if (i & (1 << j)):
#                     reversed_i |= (1 << (num_bits - 1 - j))
            
#             # Swap data[i] and data[reversed_i] if reversed_i < i
#             if reversed_i < i:
#                 data[i], data[reversed_i] = data[reversed_i], data[i]
        
#         return data
    
#     # Perform the bit reversal
#     samples = bit_reversal_permutation(samples)
    
#     # Cooley-Tukey FFT algorithm
#     n = len(samples)
    
#     # Log2(n) stages (8 stages for 256-point FFT)
#     num_stages = log2_int(n)
#     # pragma loop_count 8
#     for stage in range(num_stages):
#         # Size of butterfly
#         butterfly_size = 1 << (stage + 1)  # 2^(stage + 1)
#         # Twiddle factor step
#         twiddle_step = n // butterfly_size
        
#         # Process each group
#         # pragma hls pipeline enable
#         # pragma loop_count 128
#         for group in range(n // butterfly_size):
#             # Process each butterfly in the group
#             # pragma loop_count 2
#             for butterfly in range(butterfly_size // 2):
#                 # Indices of the two elements to combine
#                 idx1 = group * butterfly_size + butterfly
#                 idx2 = idx1 + butterfly_size // 2
                
#                 # Twiddle factor: e^(-2*pi*i*butterfly*twiddle_step/n)
#                 angle = -2.0 * PI * butterfly * twiddle_step / n
#                 twiddle_real, twiddle_imag = complex_exp(angle)
                
#                 # Get values
#                 s1_real, s1_imag = samples[idx1]
#                 s2_real, s2_imag = samples[idx2]
                
#                 # Butterfly operation: temp = samples[idx2] * twiddle
#                 temp_real, temp_imag = complex_mult(s2_real, s2_imag, twiddle_real, twiddle_imag)
                
#                 # samples[idx2] = samples[idx1] - temp
#                 samples[idx2] = complex_sub(s1_real, s1_imag, temp_real, temp_imag)
                
#                 # samples[idx1] = samples[idx1] + temp
#                 samples[idx1] = complex_add(s1_real, s1_imag, temp_real, temp_imag)
    
#     # Copy to output
#     # pragma hls unroll factor=4
#     # pragma loop_count 256
#     for i in range(n):
#         output[i] = samples[i]
    
#     return output

# def fft_optimized_256_point(input_data):
#     """
#     Optimized version of the 256-point FFT for HLS.
#     Manual implementation without math/cmath libraries.
    
#     Args:
#         input_data: A list of 256 numbers (real or tuples of (real, imag))
        
#     Returns:
#         A list of 256 tuples representing complex numbers (real, imag)
#     """
#     # Memory size annotations for the HLS scheduler
#     FFT_SIZE = 256
#     input_memory_size = FFT_SIZE  # 256 complex values
    
#     # Twiddle factors (precomputed)
#     # pragma hls memory_type ROM
#     twiddle_factors = [(0.0, 0.0)] * (FFT_SIZE // 2)  # We need at most n/2 twiddle factors
#     twiddle_memory_size = FFT_SIZE // 2  # 128 complex values
    
#     # Precompute twiddle factors
#     # pragma hls pipeline enable
#     # pragma loop_count 128
#     for i in range(FFT_SIZE // 2):
#         angle = -2.0 * PI * i / FFT_SIZE
#         twiddle_factors[i] = complex_exp(angle)
    
#     # Output array
#     # pragma hls memory_type RAM
#     output = [(0.0, 0.0)] * FFT_SIZE
#     output_memory_size = FFT_SIZE  # 256 complex values
    
#     # Initialize work array with input
#     # pragma hls memory_type RAM
#     samples = [(0.0, 0.0)] * FFT_SIZE
#     samples_memory_size = FFT_SIZE  # 256 complex values
    
#     # Copy input to work array with bit reversal
#     # pragma hls pipeline enable
#     # pragma loop_count 256
#     for i in range(FFT_SIZE):
#         # Compute bit-reversed index (hardcoded for 8 bits)
#         reversed_i = ((i & 0x01) << 7) | ((i & 0x02) << 5) | ((i & 0x04) << 3) | \
#                      ((i & 0x08) << 1) | ((i & 0x10) >> 1) | ((i & 0x20) >> 3) | \
#                      ((i & 0x40) >> 5) | ((i & 0x80) >> 7)
        
#         # Copy with bit reversal
#         if isinstance(input_data[i], tuple) and len(input_data[i]) == 2:
#             samples[reversed_i] = (float(input_data[i][0]), float(input_data[i][1]))
#         else:
#             samples[reversed_i] = (float(input_data[i]), 0.0)
    
#     # Cooley-Tukey FFT algorithm - optimized for HLS
#     # Stage 1: Butterfly with size=2
#     # pragma hls pipeline enable
#     # pragma loop_count 128
#     for i in range(0, FFT_SIZE, 2):
#         # No twiddle factor needed for first stage
#         temp_real, temp_imag = samples[i]
#         w1_real, w1_imag = samples[i+1]
        
#         samples[i] = complex_add(temp_real, temp_imag, w1_real, w1_imag)
#         samples[i+1] = complex_sub(temp_real, temp_imag, w1_real, w1_imag)
    
#     # Stage 2: Butterfly with size=4
#     # pragma hls pipeline enable
#     # pragma loop_count 64
#     for i in range(0, FFT_SIZE, 4):
#         # First butterfly in group (twiddle = 1)
#         temp1_real, temp1_imag = samples[i]
#         temp2_real, temp2_imag = samples[i+2]
#         samples[i] = complex_add(temp1_real, temp1_imag, temp2_real, temp2_imag)
#         samples[i+2] = complex_sub(temp1_real, temp1_imag, temp2_real, temp2_imag)
        
#         # Second butterfly in group (twiddle = -j = (0, -1))
#         temp1_real, temp1_imag = samples[i+1]
#         w3_real, w3_imag = samples[i+3]
#         # Multiply by -j: (a + bi) * (-j) = b - ai
#         temp2_real, temp2_imag = complex_mult(w3_real, w3_imag, 0.0, -1.0)
#         samples[i+1] = complex_add(temp1_real, temp1_imag, temp2_real, temp2_imag)
#         samples[i+3] = complex_sub(temp1_real, temp1_imag, temp2_real, temp2_imag)
    
#     # Stages 3-8: General case
#     # pragma loop_count 6
#     for stage in range(2, 8):
#         # Size of butterfly
#         butterfly_size = 1 << (stage + 1)  # 2^(stage + 1)
#         half_size = butterfly_size >> 1     # butterfly_size // 2
        
#         # Process each group
#         # pragma hls pipeline enable
#         # pragma loop_count 64
#         for group in range(FFT_SIZE >> (stage + 1)):  # FFT_SIZE // butterfly_size
#             group_start = group * butterfly_size
            
#             # Process each butterfly in the group
#             # pragma loop_count 32
#             for butterfly in range(half_size):
#                 idx1 = group_start + butterfly
#                 idx2 = idx1 + half_size
                
#                 # Get appropriate twiddle factor
#                 twiddle_idx = (butterfly * (FFT_SIZE >> (stage + 1))) & (FFT_SIZE // 2 - 1)  # % (FFT_SIZE // 2)
#                 twiddle_real, twiddle_imag = twiddle_factors[twiddle_idx]
                
#                 # Get values
#                 w1_real, w1_imag = samples[idx1]
#                 w2_real, w2_imag = samples[idx2]
                
#                 # Butterfly operation
#                 temp_real, temp_imag = complex_mult(w2_real, w2_imag, twiddle_real, twiddle_imag)
#                 samples[idx2] = complex_sub(w1_real, w1_imag, temp_real, temp_imag)
#                 samples[idx1] = complex_add(w1_real, w1_imag, temp_real, temp_imag)
    
#     # Copy to output
#     # pragma hls unroll factor=4
#     # pragma loop_count 256
#     for i in range(FFT_SIZE):
#         output[i] = samples[i]
    
#     return output

# def test_fft():
#     """Test the FFT implementations with example data"""
#     # Test with a simple 8-point input for smaller FFT
#     test_input_8 = [1, 0, 0, 0, 0, 0, 0, 0]
    
#     # Define a small 8-point FFT function for testing
#     def fft_8_point(input_data):
#         # Similar to 256-point but with n=8
#         n = 8
#         samples = [(0.0, 0.0)] * 8
#         for i in range(8):
#             x = input_data[i]
#             if isinstance(x, tuple) and len(x) == 2:
#                 samples[i] = (float(x[0]), float(x[1]))
#             else:
#                 samples[i] = (float(x), 0.0)
        
#         # Bit reversal
#         for i in range(n):
#             j = 0
#             for k in range(3):  # log2(8) = 3
#                 j = (j << 1) | ((i >> k) & 1)
#             if j < i:
#                 samples[i], samples[j] = samples[j], samples[i]
        
#         # FFT computation
#         for stage in range(3):  # log2(8) = 3
#             m = 1 << (stage + 1)  # 2^(stage + 1)
#             for k in range(0, n, m):
#                 for j in range(m >> 1):  # m // 2
#                     angle = -2.0 * PI * j / m
#                     twiddle_real, twiddle_imag = complex_exp(angle)
                    
#                     a_real, a_imag = samples[k + j]
#                     b_real, b_imag = samples[k + j + (m >> 1)]
                    
#                     b_tw_real, b_tw_imag = complex_mult(b_real, b_imag, twiddle_real, twiddle_imag)
                    
#                     samples[k + j] = complex_add(a_real, a_imag, b_tw_real, b_tw_imag)
#                     samples[k + j + (m >> 1)] = complex_sub(a_real, a_imag, b_tw_real, b_tw_imag)
        
#         return samples
    
#     result_8 = fft_8_point(test_input_8)
    
#     # Create a test case for the 256-point FFT
#     # Using a simple sine wave approximation without math.sin
#     test_256 = [0.0] * 256
#     for i in range(256):
#         # Simple sine approximation: sin(2*pi*i/32)
#         angle = 2.0 * PI * i / 32.0
#         test_256[i] = sin_taylor(angle)
    
#     # Test the 256-point implementations
#     result_256 = fft_256_point(test_256)
#     result_256_opt = fft_optimized_256_point(test_256)
    
#     return result_8, result_256, result_256_opt

# if __name__ == "__main__":
#     test_fft() 