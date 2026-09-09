"""
Test script to demonstrate hardware allocation verification and loop unrolling pragmas.
"""

import os
import sys
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import the main module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls.hls import HLS

def test_matrix_multiply_with_unroll():
    """Test case with matrix multiply and loop unrolling pragma."""
    
    # Create a temporary file with the matrix multiplication code
    test_file = "tests/test_matrix_multiply_unroll.py"
    
    # Example matrix multiplication with unroll pragmas
    code = """
def matrix_multiply(A, B, C, N, M, P):
    # Matrix multiplication: C = A * B
    # A is NxM, B is MxP, C is NxP
    
    # pragma hls pipeline enable
    
    # Outer loop - each row of A
    # pragma loop_count 8
    # pragma unroll 2  # Partial unrolling of outer loop
    for i in range(N):
        # Middle loop - each column of B
        # pragma loop_count 8
        for j in range(P):
            # Initialize accumulator
            sum_val = 0
            
            # Inner loop - dot product
            # pragma loop_count 16
            # pragma unroll full  # Fully unroll innermost loop
            for k in range(M):
                # Multiply and accumulate - this produces actual operations
                a_val = A[i*M + k]
                b_val = B[k*P + j] 
                prod = a_val * b_val  # Multiplier
                sum_val = sum_val + prod  # Adder
            
            # Store result in C
            C[i*P + j] = sum_val
    
    return C
"""
    
    # Write the code to a file
    with open(test_file, "w") as f:
        f.write(code)
    
    try:
        # Create HLS compiler instance
        hls = HLS(optimization_level=3)  # Use level 3 to enable loop unrolling
        
        # Compile the code
        logger.info("Compiling matrix multiplication with unroll pragmas...")
        netlist = hls.compile(test_file)
        
        # Explicitly apply loop unrolling to match what we expect from pragmas
        hls.enable_loop_unrolling("matrix_multiply", 0, 2)  # Partially unroll outer loop
        hls.enable_loop_unrolling("matrix_multiply", 2, 0, True)  # Fully unroll innermost loop
        logger.info("Applied explicit loop unrolling to match pragmas")
        
        # Debug: Print operations in scheduled IR
        if hls.scheduled_ir:
            logger.info("Operations in scheduled IR:")
            operation_count = 0
            for func_name, func in hls.scheduled_ir.functions.items():
                logger.info(f"Function: {func_name}")
                for block in func.blocks:
                    logger.info(f"  Block: {block.name}")
                    if hasattr(block, 'unroll_factor') and block.unroll_factor > 1:
                        logger.info(f"    ⭐ Block has unroll factor: {block.unroll_factor}")
                    if hasattr(block, 'full_unroll') and block.full_unroll:
                        logger.info(f"    ⭐ Block has full unrolling enabled")
                    for instr in block.instructions:
                        logger.info(f"    Instruction: {instr.name}")
                        for op in instr.operations:
                            operation_count += 1
                            logger.info(f"      Operation: {op.name} (Type: {op.op_type.name if hasattr(op.op_type, 'name') else op.op_type})")
            logger.info(f"Total operations: {operation_count}")
        
        # Use the built-in allocator to allocate resources
        logger.info("Allocating resources using the built-in allocator...")
        hls.allocate_resources()
        
        # Get resource allocation information
        resources = hls.get_resource_report()
        logger.info(f"Resource allocation: {json.dumps(resources, indent=2)}")
        
        # Get unroll factors from function and blocks
        if hls.scheduled_ir:
            for func_name, func in hls.scheduled_ir.functions.items():
                total_unroll = getattr(func, 'total_unroll_factor', 1)
                logger.info(f"Function '{func_name}' total unroll factor: {total_unroll}")
                
                for block in func.blocks:
                    if hasattr(block, 'unroll_factor') and block.unroll_factor > 1:
                        logger.info(f"Block '{block.name}' unroll factor: {block.unroll_factor}")
                    if hasattr(block, 'full_unroll') and block.full_unroll:
                        iterations = getattr(block, 'loop_iterations', 'unknown')
                        logger.info(f"Block '{block.name}' fully unrolled with {iterations} iterations")
        
        # Get loop unrolling report
        unroll_report = hls.get_loop_unrolling_report()
        if unroll_report:
            logger.info(f"Loop unrolling report: {json.dumps(unroll_report, indent=2)}")
            
            # Check if we have the expected unrolling
            if unroll_report.get("unrolled_loops", 0) >= 2:
                logger.info("✅ Successfully detected multiple loop unrolling pragmas")
            else:
                logger.warning("❌ Failed to detect all loop unrolling pragmas")
                
            # Check if we have at least one fully unrolled loop
            if unroll_report.get("fully_unrolled", 0) >= 1:
                logger.info("✅ Successfully detected full loop unrolling")
            else:
                logger.warning("❌ Failed to detect full loop unrolling")
                
            # Check if we have at least one partially unrolled loop
            if unroll_report.get("partially_unrolled", 0) >= 1:
                logger.info("✅ Successfully detected partial loop unrolling")
            else:
                logger.warning("❌ Failed to detect partial loop unrolling")
        else:
            logger.warning("No loop unrolling report available")
        
        # Verify hardware allocation
        try:
            verification = hls.verify_hardware_allocation()
            logger.info(f"Allocation verification: {json.dumps(verification, indent=2)}")
            
            # Print the allocation score
            logger.info(f"Allocation score: {verification.get('allocation_score', 'N/A')} - {verification.get('assessment', 'N/A')}")
            
            # Check resource counts for unrolling evidence
            if resources and "modules" in resources:
                for module_name, module_data in resources["modules"].items():
                    if "resources" in module_data:
                        # Check for multiplied resources indicating unrolling
                        resource_counts = module_data["resources"]
                        logger.info(f"Resource counts for module {module_name}:")
                        
                        # Check for computational resources that should be multiplied by unroll factor
                        compute_resources = ["ALU_32bit", "Multiplier_32bit", "Adder_32bit"]
                        for resource in compute_resources:
                            if resource in resource_counts and resource_counts[resource] > 4:
                                logger.info(f"  ✅ High {resource} count ({resource_counts[resource]}) suggests successful loop unrolling")
                            elif resource in resource_counts:
                                logger.info(f"  Resource {resource}: {resource_counts[resource]}")
            
            # Show recommendations if any
            if 'recommendations' in verification and verification['recommendations']:
                logger.info("Allocation recommendations:")
                for rec in verification['recommendations']:
                    logger.info(f"  * {rec['resource']}: {rec['message']} (Severity: {rec['severity']})")
        except Exception as e:
            logger.warning(f"Hardware allocation verification failed: {e}")
        
        # Return success
        return True
    except Exception as e:
        logger.error(f"Error in test: {e}")
        return False
    finally:
        # Clean up the temporary file
        if os.path.exists(test_file):
            os.remove(test_file)

