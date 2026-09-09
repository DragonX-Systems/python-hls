#!/usr/bin/env python3
"""Test script to verify generalized array detection works with multiple workloads."""

import os
import sys
import tempfile
from python_hls.verification.rtl_verifier import RTLVerifier

def test_generalized_array_detection():
    """Test that generalized array detection works with HATS, FFT, and other workloads."""
    
    print("Testing generalized array detection across multiple workloads:")
    print("=" * 70)
    
    # Create RTL verifier instance
    verifier = RTLVerifier()
    
    # Test cases with different workloads
    test_cases = [
        # HATS workload
        {
            "file": "verification_workloads/hats_hls.py",
            "function": "hats_wrapped",
            "expected": {"events_x": True, "events_y": True, "events_p": True, "size": False}
        },
        {
            "file": "verification_workloads/hats_hls.py", 
            "function": "hats",
            "expected": {"events_x": True, "events_y": True, "events_p": True, "size": False}
        },
        # FFT workload
        {
            "file": "verification_workloads/fft.py",
            "function": "main",
            "expected": {"input_data": True}
        },
        {
            "file": "verification_workloads/fft.py",
            "function": "log2_int_hardware_optimized",
            "expected": {"n": False}
        },
        {
            "file": "verification_workloads/fft.py",
            "function": "complex_mult",
            "expected": {"a_real": False, "a_imag": False, "b_real": False, "b_imag": False}
        },
        {
            "file": "verification_workloads/fft.py",
            "function": "complex_add",
            "expected": {"a_real": False, "a_imag": False, "b_real": False, "b_imag": False}
        },
    ]
    
    # Also test with matrix multiplication workload if available
    if os.path.exists("verification_workloads/matrix_mul.py"):
        test_cases.append({
            "file": "verification_workloads/matrix_mul.py",
            "function": "matrix_multiply",
            "expected": {"A": True, "B": True, "C": True, "size": False}
        })
    
    all_passed = True
    
    for i, test_case in enumerate(test_cases):
        print(f"\nTest {i+1}: {test_case['file']} - {test_case['function']}")
        
        if not os.path.exists(test_case["file"]):
            print(f"  ⚠️  File not found: {test_case['file']}")
            continue
        
        # Extract function info
        func_info = verifier._extract_function_info_from_source(test_case["file"], test_case["function"])
        
        if func_info is None:
            print(f"  ✗ Could not extract function info for {test_case['function']}")
            all_passed = False
            continue
        
        print(f"  Function: {func_info['name']}")
        
        # Check each parameter
        test_passed = True
        for param in func_info["parameters"]:
            param_name = param["name"]
            is_array = param["is_array"]
            expected_array = test_case["expected"].get(param_name)
            
            if expected_array is None:
                print(f"    ⚠️  Unexpected parameter: {param_name}")
                continue
            
            if is_array == expected_array:
                print(f"    ✓ {param_name}: {'array' if is_array else 'scalar'}")
            else:
                print(f"    ✗ {param_name}: {'array' if is_array else 'scalar'} (expected {'array' if expected_array else 'scalar'})")
                test_passed = False
                all_passed = False
        
        if test_passed:
            print(f"  ✅ PASSED")
        else:
            print(f"  ❌ FAILED")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 All tests passed! Generalized array detection is working correctly.")
    else:
        print("❌ Some tests failed. Check the output above.")
    
    return all_passed

def test_generalized_test_vector_generation():
    """Test that generalized test vector generation works with different workloads."""
    
    print("\nTesting generalized test vector generation:")
    print("=" * 50)
    
    # Create RTL verifier instance
    verifier = RTLVerifier()
    
    # Test with HATS
    print("\n1. Testing with HATS workload:")
    try:
        hats_vectors = verifier._generate_test_vectors_for_python_function(
            "verification_workloads/hats_hls.py", "hats_wrapped", 3
        )
        print(f"   Generated {len(hats_vectors)} test vectors")
        if hats_vectors:
            print(f"   Sample: {hats_vectors[0]}")
            # Check that array parameters are lists and scalar parameters are integers
            sample = hats_vectors[0]
            for key, value in sample.items():
                if key in ['events_x', 'events_y', 'events_p']:
                    if isinstance(value, list):
                        print(f"   ✓ {key}: array (length {len(value)})")
                    else:
                        print(f"   ✗ {key}: should be array but got {type(value)}")
                elif key == 'size':
                    if isinstance(value, int):
                        print(f"   ✓ {key}: scalar ({value})")
                    else:
                        print(f"   ✗ {key}: should be scalar but got {type(value)}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test with FFT
    print("\n2. Testing with FFT workload:")
    try:
        fft_vectors = verifier._generate_test_vectors_for_python_function(
            "verification_workloads/fft.py", "main", 3
        )
        print(f"   Generated {len(fft_vectors)} test vectors")
        if fft_vectors:
            print(f"   Sample: {fft_vectors[0]}")
            # Check that input_data is an array
            sample = fft_vectors[0]
            for key, value in sample.items():
                if key == 'input_data':
                    if isinstance(value, list):
                        print(f"   ✓ {key}: array (length {len(value)})")
                    else:
                        print(f"   ✗ {key}: should be array but got {type(value)}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test with scalar function
    print("\n3. Testing with scalar function:")
    try:
        scalar_vectors = verifier._generate_test_vectors_for_python_function(
            "verification_workloads/fft.py", "complex_mult", 3
        )
        print(f"   Generated {len(scalar_vectors)} test vectors")
        if scalar_vectors:
            print(f"   Sample: {scalar_vectors[0]}")
            # Check that all parameters are scalars
            sample = scalar_vectors[0]
            for key, value in sample.items():
                if isinstance(value, (int, float)):
                    print(f"   ✓ {key}: scalar ({value})")
                else:
                    print(f"   ✗ {key}: should be scalar but got {type(value)}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

if __name__ == "__main__":
    print("🔍 Testing Generalized Array Detection System")
    print("=" * 80)
    
    # Test array detection
    detection_success = test_generalized_array_detection()
    
    # Test vector generation
    test_generalized_test_vector_generation()
    
    print("\n" + "=" * 80)
    if detection_success:
        print("✅ Overall: Generalized array detection system is working correctly!")
    else:
        print("❌ Overall: Some issues found in generalized array detection.")
    
    sys.exit(0 if detection_success else 1)