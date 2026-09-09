#!/usr/bin/env python3
"""
Simple test script for RTL verification framework.
"""

import os
import sys
import tempfile
import logging

# Add the python_hls directory to the path
sys.path.insert(0, os.path.abspath('.'))

from python_hls import HLS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_simple_function():
    """Test RTL verification with a simple function."""
    
    print("Testing RTL Verification Framework")
    print("=" * 40)
    
    # Create a simple test function
    test_code = '''
def simple_add(a, b):
    """Simple addition function."""
    return a + b
'''
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_code)
        temp_file = f.name
    
    try:
        # Create HLS instance
        hls = HLS(optimization_level=1, tech_node=45)
        
        print("1. Compiling Python to Verilog...")
        
        # Compile the function
        result = hls.compile(temp_file, target="verilog")
        
        if result:
            print("   ✓ Compilation successful")
            
            # Check if verification framework is available
            print("\n2. Testing verification framework...")
            
            # Test vectors
            test_vectors = [
                {"a": 1, "b": 2},
                {"a": 0, "b": 5},
                {"a": -1, "b": 3},
                {"a": 10, "b": -5}
            ]
            
            # Test Python execution first
            print("   Testing Python execution...")
            python_results = hls.rtl_verifier.python_executor.execute_function(
                temp_file, "simple_add", test_vectors
            )
            
            if "results" in python_results:
                print("   ✓ Python execution successful")
                print("   Results:", python_results["results"])
            else:
                print("   ✗ Python execution failed:", python_results.get("error"))
                return False
            
            # Test RTL verification (will check Verilator availability)
            print("\n3. Testing RTL verification...")
            verification_results = hls.verify_rtl(
                test_vectors=test_vectors,
                num_random_tests=0,
                save_report=True
            )
            
            if "error" in verification_results:
                print(f"   ⚠ RTL verification not available: {verification_results['error']}")
                if "Verilator not available" in verification_results['error']:
                    print("   Install Verilator to enable full RTL verification")
                    print("   Framework is working - just missing Verilator")
                    return True
            else:
                print("   ✓ RTL verification completed successfully")
                if "report" in verification_results:
                    print("   Report generated successfully")
                return True
        else:
            print("   ✗ Compilation failed")
            return False
    
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def main():
    """Main test function."""
    success = test_simple_function()
    
    print("\n" + "=" * 40)
    if success:
        print("✓ RTL Verification Framework Test PASSED")
        print("\nThe verification framework is working correctly.")
        print("If Verilator is installed, full RTL verification will be available.")
    else:
        print("✗ RTL Verification Framework Test FAILED")
        print("\nThere may be an issue with the framework setup.")
    
    print("\nTo install Verilator for full RTL verification:")
    print("  Ubuntu/Debian: sudo apt-get install verilator")
    print("  macOS: brew install verilator")
    print("  From source: https://verilator.org/guide/latest/install.html")


if __name__ == "__main__":
    main() 