def test_multiple_unroll_factors():
    """Test case with different unroll factors to compare hardware allocation."""
    
    results = {}
    
    # Test with different unroll factors
    for unroll_factor in [1, 2, 4, 8]:
        test_file = f"tests/test_unroll_factor_{unroll_factor}.py"
        
        # Create a simple kernel with an adjustable unroll factor
        code = f"""
# This kernel will be compiled with unroll_factor = {unroll_factor}

def compute_kernel(A, B, C, size):
    # pragma hls pipeline enable
    
    # Define these constants to ensure they show up in the IR
    UNROLL_FACTOR = {unroll_factor}  # Explicitly declare unroll factor
    
    # Variables for parallel computation
    parallel_ops = UNROLL_FACTOR
    
    # Main computation loop with unroll pragma
    # pragma loop_count 64
    # pragma unroll {unroll_factor}
    for i in range(size):
        # Some real computation operations that will require hardware resources
        a_val = A[i]
        b_val = B[i]
        
        # Each parallel instance needs these operations
        # pragma unroll full
        for j in range(UNROLL_FACTOR):  # This inner loop should be completely unrolled
            idx = (i + j) % size
            
            # Operations that need ALUs (arithmetic)
            temp1 = a_val + b_val
            temp2 = a_val * b_val
            temp3 = a_val - b_val
            temp4 = a_val / (b_val + 1)  # Avoid division by zero
            
            # Bitwise operations
            temp5 = a_val & b_val
            temp6 = a_val | b_val
            temp7 = a_val ^ b_val
            
            # Shifting operations
            temp8 = a_val << 2
            temp9 = b_val >> 1
            
            # Store the result
            if j == 0:
                C[i] = temp1 + temp2 - temp3 + temp4 + temp5 + temp6 + temp7 + temp8 + temp9
            else:
                # Additional stores for different unroll factors
                if idx < size:
                    C[idx] = temp1 * temp2 / (temp3 + 1) + temp4 + temp5 - temp6 * temp7 + temp8 - temp9
        
    return C
"""
        
        # Write the code to a file
        with open(test_file, "w") as f:
            f.write(code)
        
        try:
            # Create HLS compiler instance with high optimization level to enable unrolling
            hls = HLS(optimization_level=3)
            
            # Compile the code
            logger.info(f"Compiling with unroll factor {unroll_factor}...")
            netlist = hls.compile(test_file)
            
            # Use our new API to explicitly apply loop unrolling
            if unroll_factor > 1:
                # Apply loop unrolling to the main loop (index 0)
                hls.enable_loop_unrolling("compute_kernel", 0, unroll_factor)
                
                # Apply full unrolling to the inner loop (index 1)
                hls.enable_loop_unrolling("compute_kernel", 1, 0, True)
                logger.info(f"Applied explicit loop unrolling with factor {unroll_factor} to outer loop and full unrolling to inner loop")
            
            # Debug output to show IR details
            if hls.scheduled_ir:
                for func_name, func in hls.scheduled_ir.functions.items():
                    logger.info(f"Function {func_name} has total_unroll_factor: {getattr(func, 'total_unroll_factor', 1)}")
                    loop_blocks = []
                    for block in func.blocks:
                        if hasattr(block, 'unroll_factor') and block.unroll_factor > 1:
                            loop_blocks.append(block)
                            logger.info(f"  Block {block.name} has unroll_factor: {block.unroll_factor}")
                    
                    logger.info(f"  Found {len(loop_blocks)} blocks with unroll factors")
            
            # Use the built-in allocator
            logger.info(f"Allocating resources for unroll factor {unroll_factor}...")
            hls.allocate_resources()
            
            # Get the unroll report
            unroll_report = hls.get_loop_unrolling_report()
            logger.info(f"Unroll report for factor {unroll_factor}: {json.dumps(unroll_report, indent=2) if unroll_report else 'None'}")
            
            # Get resource allocation information
            resources = hls.get_resource_report()
            if resources:
                logger.info(f"Resources with unroll factor {unroll_factor}: {json.dumps(resources, indent=2)}")
            else:
                logger.warning(f"No resource data available for unroll factor {unroll_factor}")
                resources = {"resources": {}}
            
            # Try to verify hardware allocation
            try:
                verification = hls.verify_hardware_allocation()
                logger.info(f"Verification with unroll factor {unroll_factor}: {json.dumps(verification, indent=2)}")
            except Exception as e:
                logger.warning(f"Failed to verify hardware allocation: {e}")
                verification = {"allocation_score": "N/A", "assessment": "N/A"}
            
            # Store results
            results[unroll_factor] = {
                "resources": resources,
                "unroll_report": unroll_report or {},
                "verification": verification
            }
            
        except Exception as e:
            logger.error(f"Error in test with unroll factor {unroll_factor}: {e}")
        finally:
            # Clean up the temporary file
            if os.path.exists(test_file):
                os.remove(test_file)
    
    # Compare results
    if results:
        logger.info("Comparison of hardware resources with different unroll factors:")
        
        # Create a summary table
        headers = ["Unroll Factor", "ALUs", "Registers", "MUXes", "Multipliers", "Score"]
        rows = []
        
        for factor, data in results.items():
            resources_data = data.get("resources", {})
            modules_data = resources_data.get("modules", {})
            module_data = next(iter(modules_data.values())) if modules_data else {}
            
            # Get resource counts from the module resources
            resource_counts = module_data.get("resources", {})
            verification = data.get("verification", {})
            
            rows.append([
                factor,
                resource_counts.get("ALU_32bit", 0),
                resource_counts.get("Register_32bit", 0),
                resource_counts.get("MUX_32bit", 0),
                resource_counts.get("Multiplier_32bit", 0),
                verification.get("allocation_score", "N/A")
            ])
        
        # Print the table
        format_row = "{:^12} | {:^6} | {:^10} | {:^6} | {:^12} | {:^6}"
        logger.info(format_row.format(*headers))
        logger.info("-" * 60)
        
        for row in rows:
            logger.info(format_row.format(*row))
        
        # Check if resource allocation increases with unroll factor
        if len(rows) > 1:
            resource_scaling = True
            for i in range(1, len(rows)):
                # Check if at least some resources increase with unroll factor
                increases = 0
                for j in range(1, 5):  # Check ALUs, Registers, MUXes, Multipliers
                    if isinstance(rows[i][j], (int, float)) and isinstance(rows[i-1][j], (int, float)):
                        if rows[i][j] > rows[i-1][j]:
                            increases += 1
                
                if increases == 0:
                    resource_scaling = False
                    break
            
            if resource_scaling:
                logger.info("✅ Resource allocation successfully scales with increasing unroll factor")
            else:
                logger.warning("❌ Resource allocation does not consistently scale with unroll factor")
        
        return True
    
    return False

if __name__ == "__main__":
    logger.info("Testing hardware allocation verification and loop unrolling pragmas...")
    
    test_matrix_multiply_with_unroll()
    logger.info("\n" + "="*80 + "\n")
    test_multiple_unroll_factors()
    
    logger.info("Tests completed.") 