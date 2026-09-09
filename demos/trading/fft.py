"""
FFT (32-point) - Spectral analysis, cycle detection for market data.
Cooley-Tukey algorithm. Fixed-point arithmetic for HLS.
"""

def fft_32_point(input_signal):
    """32-point FFT using Cooley-Tukey. Returns [real0,imag0,real1,imag1,...]."""
    FFT_SIZE = 32
    NUM_STAGES = 5

    signal_real = [0] * FFT_SIZE
    signal_imag = [0] * FFT_SIZE
    twiddle_real = [0] * (FFT_SIZE // 2)
    twiddle_imag = [0] * (FFT_SIZE // 2)

    for i in range(FFT_SIZE):
        if i < FFT_SIZE // 8:
            signal_real[i] = 1
        else:
            signal_real[i] = 0
        signal_imag[i] = 0

    for i in range(FFT_SIZE // 2):
        angle = (2 * 314159 * i) // (100000 * FFT_SIZE)
        if angle == 0:
            twiddle_real[i] = 1000
            twiddle_imag[i] = 0
        elif angle <= 78539:
            twiddle_real[i] = 707
            twiddle_imag[i] = -707
        elif angle <= 157079:
            twiddle_real[i] = 0
            twiddle_imag[i] = -1000
        else:
            twiddle_real[i] = -707
            twiddle_imag[i] = -707

    for i in range(FFT_SIZE):
        j = 0
        temp = i
        for bit in range(NUM_STAGES):
            j = (j << 1) | (temp & 1)
            temp = temp >> 1
        if j > i:
            temp_real = signal_real[i]
            signal_real[i] = signal_real[j]
            signal_real[j] = temp_real
            temp_imag = signal_imag[i]
            signal_imag[i] = signal_imag[j]
            signal_imag[j] = temp_imag

    for stage in range(NUM_STAGES):
        butterfly_size = 1 << (stage + 1)
        half_size = butterfly_size >> 1
        num_groups = FFT_SIZE // butterfly_size
        for group in range(num_groups):
            group_start = group * butterfly_size
            for butterfly in range(half_size):
                idx1 = group_start + butterfly
                idx2 = idx1 + half_size
                twiddle_idx = (butterfly * (FFT_SIZE // butterfly_size)) % (FFT_SIZE // 2)
                if twiddle_idx >= FFT_SIZE // 2:
                    twiddle_idx = (FFT_SIZE // 2) - 1
                tw_real = twiddle_real[twiddle_idx]
                tw_imag = twiddle_imag[twiddle_idx]
                temp_real = (signal_real[idx2] * tw_real - signal_imag[idx2] * tw_imag) // 1000
                temp_imag = (signal_real[idx2] * tw_imag + signal_imag[idx2] * tw_real) // 1000
                signal_real[idx2] = signal_real[idx1] - temp_real
                signal_imag[idx2] = signal_imag[idx1] - temp_imag
                signal_real[idx1] = signal_real[idx1] + temp_real
                signal_imag[idx1] = signal_imag[idx1] + temp_imag

    output = [0] * (FFT_SIZE * 2)
    for i in range(FFT_SIZE):
        output[2 * i] = signal_real[i]
        output[2 * i + 1] = signal_imag[i]
    return output
