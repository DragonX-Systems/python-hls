"""
Bounded NumPy Matrix Multiplication Example.

Demonstrates fixed-shape 2D matrix multiplication lowered into hardware
memory interfaces and scheduleable nested execution loops.
"""

import numpy as np
from python_hls import HLS, numpy_kernel


# 4x4 matrix multiplication kernel
@numpy_kernel(
    shapes={"a": (4, 4), "b": (4, 4)},
    dtypes={"a": "int32", "b": "int32"},
)
def matrix_multiply(a, b):
    """Compute C = A @ B for 4x4 integer matrices."""
    return a @ b


def main():
    print("=== Python-HLS Bounded NumPy Matrix Multiplication ===")
    
    # Reference NumPy execution
    a = np.array([[1, 0, 2, 0],
                  [0, 3, 0, 4],
                  [0, 0, 5, 0],
                  [6, 0, 0, 7]], dtype=np.int32)
    b = np.eye(4, dtype=np.int32) * 2
    
    expected = a @ b
    print("NumPy Reference A @ B:\n", expected)

    # Compile to Verilog
    hls = HLS(optimization_level=1, tech_node=45)
    output_rtl = "matmul_4x4.v"
    
    print(f"\nCompiling matrix_multiply to Verilog ({output_rtl})...")
    netlist, logs = hls.compile_numpy(matrix_multiply, output_file=output_rtl)
    
    print("Compilation successful!")


if __name__ == "__main__":
    main()
