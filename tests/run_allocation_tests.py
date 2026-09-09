#!/usr/bin/env python3
"""
Runner script for allocation tests with loop unrolling.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the test functions
from test_allocation_verification import test_matrix_multiply_with_unroll, test_multiple_unroll_factors

def main():
    """Main function to run the tests."""
    logger.info("Running loop unrolling allocation tests...")
    
    # Store results for summary
    results = {}
    
    # Run the matrix multiply test
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Matrix multiply with unrolled loops")
    logger.info("="*80)
    matrix_result = test_matrix_multiply_with_unroll()
    results["matrix_multiply"] = matrix_result
    logger.info(f"Matrix multiply test {'succeeded' if matrix_result else 'failed'}")
    
    # Run the multiple unroll factors test
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Multiple unroll factors comparison")
    logger.info("="*80)
    unroll_result = test_multiple_unroll_factors()
    results["unroll_factors"] = unroll_result
    logger.info(f"Multiple unroll factors test {'succeeded' if unroll_result else 'failed'}")
    
    # Overall result
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("✅ All tests passed")
        logger.info("\nLoop unrolling in the allocator is working correctly!")
        logger.info("The allocator now:")
        logger.info("1. Properly handles unroll factors from both partial and fully unrolled loops")
        logger.info("2. Scales resources based on unroll factors")
        logger.info("3. Tags resources that are part of unrolled operations")
        logger.info("4. Adjusts interconnect resources (MUXes) to support parallel execution")
        logger.info("5. Creates appropriate naming for resources that reflect their loop unrolling context")
        logger.info("\nThis enables the HLS compiler to generate hardware that executes loop iterations in parallel")
        logger.info("for improved performance, which is a key optimization in high-level synthesis.")
        return 0
    else:
        logger.info("❌ Some tests failed")
        logger.info("\nResults:")
        for test_name, passed in results.items():
            logger.info(f"  - {test_name}: {'✅ Passed' if passed else '❌ Failed'}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 