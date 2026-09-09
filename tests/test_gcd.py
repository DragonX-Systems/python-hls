"""
GCD tests - requires API that compiles from function objects.
Skipped: current HLS compiles from file path only.
"""
import sys
import os
import logging
import tempfile
from pathlib import Path

import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def gcd(a, b):
    """Compute the greatest common divisor of a and b."""
    while b:
        a, b = b, a % b
    return a

def enhanced_gcd(a, b):
    """Enhanced GCD implementation with explicit operations to ensure ALU usage.
    This version makes the ALU operations more explicit to help the HLS engine.
    """
    # Initialize variables
    result = 0
    
    # Main GCD algorithm
    while b != 0:
        # Explicitly compute modulo using subtract operations
        temp_a = a
        temp_b = b
        remainder = temp_a
        
        # Manual modulo calculation to force ALU operations
        while remainder >= temp_b:
            remainder = remainder - temp_b
        
        # Update values for next iteration
        a = temp_b
        b = remainder
        
        # Add extra operations to ensure we have multiple arithmetic operations
        result = a + 0  # Force an additional ALU operation
    
    return a

@pytest.mark.skip(reason="Legacy API: compile(function_object), hls.run(). Current API: compile(file_path). Use examples/gcd.py + verify-equivalence instead.")
def test_gcd_legacy():
    """Legacy test - uses compile(function), hls.run() which no longer exist."""
    pass


def test_gcd_file_based():
    """Test GCD compilation using file-based API (current)."""
    # Use examples/gcd.py which exists in the repo
    gcd_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'gcd.py')
    if not os.path.exists(gcd_file):
        pytest.skip("examples/gcd.py not found")

    hls = HLS(optimization_level=1, tech_node=45)
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = os.path.join(tmpdir, "gcd.v")
        result = hls.compile(gcd_file, target="verilog", output_file=output_file)
        netlist = result[0] if isinstance(result, tuple) else result

        assert netlist is not None
        assert hasattr(netlist, 'modules')
        assert len(netlist.modules) > 0
        assert 'gcd' in netlist.modules
        assert os.path.exists(output_file)
        with open(output_file) as f:
            verilog = f.read()
        assert 'module gcd' in verilog or 'module gcd' in verilog.lower()


if __name__ == "__main__":
    pytest.main([__file__, '-v']) 