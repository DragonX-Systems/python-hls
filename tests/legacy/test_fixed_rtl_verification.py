#!/usr/bin/env python3
"""
Test RTL verification with fixed port mapping.
"""

import os
import sys
import tempfile
import logging

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python_hls import HLS

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Enable debug logging for verification components
logging.getLogger('python_hls.verification').setLevel(logging.DEBUG)

def simple_add(a, b):
    """Simple addition function for testing."""
    return a + b

def test_simple_function_rtl():
    """Test RTL verification with a simple function."""
    logger.info("Testing RTL verification with simple add function")
    
    # Create temporary file with the function
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
def simple_add(a, b):
    return a + b
""")
        temp_file = f.name
    
    try:
        # Initialize HLS
        hls = HLS()
        
        # Compile the function
        logger.info("Compiling simple_add function")
        hls.compile(temp_file, entry_function="simple_add")
        
        # Check if compilation succeeded
        if not hls.netlist:
            logger.error("Compilation failed - no netlist generated")
            return False
        
        logger.info(f"Generated {len(hls.netlist.modules)} modules")
        
        # Print module information
        for module_name, module in hls.netlist.modules.items():
            logger.info(f"Module: {module_name}")
            if hasattr(module, 'verilog_blocks') and module.verilog_blocks:
                verilog_code = module.verilog_blocks[0]
                
                # Extract module ports for debugging
                import re
                module_match = re.search(r'module\s+\w+\s*\((.*?)\);', verilog_code, re.DOTALL)
                if module_match:
                    port_declarations = module_match.group(1)
                    logger.info(f"Module ports:\n{port_declarations}")
                else:
                    logger.warning("Could not extract port information")
        
        # Test RTL verification
        logger.info("Starting RTL verification")
        verification_result = hls.verify_rtl(num_random_tests=5)
        
        if "error" in verification_result:
            logger.error(f"RTL verification failed: {verification_result['error']}")
            return False
        
        # Check verification results
        verification_results = verification_result.get("verification_results", {})
        logger.info(f"Verified {len(verification_results)} modules")
        
        for module_name, result in verification_results.items():
            if "error" in result:
                logger.error(f"Module {module_name} verification failed: {result['error']}")
                return False
            else:
                logger.info(f"Module {module_name} verification completed")
                if "comparison" in result:
                    comparison = result["comparison"]
                    logger.info(f"  Passed: {comparison.get('passed', 0)}")
                    logger.info(f"  Failed: {comparison.get('failed', 0)}")
                    logger.info(f"  Success rate: {comparison.get('success_rate', 0):.2%}")
        
        logger.info("RTL verification test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during RTL verification test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def test_port_extraction():
    """Test the port extraction functionality specifically."""
    logger.info("Testing port extraction from Verilog modules")
    
    # Create temporary file with the function
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
def multiply_add(x, y, z):
    return x * y + z
""")
        temp_file = f.name
    
    try:
        # Initialize HLS
        hls = HLS()
        
        # Compile the function
        logger.info("Compiling multiply_add function")
        hls.compile(temp_file, entry_function="multiply_add")
        
        # Check if compilation succeeded
        if not hls.netlist:
            logger.error("Compilation failed - no netlist generated")
            return False
        
        # Test port extraction
        from python_hls.verification.rtl_verifier import RTLVerifier
        verifier = RTLVerifier()
        
        for module_name, module in hls.netlist.modules.items():
            logger.info(f"Testing port extraction for module: {module_name}")
            
            port_info = verifier._extract_module_port_info(module)
            if port_info:
                logger.info("Port extraction successful:")
                logger.info(f"  Input ports: {[p['name'] for p in port_info['input_ports']]}")
                logger.info(f"  Output ports: {[p['name'] for p in port_info['output_ports']]}")
                
                # Test test vector generation
                test_vectors = verifier._generate_test_vectors_from_ports(port_info, 3)
                logger.info(f"  Generated {len(test_vectors)} test vectors")
                for i, tv in enumerate(test_vectors):
                    logger.info(f"    Test {i+1}: {tv}")
                
                return True
            else:
                logger.error("Port extraction failed")
                return False
        
        return False
        
    except Exception as e:
        logger.error(f"Error during port extraction test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

if __name__ == "__main__":
    logger.info("Starting RTL verification fix tests")
    
    # Test port extraction first
    logger.info("=" * 60)
    logger.info("TEST 1: Port Extraction")
    logger.info("=" * 60)
    port_test_passed = test_port_extraction()
    
    # Test simple function RTL verification
    logger.info("=" * 60)
    logger.info("TEST 2: Simple Function RTL Verification")
    logger.info("=" * 60)
    rtl_test_passed = test_simple_function_rtl()
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Port extraction test: {'PASSED' if port_test_passed else 'FAILED'}")
    logger.info(f"RTL verification test: {'PASSED' if rtl_test_passed else 'FAILED'}")
    
    if port_test_passed and rtl_test_passed:
        logger.info("All tests PASSED! RTL verification fixes are working.")
        sys.exit(0)
    else:
        logger.error("Some tests FAILED. RTL verification needs more work.")
        sys.exit(1) 