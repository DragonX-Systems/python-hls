import os
import sys
import time
import ast
import logging
import copy
import shutil
from pprint import pformat
import unittest

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fft_hls_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("fft_hls_test")

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)   # Add parent directory to path

# Import the HLS class from python_hls
from python_hls import HLS
from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator

def create_fft_code(fft_size):
    """Create FFT code with a given FFT size"""
    # Calculate number of stages for Cooley-Tukey FFT
    import math
    num_stages = int(math.log2(fft_size))
    
    return f"""
def fft_{fft_size}_point(input_signal):
    '''
    Compute the {fft_size}-point Fast Fourier Transform using the Cooley-Tukey algorithm.
    
    Args:
        input_signal: A list of {fft_size} complex numbers (can be represented as real numbers if imaginary part is 0)
        
    Returns:
        A list of {fft_size} complex numbers representing the frequency domain
    '''
    # Memory size annotations for the HLS scheduler
    FFT_SIZE = {fft_size}
    NUM_STAGES = {num_stages}
    
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
    # pragma loop_count {fft_size}
    for i in range(FFT_SIZE):
        # Simple sine wave for testing
        if i < FFT_SIZE // 8:
            signal_real[i] = 1  # Impulse at beginning
        else:
            signal_real[i] = 0
        signal_imag[i] = 0
    
    # Precompute twiddle factors
    # pragma hls pipeline enable
    # pragma loop_count {fft_size // 2}
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
    # pragma loop_count {fft_size}
    for i in range(FFT_SIZE):
        # Compute bit-reversed index
        j = 0
        temp = i
        # pragma loop_count {num_stages}
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
    # pragma loop_count {num_stages}
    for stage in range(NUM_STAGES):
        # Size of butterfly
        butterfly_size = 1 << (stage + 1)  # 2^(stage+1)
        half_size = butterfly_size >> 1     # butterfly_size / 2
        
        # Process each group
        num_groups = FFT_SIZE // butterfly_size
        # pragma hls pipeline enable
        # pragma loop_count {fft_size // 2}
        for group in range(num_groups):
            group_start = group * butterfly_size
            
            # Process each butterfly in the group
            # pragma hls pipeline enable
            # pragma loop_count {fft_size // 2}
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
    # pragma loop_count {fft_size}
    for i in range(FFT_SIZE):
        output[2*i] = signal_real[i]
        output[2*i + 1] = signal_imag[i]
    
    return output
"""

def write_fft_file(fft_size, filename):
    """Write FFT code to a file"""
    code = create_fft_code(fft_size)
    with open(filename, "w") as f:
        f.write(code)
    # Also save to a visible location for inspection
    with open(f"fft_{fft_size}_code.py", "w") as f:
        f.write(code)
    return filename

def analyze_fft(fft_size):
    """Analyze FFT code with specified FFT size"""
    logger.info(f"=" * 80)
    logger.info(f"Analyzing {fft_size}-point FFT")
    logger.info(f"=" * 80)
    
    # Create a temporary directory for test output
    import tempfile
    import shutil
    test_dir = tempfile.mkdtemp()
    
    try:
        # Generate code and save to file
        filepath = os.path.join(test_dir, f"fft_{fft_size}.py")
        write_fft_file(fft_size, filepath)
        logger.info(f"Generated {fft_size}-point FFT code in {filepath}")
        
        # Create an HLS instance
        hls = HLS(optimization_level=1, tech_node=45)
        
        # Compile the FFT code
        try:
            logger.info(f"Compiling {fft_size}-point FFT code")
            
            # Perform the compilation
            netlist = hls.compile(filepath, target="verilog")
            
            # Get performance metrics
            metrics = hls.get_performance_metrics()
            opt_report = hls.get_optimization_report()
            opt_summary = hls.get_optimization_summary()
            
            logger.info(f"RESULTS for {fft_size}-point FFT:")
            logger.info(f"  - Technology node: {metrics['technology_node']}")
            logger.info(f"  - Total area: {metrics['total_area']}")
            logger.info(f"  - Total power: {metrics['total_power']}")
            logger.info(f"  - Critical path: {metrics['critical_path']}")
            logger.info(f"  - Latency cycles: {metrics['latency_cycles']}")
            logger.info(f"  - Power breakdown: {metrics['power_breakdown']}")
            logger.info(f"  - Optimization summary: {opt_summary}")
            
            # Clean up
            shutil.rmtree(test_dir)
            
            return {
                "netlist": netlist,
                "metrics": metrics,
                "opt_report": opt_report,
                "opt_summary": opt_summary
            }
            
        except Exception as e:
            logger.error(f"Error during compilation: {e}")
            # Clean up
            shutil.rmtree(test_dir)
            raise

    except Exception as e:
        logger.error(f"Error during FFT analysis: {e}")
        # Clean up
        shutil.rmtree(test_dir)
        raise

def main():
    """Main function to run tests"""
    logger.info("Starting FFT HLS analysis")
    
    # Analyze with 64-point FFT
    results_64 = analyze_fft(64)
    
    # Analyze with 128-point FFT
    results_128 = analyze_fft(128)
    
    # Compare results
    logger.info("=" * 80)
    logger.info("COMPARISON OF RESULTS:")
    logger.info("=" * 80)
    
    # Compare performance metrics
    metrics_64 = results_64["metrics"]
    metrics_128 = results_128["metrics"]
    
    logger.info(f"Total area for 64-point: {metrics_64['total_area']}")
    logger.info(f"Total area for 128-point: {metrics_128['total_area']}")
    logger.info(f"Area ratio 128/64: {metrics_128['total_area']/metrics_64['total_area'] if metrics_64['total_area'] != 0 else 'N/A'}")
    
    logger.info(f"Critical path for 64-point: {metrics_64['critical_path']}")
    logger.info(f"Critical path for 128-point: {metrics_128['critical_path']}")
    logger.info(f"Critical path ratio 128/64: {metrics_128['critical_path']/metrics_64['critical_path'] if metrics_64['critical_path'] != 0 else 'N/A'}")
    
    logger.info(f"Latency cycles for 64-point: {metrics_64['latency_cycles']}")
    logger.info(f"Latency cycles for 128-point: {metrics_128['latency_cycles']}")
    logger.info(f"Latency ratio 128/64: {metrics_128['latency_cycles']/metrics_64['latency_cycles'] if metrics_64['latency_cycles'] != 0 else 'N/A'}")
    
    return results_64, results_128


class TestFFT(unittest.TestCase):
    """Test FFT HLS functionality"""
    
    def test_fft_hls(self):
        """Test that FFT HLS compilation runs successfully"""
        # Run the analysis with a small size for testing
        results = analyze_fft(32)
        
        # Verify results
        self.assertIsNotNone(results["netlist"], "Netlist should not be None")
        self.assertGreater(results["metrics"]["total_area"], 0, "Area should be greater than 0")
        self.assertGreater(results["metrics"]["latency_cycles"], 0, "Latency should be greater than 0")


if __name__ == "__main__":
    main() 